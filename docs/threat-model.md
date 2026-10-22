# Threat Model

Structured using STRIDE per component. This is a living document — each milestone adds detail (especially M6 uploads and M11 hardening). Threats here are listed with the control that already exists or the milestone that will add it.

## 1. Assets worth defending

| Asset | Why it matters |
|---|---|
| Victim-submitted message content | Contains potential PII; must be minimized and handled carefully |
| Submitted screenshots | PII-rich images; private bucket, short retention |
| Scam intelligence graph (RDS) | Integrity: poisoned data degrades everyone's verdicts |
| Upload channel (S3 presigned URLs) | Abuse → storage cost + storage of malware |
| Queue (SQS) / worker | Availability of async pipeline |
| LLM explanation (optional, M9) | Prompt injection via untrusted message text |
| AWS account & roles | Busting the $100 budget / data breach |

## 2. STRIDE table

| # | Threat | STRIDE type | Mitigation | When |
|---|---|---|---|---|
| T1 | Attacker submits arbitrary/huge text or floods the API | DoS | Request-size limits; rate limiting | M1 basics / M11 rate limiting |
| T2 | Attacker mass-reports a legitimate entity to poison reputation | Tampering / spoofing | Unique reporter counts, duplicate-report detection, allowlists, wording "reported by X users"; campaign metric shared across entities | M9, schema already implies reporter identity (M2 adds report origin fields) |
| T3 | Message content contains a URL that we fetch → SSRF / internal-network scan | Elevation / information disclosure | **Never fetch user-submitted URLs.** Analyze as strings only | Rule set as a hard rule from M1 (development convention) |
| T4 | Malicious image upload (oversized, wrong type, decompression bomb) | DoS / malware | Size limit, content-type allowlist, dimension limits, image validation, private S3, short retention, deletion after processing | M6 |
| T5 | SQS duplicate delivery → duplicate reports/analysis | Tampering | Idempotent worker keyed on the report/upload id; visibility timeout > processing time | M6 |
| T6 | Worker redelivery after crash → partial writes | Tampering | Idempotency + atomic DB writes; retries with backoff; DLQ captures poison messages | M6 |
| T7 | DB reachable from the internet | Information disclosure / tampering | Security groups: only app SG can reach DB SG on 5432; DB in private subnets | M3/M4 |
| T8 | AWS credentials leaked / hard-coded | Spoofing / information disclosure | IAM roles everywhere, no access keys in code, SSM for secrets, `.gitignore` for `.env`, secret scanning discipline | M4, M11 |
| T9 | Over-provisioned IAM role used as pivot | Elevation | Least privilege per role; principal scoping; IAM Access Analyzer review | M4/M11 |
| T10 | Scam message text is passed to an LLM and the LLM obeys instructions inside it | Elevation / tampering | Untrusted text is *data*: strict structured prompt, message wrapped in delimiters, length limits, timeout, template fallback; LLM explains, never decides | M9 |
| T11 | Identifiers (UPI/phone) stored openly and deanonymized | Information disclosure | Store only what analysis needs; redaction minimises victim PII; HMAC + SSM pepper for any sensitive hashing (raw store is acceptable only for scam-side identifiers with clear doc) | M2 / M11 privacy review |
| T12 | S3 bucket becomes public / signed upload abused | Information disclosure / cost | Presigned write-only URLs, bucket policy denies public access, validation on the backend too | M6 |
| T13 | Logs contain message content or secrets | Information disclosure | Structured logging with PII redaction; never log secrets or full message bodies by default | M2/M8 |

## 3. Trust boundaries

```
[Internet browsers]            untrusted
        ▼ (HTTPS, M5; localhost dev only now)
[ALB]                          boundary: validates TLS, forwards to app SG only
        ▼
[EC2 app containers]           processes untrusted input — input treated as data
        ▼ (app SG → db SG, port 5432)
[RDS]                          most-protected zone: no internet route, no admin console exposure
```

Critical rule throughout: **everything arriving from a browser is untrusted input**, including the "scam message" whose content we classify. The system's job is to analyze it, never to follow it.

## 4. Development-time conventions (in force from M1)

1. Do not visit URLs found inside submitted messages.
2. No credentials in code, logs, or git history (`git log` is checked during reviews).
3. Dev-only local defaults are clearly labelled and never reused on AWS.
4. Upload validation is implemented on the backend, not just the client.

## 5. Residual risks (accepted, documented)

- Local API now has an in-process per-IP analysis limiter and request-size
  enforcement. A shared edge limiter is still required before multi-worker or
  public deployment.
- No authentication yet → the local skeleton is single-user; auth design lands with the public milestone (M5+).
- Legacy banking/OTP messages can be misclassified as scam until classifier evaluation (M2) tunes thresholds.
