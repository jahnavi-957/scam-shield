"""Assemble the labelled Scam Shield dataset + stratified train/val/test split.

DATASET SOURCING (3 layers — see ml/README.md):
  1. Hand-written Indian-context seeds (dataset/handwritten/*.jsonl).
     The CORE of the dataset: real Hinglish/English scam patterns.
  2. UCI SMS Spam Collection (via --uci-csv, or auto-download with the
     optional `datasets` library: Abirate/english_sms_spam).
     ham -> not_scam; spam is triaged to a subtype (conservative).
  3. Optional phishing-email CSV (Kaggle "Phishing Emails") via
     --phishing-csv.

WHY CONSERVATIVE TRIAGE: public spam collections are mostly benign
promotions/pranks, not Indian scams. A subtype label is assigned only
when the keyword count is >= 2 AND leads the runner-up by >= 1;
otherwise the row is DROPPED rather than risk a wrong label.

PRIVACY: public rows are PII-redacted before anything is written
(phones -> [PHONE], UPI IDs -> [UPI], URLs -> [URL], amounts ->
[AMOUNT]) using the package's own extractor.

DEDUPLICATION: exact duplicates removed instantly, then
near-duplicates found with MinHash + LSH banding and
verified with exact 3-gram Jaccard at 0.95 — the public
data is template-generated, so a lower threshold would
collapse legitimately distinct rows. Cross-split
near-duplicates at 0.85 are AUDITED and reported
(stats.json) instead of silently removed.

OUTPUT (JSONL, one JSON object per line — schema in dataset/README.md):
    dataset/train.jsonl  dataset/val.jsonl  dataset/test.jsonl
    dataset/stats.json

Usage:
    python prepare_dataset.py
    python prepare_dataset.py --uci-csv path/to/SMSSpamCollection
    python prepare_dataset.py --phishing-csv path/to/phishing.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Allow running as a script from the repo root without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scamshield_ml import ALL_LABELS, NOT_SCAM, extract_entities  # noqa: E402

ML_DIR = Path(__file__).resolve().parent
DATASET_DIR = ML_DIR / "dataset"
HANDWRITTEN_DIR = DATASET_DIR / "handwritten"

# --------------------------------------------------------------------------- #
# Layer 2 triage: keyword rules mapping public `spam` rows to subtypes
# --------------------------------------------------------------------------- #
_TRIAGE_KEYWORDS: dict[str, list[str]] = {
    "fake_prize": ["win", "winner", "prize", "gift", "lucky", "congratulation", "claim", "selected", "awarded", "cash"],
    "loan_scam": ["loan", "credit", "debt", "arrears", "repay", "mortgage", "guarantor"],
    "investment_fraud": ["invest", "profit", "return", "trading", "bitcoin", "crypto", "earn", "stock"],
    "phishing": ["verify", "account", "update", "confirm", "click", "urgent", "suspend", "security", "login", "password", "activate"],
    "impersonation": ["police", "bank manager", "family emergency", "son ", "daughter"],
}


def triage_spam(text: str) -> str | None:
    """Best-effort subtype for a public `spam` row; None = ambiguous -> drop."""
    lowered = text.lower()
    counts = {label: sum(lowered.count(kw) for kw in keywords) for label, keywords in _TRIAGE_KEYWORDS.items()}
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top_label, top_count = ranked[0]
    runner_up = ranked[1][1]
    if top_count >= 2 and top_count - runner_up >= 1:
        return top_label
    return None


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"  ! skipping invalid JSON at {path.name}:{line_no}: {exc}")
    return records


def load_handwritten(directory: Path = HANDWRITTEN_DIR) -> list[dict]:
    """Load hand-written seeds (dataset/handwritten/*.jsonl) and validate labels."""
    records: list[dict] = []
    if not directory.is_dir():
        return records
    for path in sorted(directory.glob("*.jsonl")):
        for rec in load_jsonl(path):
            label = str(rec.get("label", "")).strip().lower()
            text = str(rec.get("text", "")).strip()
            if label not in ALL_LABELS or not text:
                print(f"  ! skipping invalid row in {path.name}: label={label!r}")
                continue
            records.append({"text": text, "label": label, "source": "handwritten"})
    return records


def _download_uci() -> str | None:
    """Fetch the UCI SMS Spam Collection via the optional `datasets` library."""
    try:
        from datasets import load_dataset
    except ImportError:
        return None
    ds = load_dataset("Abirate/english_sms_spam", split="train")
    path = DATASET_DIR / "uci_sms_spam.csv"
    rows = [{"label": r["label"], "text": r["sms"]} for r in ds]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["label", "text"])
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def load_uci(path: str | None = None) -> list[dict]:
    """Load UCI SMS Spam Collection.

    Accepts the classic tab-separated `ham\\t<text>` file or the
    HF/Kaggle CSV export (columns `sms`/`text` + `label`).
    """
    if not path:
        path = _download_uci()
        if not path:
            print("  - `datasets` library not available; skipping UCI download.")
            print("    Optionally pass --uci-csv path/to/SMSSpamCollection")
            return []
    rows: list[dict] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        sample = f.read(4096)
        f.seek(0)
        has_header = any(col in sample.lower() for col in ("sms", "text", "message")) and "\t" not in sample.splitlines()[0].lower()
        if has_header:
            reader = csv.DictReader(f)
            text_col = next(c for c in ("sms", "text", "message") if c in (reader.fieldnames or []))
            label_col = next(c for c in ("label", "category") if c in (reader.fieldnames or []))
            for row in reader:
                rows.append({"label": row[label_col].strip().lower(), "text": row[text_col].strip()})
        else:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) >= 2:
                    rows.append({"label": parts[0].strip().lower(), "text": parts[1].strip()})

    records: list[dict] = []
    for row in rows:
        label = row["label"]
        text = row["text"]
        if label in ("ham", "not_spam", "not spam", "legitimate"):
            records.append({"text": text, "label": NOT_SCAM, "source": "uci"})
        elif label in ("spam", "smsspam"):
            subtype = triage_spam(text)
            if subtype:
                records.append({"text": text, "label": subtype, "source": "uci"})
            # ambiguous public spam is dropped by design
    return records


def load_phishing_csv(
    path: str,
    text_col: str = "text",
    label_col: str = "label",
    positive_label: str = "phishing",
    negative_label: str = "legitimate",
) -> list[dict]:
    """Load a phishing-email CSV (e.g. Kaggle "Phishing Emails")."""
    records: list[dict] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            text = (row.get(text_col) or "").strip()
            label = (row.get(label_col) or "").strip().lower()
            if not text or label not in (positive_label.lower(), negative_label.lower()):
                continue
            if label == positive_label.lower():
                records.append({"text": text, "label": "phishing", "source": "phishing_emails"})
            else:
                records.append({"text": text, "label": NOT_SCAM, "source": "phishing_emails"})
    return records


# --------------------------------------------------------------------------- #
# Indian fraud datasets (Kaggle downloads placed in ml/dataset/)
# --------------------------------------------------------------------------- #
# india_fraud_detection_FINAL.csv: 16 categories x 200 rows, label 1/0.
# Mapping rationale (classify by the scammer's PRIMARY goal):
#   * authority/company impersonation demanding payment
#     ( challan / courier / electricity / digital arrest ) -> impersonation
#   * credential/OTP lures ( KYC suspension / tax refund )  -> phishing
#   * lottery                                               -> fake_prize
#   * fake job offers (pay-to-work schemes)                 -> investment_fraud
#   * anything *_Legitimate                               -> not_scam
_INDIAN_FRAUD_MAP = {
    "Echallan_Scam": "impersonation",
    "Courier_Scam": "impersonation",
    "Electricity_Scam": "impersonation",
    "Digital_Arrest": "impersonation",
    "KYC_Suspension": "phishing",
    "Tax_Refund_Scam": "phishing",
    "Lottery_Scam": "fake_prize",
    "Job_Scam": "investment_fraud",
}

# India_Cyber_Scam_Hinglish_Dataset.csv: label 0 = not_scam; label 1 rows
# carry a scam_category that maps as follows.
_HINGLISH_MAP = {
    "police_digital_arrest": "impersonation",
    "police_blackmail": "impersonation",
    "amazon": "impersonation",  # fake parcel-delivery scam
    "relative": "impersonation",
    "bank_kyc": "phishing",
    "aadhaar": "phishing",
    "lottery": "fake_prize",
}


def load_india_fraud(path: str | Path) -> list[dict]:
    """Load india_fraud_detection_FINAL.csv (message_text + category)."""
    records: list[dict] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            text = (row.get("message_text") or "").strip()
            if not text:
                continue
            category = (row.get("category") or "").strip()
            if category.endswith("_Legitimate"):
                label = NOT_SCAM
            else:
                label = _INDIAN_FRAUD_MAP.get(category)
            if label is None:
                continue  # unknown category -> drop rather than mislabel
            records.append({"text": text, "label": label, "source": "india_fraud"})
    return records


def load_hinglish(path: str | Path) -> list[dict]:
    """Load India_Cyber_Scam_Hinglish_Dataset.csv (text + label + scam_category)."""
    records: list[dict] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            text = (row.get("text") or "").strip()
            if not text:
                continue
            if str(row.get("label") or "").strip() == "0":
                records.append({"text": text, "label": NOT_SCAM, "source": "hinglish"})
                continue
            label = _HINGLISH_MAP.get((row.get("scam_category") or "").strip())
            if label:
                records.append({"text": text, "label": label, "source": "hinglish"})
    return records


def load_phishing_corpus(directory: str | Path) -> list[dict]:
    """Load the Phishing-Email-Dataset-main corpus (subject + body).

    Labelling convention for this corpus:
      * CEAS_08, Nazario, Nigerian_Fraud, PhishingEmailData -> all phishing
      * Ling.csv: label 1 -> phishing, label 0 -> not_scam
      * Enron.csv: all rows -> not_scam (promotional mail, not scams)
      * SpamAssasin.csv / spamResults.csv: no usable label column -> skipped
    """
    directory = Path(directory)
    records: list[dict] = []

    def _read(name: str) -> list[dict]:
        csv.field_size_limit(2**31 - 1)  # email bodies exceed the default limit
        with open(directory / name, encoding="utf-8", errors="replace") as f:
            return list(csv.DictReader(f))

    def _text(row: dict, *cols: str) -> str:
        return " ".join(str(row.get(c) or "").strip() for c in cols if row.get(c))

    for name in ("CEAS_08.csv", "Nazario.csv"):
        for row in _read(name):
            text = _text(row, "subject", "body")
            if text:
                records.append({"text": text, "label": "phishing", "source": "phishing_corpus"})

    for row in _read("Nigerian_Fraud.csv"):
        text = _text(row, "subject", "body")
        if text:
            records.append({"text": text, "label": "phishing", "source": "phishing_corpus"})

    for row in _read("PhishingEmailData.csv"):
        text = _text(row, "Email_Subject", "Email_Content")
        if text:
            records.append({"text": text, "label": "phishing", "source": "phishing_corpus"})

    for row in _read("Ling.csv"):
        text = _text(row, "subject", "body")
        if not text:
            continue
        label = "phishing" if str(row.get("label") or "").strip() == "1" else NOT_SCAM
        records.append({"text": text, "label": label, "source": "phishing_corpus"})

    for row in _read("Enron.csv"):
        text = _text(row, "subject", "body")
        if text:
            records.append({"text": text, "label": NOT_SCAM, "source": "phishing_corpus"})

    return records


# --------------------------------------------------------------------------- #
# PII redaction + deduplication
# --------------------------------------------------------------------------- #
def redact_pii(text: str) -> str:
    """Replace extracted entities with typed placeholders."""
    entities = extract_entities(text)
    redacted = text
    for entity_type, placeholder in (
        ("urls", "[URL]"),
        ("upi_ids", "[UPI]"),
        ("phone_numbers", "[PHONE]"),
        ("amounts", "[AMOUNT]"),
    ):
        for value in entities[entity_type]:
            needle = value["raw"] if isinstance(value, dict) else value
            redacted = redacted.replace(needle, placeholder)
    return redacted


# --------------------------------------------------------------------------- #
# Scalable near-duplicate detection: MinHash + LSH banding
# --------------------------------------------------------------------------- #
# Why: the public Indian datasets are TEMPLATE-generated, so naive
# char-3-gram Jaccard at a low threshold collapses thousands of
# legitimately distinct rows (and an O(n^2) all-pairs check is too
# slow at this size). Instead:
#   * exact duplicates are removed with a set (instant)
#   * candidate near-duplicates are found with MinHash + LSH
#     banding (16 permutations, 4 bands of 4 rows) — two rows with
#     Jaccard >= ~0.9 collide in a bucket with ~99% probability,
#     so only a small fraction of pairs need exact comparison
#   * candidates are verified with the exact Jaccard test
#
# The removal threshold is deliberately HIGH (0.92): template
# variants (same scam, different amount/phone) are near-duplicates
# by design, and removing them all would throw away most of the
# data. Instead we keep them, and val/test rows that are
# near-duplicates of train rows are REMOVED by
# remove_cross_split_near_dups so test accuracy stays honest.
_NUM_PERM = 16
_ROWS_PER_BAND = 4
_BANDS = _NUM_PERM // _ROWS_PER_BAND
_SALTS = [f"scamshield-salt-{i}" for i in range(_NUM_PERM)]


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union else 0.0


def _normalize_for_dedup(text: str) -> str:
    return "".join(ch for ch in text.lower() if ch.isalnum())


def _char_ngrams(text: str, n: int = 3) -> set[str]:
    return {text[i : i + n] for i in range(max(len(text) - n + 1, 0))}


def _minhash_signature(ngrams: set[str]) -> tuple:
    """16-permutation MinHash signature of an n-gram set."""
    sig = []
    for salt in _SALTS:
        minimum = 0xFFFFFFFF
        for gram in ngrams:
            digest = hashlib.md5((salt + gram).encode("utf-8")).digest()
            value = int.from_bytes(digest[:4], "big")
            if value < minimum:
                minimum = value
        sig.append(minimum)
    return tuple(sig)


def _lsh_buckets(
    records: list[dict],
) -> tuple[list[set], list[tuple], list[int], dict]:
    """Index records by LSH band; returns (ngrams, signatures,
    lengths, bucket -> record indices)."""
    ngrams_list: list[set] = []
    sigs: list[tuple] = []
    lengths: list[int] = []
    buckets: dict = defaultdict(list)
    for idx, rec in enumerate(records):
        norm = _normalize_for_dedup(rec["text"])
        ngrams = _char_ngrams(norm)
        sig = _minhash_signature(ngrams)
        ngrams_list.append(ngrams)
        sigs.append(sig)
        lengths.append(len(norm))
        for band_idx in range(_BANDS):
            band = sig[band_idx * _ROWS_PER_BAND : (band_idx + 1) * _ROWS_PER_BAND]
            buckets[(band_idx, band)].append(idx)
    return ngrams_list, sigs, lengths, buckets


def _greedy_dedupe(records: list[dict], threshold: float) -> tuple[list[dict], int]:
    """Greedy near-duplicate removal against already-kept rows."""
    kept: list[dict] = []
    kept_ngrams: list[set] = []
    kept_sigs: list[tuple] = []
    kept_lengths: list[int] = []
    buckets: dict = defaultdict(list)
    seen_exact: set[str] = set()
    removed = 0

    for rec in records:
        norm = _normalize_for_dedup(rec["text"])
        if norm in seen_exact:
            removed += 1
            continue
        ngrams = _char_ngrams(norm)
        sig = _minhash_signature(ngrams)
        length = len(norm)

        candidates: set[int] = set()
        for band_idx in range(_BANDS):
            band = sig[band_idx * _ROWS_PER_BAND : (band_idx + 1) * _ROWS_PER_BAND]
            key = (band_idx, band)
            candidates.update(buckets.get(key, ()))

        is_dup = False
        for j in candidates:
            if abs(kept_lengths[j] - length) > 0.2 * max(kept_lengths[j], length, 1):
                continue
            if _jaccard(ngrams, kept_ngrams[j]) >= threshold:
                is_dup = True
                break
        if is_dup:
            removed += 1
            continue
        seen_exact.add(norm)
        # Register in the LSH index ONLY if kept — discarded
        # duplicates must never become comparison targets.
        for band_idx in range(_BANDS):
            band = sig[band_idx * _ROWS_PER_BAND : (band_idx + 1) * _ROWS_PER_BAND]
            buckets.setdefault((band_idx, band), []).append(len(kept))
        kept.append(rec)
        kept_ngrams.append(ngrams)
        kept_sigs.append(sig)
        kept_lengths.append(length)
    return kept, removed


def dedupe(records: list[dict], threshold: float = 0.95) -> tuple[list[dict], int]:
    """Exact + near-duplicate removal (MinHash + LSH, then exact
    Jaccard verification). Runs globally across labels so no
    near-duplicate can leak between train/val/test."""
    return _greedy_dedupe(records, threshold)


def remove_cross_split_near_dups(
    train: list[dict],
    other: list[dict],
    threshold: float = 0.85,
) -> tuple[list[dict], int]:
    """Leakage prevention: drop rows in `other` (val/test) that
    have a near-duplicate in `train` at `threshold`.

    Uses the same MinHash + LSH candidate search (fast); only
    candidates are verified with exact Jaccard.
    Returns (kept_rows, removed_count).
    """
    if not train or not other:
        return list(other), 0
    train_ngrams, _, train_lengths, buckets = _lsh_buckets(train)
    kept: list[dict] = []
    removed = 0
    for rec in other:
        norm = _normalize_for_dedup(rec["text"])
        ngrams = _char_ngrams(norm)
        sig = _minhash_signature(ngrams)
        length = len(norm)
        candidates: set[int] = set()
        for band_idx in range(_BANDS):
            band = sig[band_idx * _ROWS_PER_BAND : (band_idx + 1) * _ROWS_PER_BAND]
            for i in buckets.get((band_idx, band), ()):
                if abs(train_lengths[i] - length) <= 0.2 * max(
                    train_lengths[i], length, 1
                ):
                    candidates.add(i)
        is_dup = any(_jaccard(ngrams, train_ngrams[i]) >= threshold for i in candidates)
        if is_dup:
            removed += 1
        else:
            kept.append(rec)
    return kept, removed


# --------------------------------------------------------------------------- #
# Stratified split
# --------------------------------------------------------------------------- #
def stratified_split(
    records: list[dict],
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> dict[str, list[dict]]:
    """Stratified 70/15/15 split per label (small classes get >=1 val/test
    row when they have >=5 rows, else everything lands in train)."""
    rng = random.Random(seed)
    by_label: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_label[rec["label"]].append(rec)

    splits: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    for label, recs in sorted(by_label.items()):
        rng.shuffle(recs)
        n = len(recs)
        if n >= 5:
            n_test = max(1, round(n * test_ratio))
            n_val = max(1, round(n * val_ratio))
            n_val = min(n_val, n - n_test - 1)  # keep >=1 in train
        elif n >= 3:
            n_test, n_val = 1, 1
        else:
            n_test, n_val = 0, 0
        splits["test"].extend(recs[:n_test])
        splits["val"].extend(recs[n_test : n_test + n_val])
        splits["train"].extend(recs[n_test + n_val :])
    return splits


def oversample_train(splits: dict, floor: int, seed: int = 42) -> None:
    """Random oversampling of minority classes in the TRAIN split only.

    Repeats rows so every class has at least `floor` training rows
    (standard technique for imbalanced small datasets). Val/test are
    NEVER touched — metrics must reflect the real class balance.
    """
    if floor <= 0:
        return
    rng = random.Random(seed)
    train = splits["train"]
    by_label: dict[str, list[dict]] = defaultdict(list)
    for rec in train:
        by_label[rec["label"]].append(rec)
    balanced: list[dict] = []
    for label, recs in sorted(by_label.items()):
        if len(recs) < floor:
            recs = recs + [rng.choice(recs) for _ in range(floor - len(recs))]
        balanced.extend(recs)
    rng.shuffle(balanced)
    splits["train"] = balanced


def _detect_lang(text: str) -> str:
    return "hi" if any("ऀ" <= ch <= "ॿ" for ch in text) else "en"


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def _autodetect_local() -> dict[str, list[Path]]:
    """Find the Indian datasets the user dropped into ml/dataset/.

    Returns paths for: india_fraud (deduped by content), hinglish,
    phishing_corpus (directory of the email corpus).
    """
    found: dict[str, list[Path]] = {"india_fraud": [], "hinglish": [], "phishing_corpus": []}
    seen_hashes: set[str] = set()
    for path in sorted(DATASET_DIR.rglob("*.csv")):
        if path.name == "india_fraud_detection_FINAL.csv":
            # the same file was downloaded into two folders — dedupe by hash
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest not in seen_hashes:
                seen_hashes.add(digest)
                found["india_fraud"].append(path)
        elif path.name == "India_Cyber_Scam_Hinglish_Dataset.csv":
            found["hinglish"].append(path)
        elif "phishing-email-dataset" in str(path.parent).lower():
            parent = path.parent
            if parent not in found["phishing_corpus"]:
                found["phishing_corpus"].append(parent)
    return found


def build_dataset(
    uci_csv: str | None = None,
    phishing_csv: str | None = None,
    phishing_text_col: str = "text",
    phishing_label_col: str = "label",
    phishing_positive_label: str = "phishing",
    phishing_negative_label: str = "legitimate",
    max_public_per_class: int = 1200,
    max_not_scam: int = 1200,
    dedup_threshold: float = 0.95,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
    oversample_floor: int = 400,
) -> dict:
    print("Layer 1/4: hand-written Indian-context seeds ...")
    handwritten = load_handwritten()
    print(f"  {len(handwritten)} rows")

    print("Layer 2/4: India Fraud Detection dataset (india_fraud_detection_FINAL.csv) ...")
    local = _autodetect_local()
    india_fraud: list[dict] = []
    for path in local["india_fraud"]:
        rows = load_india_fraud(path)
        india_fraud.extend(rows)
        print(f"  {len(rows)} rows <- {path}")

    print("Layer 3/4: India Cyber Scam Hinglish dataset ...")
    hinglish: list[dict] = []
    for path in local["hinglish"]:
        rows = load_hinglish(path)
        hinglish.extend(rows)
        print(f"  {len(rows)} rows <- {path}")

    print("Layer 4/4: phishing-email corpus (CEAS_08 / Nazario / Nigerian / Ling / Enron) ...")
    corpus: list[dict] = []
    for directory in local["phishing_corpus"]:
        rows = load_phishing_corpus(directory)
        corpus.extend(rows)
        print(f"  {len(rows)} rows <- {directory}")

    if phishing_csv:
        extra = load_phishing_csv(
            phishing_csv, phishing_text_col, phishing_label_col,
            phishing_positive_label, phishing_negative_label,
        )
        corpus.extend(extra)
        print(f"  + {len(extra)} rows from --phishing-csv")

    print("Optional: UCI SMS Spam Collection ...")
    uci = load_uci(uci_csv)
    print(f"  {len(uci)} usable rows")

    records = handwritten + india_fraud + hinglish + corpus + uci

    # PII redaction on public rows only (hand-written seeds are already
    # fictional; keep them intact so they read naturally).
    records = [
        rec if rec["source"] == "handwritten" else {**rec, "text": redact_pii(rec["text"])}
        for rec in records
    ]

    # Cap public rows per class to keep the dataset balanced-ish
    # (hand-written seeds are always kept — they are the gold).
    # Public rows are SHUFFLED first (seeded, deterministic) so
    # the cap draws a diverse mix of sources and templates
    # instead of the first N rows of whichever source sorts
    # first — those are often template-heavy and would collapse
    # during deduplication.
    rng = random.Random(seed)
    per_label: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        per_label[rec["label"]].append(rec)
    capped: list[dict] = []
    for label, recs in per_label.items():
        gold = [r for r in recs if r["source"] == "handwritten"]
        public = [r for r in recs if r["source"] != "handwritten"]
        rng.shuffle(public)
        cap = max_not_scam if label == NOT_SCAM else max_public_per_class
        capped.extend(gold + public[: max(cap - len(gold), 0)])
    records = capped
    print(f"After capping: {dict(sorted(Counter(r['label'] for r in records).items()))}")

    print(f"Deduplicating (threshold={dedup_threshold}) ...")
    records, removed = dedupe(records, dedup_threshold)
    print(f"  removed {removed} duplicate/near-duplicate rows, {len(records)} remain")

    splits = stratified_split(records, val_ratio, test_ratio, seed)

    # Leakage PREVENTION: drop any val/test row that has a
    # near-duplicate (Jaccard >= 0.85) in the train split.
    # Template-generated data makes such pairs common; keeping
    # them would inflate test accuracy. Counts disclosed in
    # stats.json.
    audit = {}
    for split_name in ("val", "test"):
        splits[split_name], removed = remove_cross_split_near_dups(
            splits["train"], splits[split_name]
        )
        audit[split_name] = removed
    print(f"Cross-split leakage cleaning (@0.85): "
          f"val -{audit['val']} rows, test -{audit['test']} rows")

    if oversample_floor > 0:
        before = len(splits["train"])
        oversample_train(splits, oversample_floor, seed)
        print(f"Oversampled train split: {before} -> {len(splits['train'])} rows "
              f"(minority classes repeated to >= {oversample_floor})")

    # Write JSONL + assign split-scoped ids.
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    stats = {
        "splits": {},
        "dedup_removed": removed,
        "dedup_threshold": dedup_threshold,
        "cross_split_near_dups_removed_085": audit,
        "oversample_floor": oversample_floor,
        "sources": {
            "handwritten": len(handwritten),
            "india_fraud": len(india_fraud),
            "hinglish": len(hinglish),
            "phishing_corpus": len(corpus),
            "uci": len(uci),
        },
    }
    for split_name, recs in splits.items():
        out_path = DATASET_DIR / f"{split_name}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for idx, rec in enumerate(recs):
                row = {
                    "id": f"{split_name}_{idx:05d}",
                    "text": rec["text"],
                    "label": rec["label"],
                    "source": rec["source"],
                    "lang": _detect_lang(rec["text"]),
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        stats["splits"][split_name] = dict(Counter(r["label"] for r in recs))
        print(f"  {split_name}: {len(recs)} rows -> {out_path}")

    with open(DATASET_DIR / "stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uci-csv", default=None, help="Path to UCI SMS Spam Collection (TSV or CSV export)")
    parser.add_argument("--phishing-csv", default=None, help="Path to phishing-email CSV (Kaggle 'Phishing Emails')")
    parser.add_argument("--phishing-text-col", default="text")
    parser.add_argument("--phishing-label-col", default="label")
    parser.add_argument("--phishing-positive-label", default="phishing")
    parser.add_argument("--phishing-negative-label", default="legitimate")
    parser.add_argument("--max-public-per-class", type=int, default=1200)
    parser.add_argument("--max-not-scam", type=int, default=1200)
    parser.add_argument("--dedup-threshold", type=float, default=0.95)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--oversample-floor", type=int, default=400,
        help="Repeat minority classes in the TRAIN split up to this many rows (0 = off)",
    )
    args = parser.parse_args()

    stats = build_dataset(
        uci_csv=args.uci_csv,
        phishing_csv=args.phishing_csv,
        phishing_text_col=args.phishing_text_col,
        phishing_label_col=args.phishing_label_col,
        phishing_positive_label=args.phishing_positive_label,
        phishing_negative_label=args.phishing_negative_label,
        max_public_per_class=args.max_public_per_class,
        max_not_scam=args.max_not_scam,
        dedup_threshold=args.dedup_threshold,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
        oversample_floor=args.oversample_floor,
    )
    print("\nClass distribution per split:")
    for split_name, counts in stats["splits"].items():
        print(f"  {split_name}: {dict(counts)}")
    print("\nDone. Next: python train_classifier.py")


if __name__ == "__main__":
    main()
