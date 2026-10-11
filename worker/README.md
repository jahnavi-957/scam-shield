# worker

Async consumer for the screenshot pipeline: S3 event → SQS → worker → OCR → scamshield_core analysis → RDS.

Will be populated in **M6 — Screenshot pipeline**. Until then the worker is deliberately not implemented; M1–M5 keep a single backend container.