"""Fine-tune DistilBERT for scam-type classification (HuggingFace Trainer).

Sensible defaults for a small dataset (a few thousand examples):
    learning rate 2e-5, batch size 16, 4 epochs, warmup 10%,
    weight decay 0.01, early stopping on validation loss (patience 2),
    best checkpoint (lowest eval loss) kept.

Outputs:
    ml/model/                 saved weights + tokenizer (+ id2label config)
    ml/runs/training_log.json per-step/epoch losses
    ml/runs/loss_curves.png   train/val loss curves (matplotlib, if installed)
    ml/evaluation.md          test-set report: accuracy, per-class
                            precision/recall/F1, confusion matrix

S3 upload — deliberately a shell command, NOT code: ml/ must stay free
of AWS SDK imports (that's the backend layer's job):
    aws s3 cp ml/model s3://<bucket>/scam-shield/model/ --recursive

Usage:
    python prepare_dataset.py          # first
    python train_classifier.py
    python train_classifier.py --epochs 2 --max-examples 200   # smoke test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a script from the repo root without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
from torch.utils.data import Dataset  # noqa: E402

from scamshield_ml.labels import ALL_LABELS  # noqa: E402

ML_DIR = Path(__file__).resolve().parent
DATASET_DIR = ML_DIR / "dataset"
DEFAULT_OUTPUT_DIR = ML_DIR / "model"
RUNS_DIR = ML_DIR / "runs"


def load_jsonl_records(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


class MessageDataset(Dataset):
    """Plain torch Dataset — tokenised on the fly so the DataCollator can
    apply dynamic padding (faster than padding every row to max length)."""

    def __init__(self, texts: list[str], labels: list[int], tokenizer, max_length: int = 128):
        # 128 tokens comfortably covers SMS/WhatsApp-length messages and
        # keeps training fast; the classifier still truncates long input
        # gracefully at inference time.
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict:
        encoded = self.tokenizer(
            self.texts[idx],
            truncation=True,
            max_length=self.max_length,
            return_attention_mask=True,
        )
        item = {key: value for key, value in encoded.items()}
        item["labels"] = self.labels[idx]
        return item


def _per_class_metrics(labels: np.ndarray, preds: np.ndarray, label_list: list[str]) -> dict:
    """Precision/recall/F1/support per class, computed with numpy
    (avoids a sklearn dependency)."""
    per_class = {}
    for idx, label in enumerate(label_list):
        tp = int(((preds == idx) & (labels == idx)).sum())
        fp = int(((preds == idx) & (labels != idx)).sum())
        fn = int(((preds != idx) & (labels == idx)).sum())
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int((labels == idx).sum()),
        }
    return per_class


def _confusion_matrix(labels: np.ndarray, preds: np.ndarray, n_classes: int) -> np.ndarray:
    cm = np.zeros((n_classes, n_classes), dtype=int)
    for true, pred in zip(labels, preds):
        cm[int(true)][int(pred)] += 1
    return cm


def _confusion_matrix_markdown(cm: np.ndarray, label_list: list[str]) -> str:
    header = "| true \\ predicted | " + " | ".join(label_list) + " |"
    sep = "|" + "---|" * (len(label_list) + 1)
    rows = []
    for label, row in zip(label_list, cm):
        rows.append("| " + label + " | " + " | ".join(str(int(v)) for v in row) + " |")
    return "\n".join([header, sep] + rows)


def _write_evaluation_report(
    output_path: Path,
    *,
    model_name: str,
    args: argparse.Namespace,
    split_sizes: dict,
    test_metrics: dict,
    per_class: dict,
    cm: np.ndarray,
    epochs_trained: int,
) -> None:
    """Write evaluation.md: numbers + short written interpretation."""
    accuracy = test_metrics["accuracy"]
    macro_f1 = float(np.mean([m["f1"] for m in per_class.values()]))
    macro_precision = float(np.mean([m["precision"] for m in per_class.values()]))
    macro_recall = float(np.mean([m["recall"] for m in per_class.values()]))

    best_class = max(per_class, key=lambda k: per_class[k]["f1"])
    worst_class = min(per_class, key=lambda k: per_class[k]["f1"])

    # Most-confused off-diagonal pair.
    best_i, best_j = 0, 0
    best_off = -1
    for i in range(len(ALL_LABELS)):
        for j in range(len(ALL_LABELS)):
            if i != j and int(cm[i][j]) > best_off:
                best_off = int(cm[i][j])
                best_i, best_j = i, j

    lines = [
        "# Scam Shield — Classifier Evaluation",
        "",
        f"- **Base model:** {model_name} (fine-tuned)",
        f"- **Labels ({len(ALL_LABELS)}):** " + ", ".join(f"`{l}`" for l in ALL_LABELS),
        f"- **Hyperparameters:** lr={args.lr}, batch_size={args.batch_size}, "
        f"epochs={epochs_trained} (requested {args.epochs}, early stopping "
        f"patience={args.patience}), seed={args.seed}",
        f"- **Split sizes:** train={split_sizes['train']}, val={split_sizes['val']}, "
        f"test={split_sizes['test']}",
        "",
        "## Test-set metrics",
        "",
        "| Class | Precision | Recall | F1 | Support |",
        "|---|---|---|---|---|",
    ]
    for label in ALL_LABELS:
        m = per_class[label]
        lines.append(
            f"| {label} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['support']} |"
        )
    lines += [
        "",
        f"- **Accuracy:** {accuracy:.3f}",
        f"- **Macro precision:** {macro_precision:.3f}",
        f"- **Macro recall:** {macro_recall:.3f}",
        f"- **Macro F1:** {macro_f1:.3f}",
        "",
        "## Confusion matrix",
        "",
        _confusion_matrix_markdown(cm, ALL_LABELS),
        "",
        "## Interpretation",
        "",
        f"- Strongest class: **{best_class}** (F1 {per_class[best_class]['f1']:.3f}); "
        f"weakest class: **{worst_class}** (F1 {per_class[worst_class]['f1']:.3f}).",
        (
            f"- Most common confusion: `{ALL_LABELS[best_i]}` predicted as "
            f"`{ALL_LABELS[best_j]}` ({best_off} cases)"
            if best_off > 0
            else "- No cross-class confusions on the test set."
        ),
        f"- Overall accuracy {accuracy:.1%} on held-out messages the model never saw "
        "during training or early-stopping decisions.",
        "- Macro F1 is the number to quote for the viva: it weights every scam type "
        "equally, so a weak minority class (e.g. `impersonation` with few training "
        "rows) shows up clearly instead of hiding inside accuracy.",
        "",
        "### Next steps",
        "",
        "1. Expand hand-written seeds for the weakest class(es) in "
        "`dataset/handwritten/` and retrain.",
        "2. If precision on a class matters more than recall (e.g. avoid flagging "
        "legitimate messages), tune the decision threshold per class.",
        "3. Upload the weights for the backend:",
        "",
        "```bash",
        f"aws s3 cp {DEFAULT_OUTPUT_DIR} s3://<bucket>/scam-shield/model/ --recursive",
        "```",
        "",
    ]
    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--model-name", default="distilbert-base-uncased")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--runs-dir", type=Path, default=RUNS_DIR)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--patience", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-examples", type=int, default=0, help="Cap rows per split (smoke tests)")
    parser.add_argument("--max-length", type=int, default=128)
    args = parser.parse_args()

    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        DataCollatorWithPadding,
        EarlyStoppingCallback,
        Trainer,
        TrainingArguments,
    )

    # ----- data -----
    splits = {}
    for split in ("train", "val", "test"):
        path = args.data_dir / f"{split}.jsonl"
        if not path.exists():
            sys.exit(f"Missing {path}. Run `python prepare_dataset.py` first.")
        records = load_jsonl_records(path)
        if args.max_examples:
            records = records[: args.max_examples]
        splits[split] = records

    label2id = {label: idx for idx, label in enumerate(ALL_LABELS)}
    train_texts = [r["text"] for r in splits["train"]]
    train_labels = [label2id[r["label"]] for r in splits["train"]]

    # ----- model -----
    # id2label/label2id are saved into config.json so inference maps
    # logits back to the exact same label strings.
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name,
        num_labels=len(ALL_LABELS),
        id2label={idx: label for label, idx in label2id.items()},
        label2id=label2id,
    )
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    train_ds = MessageDataset(train_texts, train_labels, tokenizer, args.max_length)
    val_ds = MessageDataset(
        [r["text"] for r in splits["val"]],
        [label2id[r["label"]] for r in splits["val"]],
        tokenizer,
        args.max_length,
    )
    test_ds = MessageDataset(
        [r["text"] for r in splits["test"]],
        [label2id[r["label"]] for r in splits["test"]],
        tokenizer,
        args.max_length,
    )

    if len(train_ds) < 8:
        print("WARNING: fewer than 8 training rows — results will be meaningless.")

    def compute_metrics(eval_pred) -> dict:
        logits, labels = eval_pred
        preds = np.argmax(logits, axis=-1)
        accuracy = float((preds == labels).mean())
        per_class = _per_class_metrics(labels, preds, ALL_LABELS)
        return {
            "accuracy": accuracy,
            "precision_macro": float(np.mean([m["precision"] for m in per_class.values()])),
            "recall_macro": float(np.mean([m["recall"] for m in per_class.values()])),
            "f1_macro": float(np.mean([m["f1"] for m in per_class.values()])),
        }

    args_tf = TrainingArguments(
        output_dir=str(args.runs_dir / "checkpoints"),
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=args.lr,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=min(32, max(1, len(val_ds))),
        num_train_epochs=args.epochs,
        weight_decay=0.01,
        warmup_ratio=0.1,
        logging_steps=max(1, len(train_ds) // (args.batch_size * 5)),
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to=[],  # no WandB/etc. — keeps the project dependency-light
        seed=args.seed,
    )

    trainer = Trainer(
        model=model,
        args=args_tf,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        processing_class=tokenizer,
        data_collator=DataCollatorWithPadding(tokenizer),
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=args.patience)],
    )

    print(f"Training on {len(train_ds)} rows, validating on {len(val_ds)} ...")
    trainer.train()
    # Report how many epochs actually ran (early stopping may stop < args.epochs).
    epochs_trained = int(round(trainer.state.epoch or args.epochs))

    # ----- loss curves -----
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    train_losses = [entry["loss"] for entry in trainer.state.log_history if "loss" in entry]
    eval_losses = [(entry["epoch"], entry["eval_loss"]) for entry in trainer.state.log_history if "eval_loss" in entry]
    (RUNS_DIR / "training_log.json").write_text(
        json.dumps({"train_losses": train_losses, "eval_losses": eval_losses}, indent=2),
        encoding="utf-8",
    )
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(train_losses, label="train loss (logged steps)")
        if eval_losses:
            ax.plot([e for e, _ in eval_losses], [v for _, v in eval_losses], marker="o", label="val loss (per epoch)")
        ax.set_xlabel("epoch (train curve is approximate: logged steps)")
        ax.set_ylabel("loss")
        ax.set_title("Training / validation loss")
        ax.legend()
        fig.tight_layout()
        fig.savefig(RUNS_DIR / "loss_curves.png")
        print(f"Loss curves -> {RUNS_DIR / 'loss_curves.png'}")
    except ImportError:
        print("matplotlib not installed — loss curves saved as JSON only.")

    # ----- test evaluation -----
    test_metrics = trainer.predict(test_ds)
    preds = np.argmax(test_metrics.predictions, axis=-1)
    labels = test_metrics.label_ids
    per_class = _per_class_metrics(labels, preds, ALL_LABELS)
    cm = _confusion_matrix(labels, preds, len(ALL_LABELS))

    # ----- save model + report -----
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(args.output_dir)
    tokenizer.save_pretrained(args.output_dir)
    print(f"Model saved -> {args.output_dir}")

    _write_evaluation_report(
        ML_DIR / "evaluation.md",
        model_name=args.model_name,
        args=args,
        split_sizes={k: len(v) for k, v in splits.items()},
        test_metrics={"accuracy": float(test_metrics.metrics.get("test_accuracy", float((preds == labels).mean())))},
        per_class=per_class,
        cm=cm,
        epochs_trained=epochs_trained,
    )
    print(f"Evaluation report -> {ML_DIR / 'evaluation.md'}")

    print("\nUpload to S3 (backend pulls this at startup):")
    print(f"  aws s3 cp {args.output_dir} s3://<bucket>/scam-shield/model/ --recursive")


if __name__ == "__main__":
    main()
