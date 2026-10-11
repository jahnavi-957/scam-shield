# scamshield_core

Shared Scam Shield analysis pipeline. Both the text path and the screenshot/worker path must call the same analysis logic.

Contents will be introduced in **M2 — Detection engine**:

- `redaction/` — PII redaction
- `entities/` — entity extraction (URL, UPI ID, phone, organization)
- `rules/` — explainable rule engine
- `reputation/` — scam-graph reputation lookups
- `similarity/` — embedding similarity (pgvector)
- `scoring/` — explainable risk scoring
- `explanation/` — optional Bedrock-based human explanation (M9)

No code here yet.