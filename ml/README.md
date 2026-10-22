# Scam Shield — ML module

Standalone NLP + deep-learning package for scam detection
(UPI, SMS, WhatsApp, email). **No FastAPI, no AWS SDKs, no database
imports inside `ml/`** — the backend layer owns those.

## Layout

```
ml/
├── scamshield_ml/            # importable package
│   ├── labels.py             # label taxonomy (single source of truth)
│   ├── extraction.py         # regex entity extraction
│   ├── classifier.py         # fine-tuned DistilBERT + rule-based fallback
│   ├── embeddings.py         # sentence-transformer + cosine matching
│   └── pipeline.py           # analyze_message() -> ScamVerdict
├── prepare_dataset.py        # assembles dataset + stratified split
├── train_classifier.py       # fine-tunes DistilBERT (HF Trainer)
├── dataset/                  # handwritten seeds + generated splits
├── tests/                    # pytest suite
├── model/                    # fine-tuned weights (generated, gitignored)
├── runs/                     # training logs + loss curves (generated)
└── evaluation.md             # test-set report (generated)
```

## Quickstart

```bash
cd ml
pip install -r requirements.txt
pytest tests/ -v              # offline-safe: rule-based fallback + stub embedder
pytest tests/ -v -m "not slow"  # skip the model-download tests
```

## How the pipeline fits together

```
analyze_message(text)                       # pipeline.py — backend calls this
│
├── 1. extract_entities(text)               # extraction.py (regex, fast)
│       -> upi_ids, phone_numbers, urls, amounts
│
├── 2. classify(text)                       # classifier.py (DistilBERT, loaded once)
│       -> {"label", "confidence", "all_scores"}
│
├── 3. embed(text)                          # embeddings.py (all-MiniLM-L6-v2)
│       -> 384-dim vector
│       -> is_near_duplicate(...)?          # cosine vs. known scams (backend-supplied)
│
└── ScamVerdict                             # pydantic model, JSON-serialisable
        is_scam, scam_type, confidence, entities_found,
        embedding, explanation, near_duplicate, ...
```

The explanation is **template-based** (built from classifier + extractor
output) — deterministic and free, no LLM call at inference time.

### Design decisions (viva talking points)

- **Regex for extraction, ML for classification.** Extraction must be
  fast, deterministic and testable; classification is the fuzzy part.
- **Entity masking:** URLs and UPI IDs are masked before phone/amount
  extraction so `9876543210@ybl` is never double-reported as a phone.
- **Classifier loads once** (module singleton, `get_classifier()`), so
  per-request latency is inference-only.
- **Rule-based fallback:** if `ml/model/` is absent, a transparent
  keyword+entity baseline serves requests with the same interface, so
  the package works on a fresh clone and in CI. Swap by pointing
  `SCAM_MODEL_DIR` at trained weights.
- **Dependency injection** in `analyze_message(classifier=..., embedder=...)`
  keeps tests deterministic and offline.
- **Embeddings module is persistence-free:** it takes/returns vectors
  only; the backend owns the database (RDS/pgvector).

## Near-duplicate threshold (0.85)

With `all-MiniLM-L6-v2`, rewordings of the **same** scam score cosine
0.80–0.95; genuinely different scam messages usually score < 0.75.
0.85 sits in that gap and favours **precision** (fewer false
"known scam" flags). It is configurable everywhere
(`analyze_message(similarity_threshold=...)`,
`is_near_duplicate(threshold=...)`). Tune it on labelled
near-duplicate pairs of your own.

## Dataset (4 layers)

`python prepare_dataset.py` assembles and splits it automatically:

