# Architecture Overview

Target architecture per the master spec. The AWS pieces are **not** built yet — M1 only implements the part inside the box marked "local development". This document states where each component will live so later milestones slot into a known layout.

## 1. High-level vision

```
                    Internet
                       │
                       ▼
                ┌─────────────┐
                │  ALB (HTTPS) │   M5 (on during demo/tests only — cost)
                └──────┬──────┘
                       │
         ┌─────────────▼─────────────┐
         │  EC2 instance — Docker    │   M5
         │  ┌─────────────────────┐  │
         │  │ frontend (React)    │  │
         │  ├─────────────────────┤  │
         │  │ backend (FastAPI)   │  │
         │  ├─────────────────────┤  │
         │  │ worker (screenshot) │  │   M6
         │  └─────────────────────┘  │
         └─────────────┬─────────────┘
                       │ private subnets
         ┌─────────────▼─────────────┐
         │  RDS PostgreSQL + pgvector │   M4  (never public)
         └───────────────────────────┘
```

### Screenshot pipeline (M6)
```
Frontend ──presigned S3 upload──▶ S3 (private) ──event──▶ SQS ──▶ Worker
                                                                   │
                                                   OCR → scamshield_core → RDS
```

### Observability / secrets (M8, M4)
```
App ─▶ CloudWatch Logs + Metrics ─▶ Alarms ─▶ SNS
EC2/Worker ─▶ IAM role ─▶ SSM Parameter Store (secrets/config)
```

## 2. Components and responsibilities

| Component | Role | Where it lives | Milestone |
|---|---|---|---|
| frontend | Submit text, upload screenshots, poll status | `frontend/`, image `scamshield-frontend` | M1 |
| backend | HTTP API, submissions, analysis orchestration | `backend/`, image `scamshield-backend` | M1 |
| scamshield_core | Shared analysis pipeline (redaction → entities → rules → reputation → similarity → ML → scoring → explanation) | `scamshield_core/` — imported by both backend and worker | M2 |
| worker | Consume SQS screenshot tasks, run OCR + analysis | `worker/`, image `scamshield-worker` | M6 |
| db | Reports, entities, graph links, verdicts, embeddings | RDS PostgreSQL + pgvector (local: compose `db`) | M1 local |
| ml | Dataset, training, evaluation artifacts | `ml/` | M2 |
| infra | Terraform definitions | `infra/terraform/` | M3 |

## 3. Data model (logical scam graph)

Relational graph, not Neptune. Strong identifiers (URL, UPI ID, phone number, account-like) are **entities** and act as graph links; amounts/organization/category are attributes until deliberately promoted.

```
reports  ──◀   report_entities   ▶──  entities
   │                                    │
   └── verdicts                  patterns (rule detections → evidence)
```

Report 101 and Report 102 sharing a UPI ID/URL are linked *through* the entity table — that is the graph.

## 4. Request flows

### Text report (synchronous, M2 completes this)
```
POST /reports (text)
  → redact → normalize → extract entities → rules
  → reputation lookup → embedding similarity → ML classifier
  → risk scoring → evidence → verdict
  → persist (reports, entities, report_entities, verdicts)
  → response {verdict, risk_score, evidence}
```

### Screenshot report (asynchronous, M6)
```
POST /reports/screenshots → presigned URL → upload to S3
  → SQS message → worker (idempotent) → OCR
  → same scamshield_core pipeline → RDS → status completed/failed
GET /reports/{id} → status + result
```

### Reputation/campaign path (M2/M9)
```
identifier found again → increase report count for entity
  → MaxReportsPerEntity2h metric → CloudWatch alarm → SNS
```

## 5. Key architectural decisions (see ADR 0001)

1. **Python 3.12 pinned everywhere** (host 3.14 is too new for the ML wheel ecosystem).
2. **`pgvector/pgvector:pg16`** local image — the stock `postgres` image lacks pgvector.
3. **Sync SQLAlchemy 2 + psycopg3** to start — fewer moving parts to learn; revisit only if profiling says async is needed.
4. **Alembic** migrations from day one because the schema will evolve every milestone.
5. **Docker Compose for local parity** — containers locally ≈ containers on EC2, so deployment later is "same artifact, bigger machine".

## 6. Cost posture (summary — full detail in `docs/cost.md`)

- No NAT Gateway (private instances route inbound only; outbound needs visited at M3+).
- No Multi-AZ RDS. Single-AZ, smallest allowed instance.
- ALB created only during deployment/testing windows, then destroyed.
- Everything teardown-able; a teardown runbook is a final milestone deliverable.

## 7. What M1 delivers locally (nothing on AWS)

```
frontend :5173  ──HTTP/CORS──▶  backend :8000  ──▶  db :5432 (compose network)
```

- `/health` endpoint proving backend + DB reachability.
- Schema + Alembic migrations in place so M2 can build the pipeline against real tables.
- Frontend page that renders backend/DB status.