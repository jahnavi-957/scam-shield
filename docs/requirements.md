# Requirements

Distilled from the master project context. This file is the *contract* — what the system must do — and every milestone maps back to it.

## 1. Purpose

Scam Shield is a platform for detecting and **collectively** identifying scams from suspicious text messages, UPI/payment scam messages, phishing links, loan/investment offers, impersonation attempts and screenshots. The differentiator is a shared **scam intelligence graph**: entities (URLs, UPI IDs, phone numbers) extracted from one report later help classify or contextualise other reports.

The system must distinguish clearly between:
- **reported** (someone reported it)
- **reputation** (X reporters share this identifier — an evidence signal, not proof)
- **model prediction** (statistical classification)
- **confirmed** (never claimed from reports alone)

## 2. Functional requirements

### 2.1 Text report (synchronous)
1. Receive a submitted message.
2. Redact unnecessary victim PII.
3. Normalize the message.
4. Extract entities (URL, domain, UPI ID, phone number, organization, …).
5. Run the explainable rule engine (urgency, KYC claims, shorteners, guaranteed returns, …).
6. Run ML classification (TF-IDF + Logistic Regression baseline; precision/recall/F1, confusion matrix, threshold calibration, focus on not flagging legitimate banking/OTP messages).
7. Search the scam graph for previously reported identifiers (report reputation).
8. Search semantic similarity against previous messages (pgvector embeddings).
9. Compute an explainable, non-double-counted risk score (content evidence vs network/reputation evidence).
10. Persist the report, verdict and entity graph.
11. Return a verdict with evidence.

### 2.2 Screenshot report (asynchronous)
1. User uploads an image via a **presigned** S3 URL (bucket stays private).
2. S3 object created → SQS message → worker consumes it (at-least-once → idempotent worker, visibility timeout, retries, DLQ).
3. Worker runs OCR, then feeds the extracted text through the **same** analysis pipeline (`scamshield_core`).
4. Report status transitions `submitted → processing → completed | failed`.
5. Client polls `GET /reports/{id}` for status/results.

### 2.3 Shared intelligence
- Identifiers repeated across multiple reports are surfaced as reputation evidence and, eventually, campaign detection (M9) with `MaxReportsPerEntity2h` CloudWatch metric + SNS alert.
- Anti-poisoning: unique reporter counts, rate limiting, duplicate-report detection, legitimate-domain allowlists, wording "reported by X users" (never "confirmed").

### 2.4 Verification requirements
- Every milestone ships the tests appropriate to it (unit: extraction/normalization/rules/scoring; integration: API→Postgres; e2e: submit→analysis→verdict→DB; screen- shot: upload→OCR→analysis→completed; later AWS connectivity tests).

## 3. Non-functional requirements

### 3.1 Cloud architecture (faculty requirements)
- Custom VPC: public subnets (ALB), private app subnets (EC2), private DB subnets (RDS). IGW, route tables, security groups. **RDS not internet-reachable.**
- Backend on EC2/containers — a fully serverless architecture is **not** allowed.
- Managed relational DB: RDS PostgreSQL + pgvector (single-AZ acceptable).
- S3 with a genuine purpose (screenshots), private.
- IAM roles + least privilege; no hard-coded AWS keys.
- Secrets/config in SSM Parameter Store (not env files) once we reach AWS.
- CloudWatch Logs/Metrics/Alarms/Dashboard with ≥1 meaningful app alarm; SNS for alerts.
- AWS Budget alerts. Design target ≈ **$100 team credits**. No always-on NAT Gateway, no Multi-AZ, small instances, teardown between sessions.

### 3.2 Security
- Never fetch URLs submitted inside scam messages (SSRF risk) — analyze them as strings/identifiers.
- Validate uploads: size limit, content type allowlist, dimension limits; short retention, deletion after processing.
- Defensive LLM usage (optional, late): untrusted text = data, never instructions; strict prompt, length limit, timeout, template fallback.
- PII minimized; sensitive identifier hashing uses HMAC + SSM pepper if ever needed.

### 3.3 Reliability
- Idempotent worker (SQS at-least-once), visibility timeout > processing time, DLQ/redrive.
- ASG min=1 / desired=1 / max=2 for failure demonstration; do not run two instances continuously.

### 3.4 Observability
- Structured logs; metrics: request count, latency, analysis failures, SQS depth/DLQ, 5xx, scam detections, reports-per-entity.

## 4. Milestone mapping (from master spec)

| Milestone | Deliverable | Requirement refs |
|---|---|---|
| M0 | Foundation (this doc set) | all |
| M1 | Local skeleton: React + FastAPI + PostgreSQL + Compose + schema/migrations | 3.x local dev |
| M2 | Detection engine (redaction, entities, rules, ML, similarity, scoring) | 2.1.2–2.1.9 |
| M3 | AWS networking (VPC/subnets/route tables/IGW/SGs) | 3.1 |
| M4 | RDS + IAM + SSM · Session Manager | 3.1 |
| M5 | EC2 + Docker + ALB + HTTPS | 3.1 |
| M6 | Screenshot pipeline (S3/SQS/worker/OCR/DLQ) | 2.2 |
| M7 | ASG + health checks + failure testing | 3.3 |
| M8 | CloudWatch metrics/dashboard/alarms/SNS | 3.4 |
| M9 | Campaign detection, unique reporters, generous-time reputation, optional Bedrock explanation | 2.3 |
| M10 | Terraform + GitHub Actions + OIDC | 3.1 |
| M11 | Security hardening (IAM review, CloudTrail, retention, rate limiting) | 3.2 |
| M12 | Finalization: tests, cost evidence, diagrams, demo, teardown runbook | — |

## 5. Out of scope for M0/M1
- AWS resources of any kind.
- ML models, rules, embeddings (M2).
- Upload/S3/SQS/OCR (M6).
- Authentication and multi-user authorization remain out of scope for the
  local single-user stack. Local analysis rate limiting and request-size
  enforcement are implemented; shared/public rate limiting is a deployment
  requirement.

## 6. Definition of done for the whole project
A user submits a scam message and Scam Shield: redacts → normalizes → extracts entities → rules → ML → graph lookup → similarity → explainable score → persists report/verdict → returns verdict + evidence → updates identifier reputation → detects repeated campaign activity → emits metrics → raises SNS alert at threshold. Screenshots follow the async path to the same result.