| Layer | Source | Rows used | Maps to |
|---|---|---|---|
| 1. Hand-written seeds | `dataset/handwritten/*.jsonl` | 132 | all 6 labels (the gold) |
| 2. India Fraud Detection | `dataset/archive/india_fraud_detection_FINAL.csv` (Kaggle) | 3,200 → capped | Echallan/Courier/Electricity/Digital_Arrest → `impersonation`; KYC_Suspension/Tax_Refund → `phishing`; Lottery → `fake_prize`; Job → `investment_fraud`; `*_Legitimate` → `not_scam` |
| 3. Cyber Scam Hinglish | `dataset/cyber scam hinglish/India_Cyber_Scam_Hinglish_Dataset.csv` (Kaggle) | 10,000 → capped | police_digital_arrest/police_blackmail/amazon/relative → `impersonation`; bank_kyc/aadhaar → `phishing`; lottery → `fake_prize`; label 0 → `not_scam` |
| 4. Phishing email corpus | `dataset/phishing dataset/Phishing-Email-Dataset-main/` | CEAS_08 + Nazario + Nigerian_Fraud + PhishingEmailData → `phishing`; Ling (label 1/0) → `phishing`/`not_scam`; Enron → `not_scam` |

Optional: `--uci-csv` adds the UCI SMS Spam Collection (auto-downloads
with the `datasets` library otherwise).

**Category-mapping rationale (viva):** a message gets the scammer's
*primary goal* — a fake challan *poses as traffic police* →
`impersonation`; a KYC-suspension lures *credentials/OTP* → `phishing`.

**Cleaning pipeline:**
1. PII redaction on all public rows (phones → `[PHONE]`, UPI IDs →
   `[UPI]`, URLs → `[URL]`, amounts → `[AMOUNT]`).
2. Per-class caps (1,200 public rows/class; hand-written seeds always
   kept), drawn from a **seeded shuffle** so the cap gets a diverse
   mix of sources/templates.
3. **Near-duplicate removal**: exact duplicates via a set, then
   candidates via **MinHash + LSH banding** (16 permutations, 4 bands
   of 4), verified with exact 3-gram Jaccard at **0.95**. The public
   data is template-generated, so a lower threshold would collapse
   legitimately distinct rows.
4. **Stratified 70/15/15 split** per label.
5. **Leakage prevention**: any val/test row with a ≥0.85 near-duplicate
   in train is *dropped* (counts printed + saved to `stats.json`).
6. **Random oversampling** of the train split only (minority classes
   repeated to ≥400 rows) — val/test keep the real class balance.

Final dataset: **~3,400 unique rows** → train 3,207 (oversampled),
val 453, test 449.

## Retraining

```bash
cd ml

# 1. Assemble dataset + stratified split (auto-detects the Kaggle
#    datasets you dropped into ml/dataset/)
python prepare_dataset.py

# 2. Fine-tune DistilBERT (Trainer API, early stopping on val loss)
python train_classifier.py
#    smoke test: python train_classifier.py --epochs 1 --max-examples 200

# 3. Upload weights for the backend (run from a shell — ml/ has no AWS imports)
aws s3 cp ml/model s3://<bucket>/scam-shield/model/ --recursive
```

Training defaults (small-dataset regime): lr 2e-5, batch 16, 4 epochs,
warmup 10%, weight decay 0.01, early stopping on validation loss
(patience 2), best checkpoint kept. Note: the first run downloads
`distilbert-base-uncased` (~268 MB) from HuggingFace — needs internet
once.

### Expanding the dataset

Add Indian-context examples to `dataset/handwritten/*.jsonl`:

```json
{"text": "Aapka SBI account block ho gaya. KYC update karein: bit.ly/kyc-sbi", "label": "phishing"}
```

Priority order for new data (current weakest classes):
`impersonation`, `loan_scam` — public datasets barely cover these
in Indian context.

## API surface

```python
from scamshield_ml import analyze_message, extract_entities, classify, embed

verdict = analyze_message("Congrats! You won Rs. 50,000. Pay Rs. 500 to fraud123@okaxis")
verdict.is_scam          # True
verdict.scam_type        # "fake_prize"
verdict.entities_found   # {"upi_ids": [...], "phone_numbers": [...], "urls": [...], ...}
verdict.embedding        # list[float], length 384
verdict.explanation      # human-readable string

entities = extract_entities(text)   # dict, no model load
result = classify(text)             # {"label", "confidence", "all_scores"}
vector = embed(text)                # np.ndarray, shape (384,)
```

## Requirements

Python 3.10+. Core: `numpy`, `pydantic`, `torch`, `transformers`,
`sentence-transformers`, `pytest`. Optional for convenience:
`matplotlib` (loss-curve PNGs), `datasets` (auto-download of the
UCI SMS Spam Collection). See `requirements.txt`.
