# Scam Shield Dataset

## Schema (JSONL — one JSON object per line)

| Field    | Type   | Description                                                        |
|----------|--------|--------------------------------------------------------------------|
| `id`     | string | `"<split>_<index>"`, e.g. `train_00042` (assigned by the split)  |
| `text`   | string | The message text (SMS / WhatsApp / email body)                     |
| `label`  | string | One of the 6 labels below                                          |
| `source` | string | `handwritten` \| `uci` \| `phishing_emails`                        |
| `lang`   | string | `en` \| `hi` (Devanagari detection heuristic)                      |

Example:

```json
{"id": "train_00042", "text": "Congrats! You won Rs. 50,000...", "label": "fake_prize", "source": "handwritten", "lang": "en"}
```

## Label taxonomy (6 classes, single-label)

| Label             | Meaning                                                       |
|-------------------|---------------------------------------------------------------|
| `phishing`        | Credential theft via fake links / urgent verification         |
| `fake_prize`      | "You won" + upfront fee to claim                              |
| `loan_scam`       | Fake loan approval + processing fee                           |
| `impersonation`   | Posing as family / bank / police / boss                       |
| `investment_fraud`| Guaranteed high returns, crypto, trading, WFH schemes         |
| `not_scam`        | Legitimate messages                                           |

Boundary rule: one label per message = the scammer's **primary goal**.
A prize scam with a phishing link is labelled `fake_prize`.

## Sources (4 layers + optional)

1. **Hand-written seeds** (`handwritten/*.jsonl`) — Indian-context
   Hinglish/English examples. **The core of the dataset.** Add rows as
   `{"text": "...", "label": "phishing"}` to any `*.jsonl` here.
2. **India Fraud Detection** (`archive/india_fraud_detection_FINAL.csv`,
   Kaggle) — 3,200 rows, 16 categories × 200, balanced scam/legit.
   Category → label mapping is in `prepare_dataset.py`
   (`_INDIAN_FRAUD_MAP`).
3. **India Cyber Scam Hinglish** (`cyber scam hinglish/India_Cyber_Scam_Hinglish_Dataset.csv`,
   Kaggle) — 10,000 rows, Hinglish call/SMS scripts; `scam_category`
   → label mapping in `_HINGLISH_MAP`.
4. **Phishing email corpus** (`phishing dataset/Phishing-Email-Dataset-main/`) —
   CEAS_08, Nazario, Nigerian_Fraud, PhishingEmailData (all phishing),
   Ling (mixed), Enron (legit).
5. Optional: UCI SMS Spam Collection (`--uci-csv` or auto-download with
   the `datasets` library).

**Privacy:** all public rows are PII-redacted before being written
(phones → `[PHONE]`, UPI IDs → `[UPI]`, URLs → `[URL]`,
amounts → `[AMOUNT]`) using the package's own extractor.

**Deduplication:** exact duplicates removed instantly; near-duplicates
found with MinHash + LSH banding (16 perms, 4 bands of 4) and verified
with exact 3-gram Jaccard at 0.95 (the data is template-generated —
a lower threshold would collapse distinct rows).

**Leakage prevention:** stratified 70/15/15 split, then any val/test
row with a ≥0.85 near-duplicate in train is dropped (counts in
`stats.json`). The train split only is oversampled (minority classes
repeated to ≥400 rows).

## Suggested expansion (Kaggle / HuggingFace, India-specific)

- Kaggle "Spam detection dataset" (~7.5k SMS incl. Indian/Hinglish spam)
- Kaggle "Indian SMS Spam" collections
- Add WhatsApp forwards (text-only) and email bodies for domain coverage

**Known gap:** public data has almost no `loan_scam` examples in Indian
context — hand-written seeds carry that class (52 rows). Expand them
before relying on per-class `loan_scam` metrics; same for
`investment_fraud` (232 rows).
