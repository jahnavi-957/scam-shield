# Scam Shield — Implementation Status

*Last updated: 2026-10-11 · Backend API and ML pipeline implemented and verified locally; AWS work not started.*

## Overall Status

The project is at **M1 skeleton + M2 detection engine (backend side)**. The local Docker Compose stack (FastAPI + React + PostgreSQL/pgvector) is in place, the `ml/` package ships a fine-tuned DistilBERT classifier and MiniLM embedder, and the FastAPI backend implements the full analysis API on top of them.

**No AWS resources have been created. No AWS credentials exist anywhere in the repository.** AWS work starts at M3 by plan.

| Milestone | Area | Status |
|---|---|---|
| M0 | Foundation (docs, repo, cost plan, threat model) | **Done** |
| M1 | Local skeleton (React + FastAPI + PostgreSQL + Compose + schema/migrations) | **Done, verified** |
| M2 | Detection engine — ML side (`ml/` package, trained weights, 100 tests) | **Done** |
| M2 | Detection engine — backend API (analyze, entities, alerting, S3, SSM, OCR) | **Done, unit-verified** (integration tests need the compose DB) |
| M3 | AWS networking (VPC/subnets/route tables/IGW/SGs) | Not started |
| M4 | RDS + IAM + SSM Parameter Store | Not started |
| M5 | EC2 + Docker + ALB + HTTPS | Not started |
| M6 | Screenshot pipeline (S3/SQS/worker/OCR/DLQ) | Not started (S3 + OCR server-side pieces already coded) |
| M7 | Auto scaling + failure testing | Not started |
| M8 | CloudWatch metrics/dashboard/alarms/SNS | Not started (SNS publish implemented) |
| M9 | Campaign detection + optional Bedrock explanation | Not started |
| M10 | Terraform + GitHub Actions + OIDC | Not started |
| M11 | Security hardening | Not started |
| M12 | Finalization (tests, demo, cost evidence, teardown) | Not started |

## Directory Breakdown & Progress

### 1. Backend (`backend/`)
**Status:** Analysis API implemented (the M2 detection-engine wiring).
**Stack:** FastAPI (Python 3.12 pinned in `python:3.12-slim`), sync SQLAlchemy 2, psycopg v3, Alembic, pydantic-settings, boto3 (S3/SNS/SSM), pgvector, pytesseract.

- `app/main.py` — FastAPI entrypoint, CORS scoped to `http://localhost:5173`, mounted routers, startup `bootstrap()` (SSM overlay when `SSM_ENABLED=true`).
- `app/api/` — `POST /analyze/text`, `POST /analyze/screenshot`, `GET /uploads/presigned-url`, `GET /entities/{value}`, `GET /health`, `GET /`.
- `app/ai.py` — lazy adapter around `scamshield_ml.analyze_message()`; heavy imports deferred to first request; any model failure becomes `AIPipelineError` → generic 500 (real error logged server-side).
- `app/core/config.py` — env-driven settings; `bootstrap()` overlays `/scam-shield/<env>/{database_url,s3_bucket,sns_topic_arn}` from SSM (decrypted) when enabled.
- `app/db/` — declarative `Base`, session factory + `get_db`, repository layer (save/find, idempotent entities, windowed report counts, pgvector cosine search), retry with exponential backoff on transient `OperationalError`.
- `app/services/` — `analysis.py` (orchestration: persist → classify → embed → near-duplicate check → entity tracking → alert evaluation), `alerts.py` (SNS publish, `should_alert` threshold rule with cooldown), `storage.py` (15-min presigned S3 PUT URLs), `ocr.py` (Tesseract, `OCR_ENGINE=textract` switchable), `model_loader.py` (one-time weight download from S3, rule-based fallback).
- `alembic/` — two migrations, single head `0002`: `0001` M1 scam-graph schema, `0002` analysis schema (drops the M1 tables, creates `messages`, `entities`, `analysis_results` with `vector(384)`, `message_entities`; enables the `vector` extension).
- `tests/` — **30 tests: 10 unit pass, 20 integration skip cleanly** when the compose Postgres is unreachable (they run against it via `docker compose up -d db`). The AI pipeline is always mocked in tests (real model loading is far too slow); the adapter itself is covered by the ml package's own suite.
- `scripts/start.sh` — container start: `alembic upgrade head` → S3 model download → gunicorn, 1 worker (each worker holds the model in RAM).
- `Dockerfile` — multi-stage, CPU-only PyTorch wheel (~200 MB, not the ~2 GB CUDA build), tesseract, runs unprivileged as `appuser`.

### 2. Frontend (`frontend/`)
**Status:** Skeleton implemented.
**Stack:** React 18, Vite 5, TypeScript (strict).

- `src/App.tsx` — renders a status card from the backend `/health` call (loading / error / ready states).
- `src/api.ts` — small typed client; API base from `VITE_API_URL`, default `http://localhost:8000`.
- Dev server on `:5173`, `host: true` so Vite is reachable from the host browser; hot reload via bind mount.

### 3. Database (`db` service)
**Status:** Running locally, schema applied, connection verified.
**Stack:** `pgvector/pgvector:pg16` (PostgreSQL 16 with the `vector` extension built in).

- **pgvector** extension enabled by migration `0001`; `0002` stores 384-dim MiniLM embeddings in `analysis_results.embedding` with an IVFFlat index (`lists = 16`).
- Migration `0002` (head) — the analysis schema:

| Table | Purpose |
|---|---|
| `messages` | One row per submitted message (raw text, source `text`/`screenshot`, created_at) |
| `analysis_results` | Verdict per message: scam_type, confidence, is_scam, explanation, embedding |
| `entities` | Graph nodes: entity_type (`upi`/`phone`/`url`), normalized_value, lifetime report_count, last_alert_at (cooldown) |
| `message_entities` | Graph edges: message ↔ entity links |

- DB is **not** exposed publicly: only `127.0.0.1:5433` on the host, port 5432 stays internal to the compose network.

### 4. Docker Compose (`docker-compose.yml`)
**Status:** Working.
- Services `db`, `backend`, `frontend` with healthchecks and `depends_on` (backend waits for healthy DB).
- Backend container applies migrations on every start.
- Named volumes: `pgdata`, `frontend_node_modules`.
- Verified: all three containers `Up (healthy)`, health endpoint 200.

### 5. Infrastructure (`infra/`)
**Status:** Not started. Placeholder `README.md` only. Terraform (VPC → RDS → EC2/ALB → S3/SQS …) is generated from **M3** onward — never before the local app is proven to work.

### 6. Machine Learning (`ml/`)
**Status:** Done — merged into the repo.
- `scamshield_ml` package: `classifier.py` (DistilBERT-base-uncased fine-tuned on the labeled dataset), `embeddings.py` (MiniLM, 384-dim), `extraction.py` (UPI IDs, +91-normalised phones, URLs incl. shorteners, INR amounts — with masking so extractors don't feed each other), `labels.py`, `pipeline.py` (`analyze_message(text) -> ScamVerdict`).
- Trained weights in `ml/model/`; `finetune_distilbert.py` reproduces them; evaluation with precision/recall/F1 and confusion matrix in `ml/runs/`.
- **Backend integration verified:** `analyze_message`'s `ScamVerdict` fields (`is_scam`, `scam_type`, `confidence`, `explanation`, `embedding`, `entities_found`) match the backend adapter (`app/ai.py`) exactly; entity dict keys (`upi_ids`, `phone_numbers`, `urls`) match the analysis service.
- **Tests: `100 passed, 2 skipped`** (45.6 s).
- If model weights are unavailable at runtime, the pipeline falls back to the rule-based classifier (degraded, not down).

### 7. Scam Shield Core Pipeline (`scamshield_core/`)
**Status:** Not started. Placeholder directory. Will hold the shared analysis pipeline (redaction → entities → rules → reputation → similarity → scoring → explanation) that both the text path and the worker path will import. Target: **M2**.

### 8. Worker (`worker/`)
**Status:** Not started. Placeholder directory. Async screenshot consumer (S3 event → SQS → OCR → analysis) arrives in **M6**.

### 9. Documentation (`docs/`)
**Status:** M0 set complete.
- `requirements.md` — functional/non-functional contract per master spec.
- `architecture/overview.md` — target architecture, data flows, component map.
- `threat-model.md` — STRIDE table with controls and milestone owners.
- `cost.md` — $100 budget plan, per-resource estimates, deliberately-avoided list.
- `adr/0001-local-stack-decisions.md` — Python 3.12 pin, pgvector image, sync SQLAlchemy, Alembic-first.

## Verification Evidence

**2026-10-11 (this update, Windows host):**

| Check | Result |
|---|---|
| `python -m py_compile` (all backend modules) | OK |
| Backend `pytest` | **10 passed, 20 skipped, 0 failed** (integration tests skip without the compose DB) |
| ML `pytest` (`ml/tests`) | **100 passed, 2 skipped** (45.6 s) |
| `alembic heads` / `alembic history` | single head `0002`, chain `<base> -> 0001 -> 0002` |
| Backend ↔ ml contract (`ScamVerdict` fields, entity keys) | matches `app/ai.py` / `app/services/analysis.py` |

**Earlier M1 run (compose stack, from the previous session):**

| Check | Result |
|---|---|
| `docker compose config` | valid |
| `docker compose up -d --build` | 3/3 containers, backend + db `healthy` |
| `GET http://localhost:8000/health` | `200 {"status":"ok","service":"scamshield-backend","database":"connected"}` |
| `GET http://localhost:5173` | 200 (Vite dev server up) |
| `GET http://localhost:8000/docs` | 200 (Swagger UI) |
| CORS preflight (Origin `http://localhost:5173`) | `Access-Control-Allow-Origin: http://localhost:5173` |
| Migrations | `alembic_version = 0001`; 5 tables present (superseded by `0002`) |
| pgvector | `vector 0.8.7` enabled |

> Not re-verified in this session: Docker Desktop is not running on the current machine, so the compose stack and the integration tests against live Postgres were not re-run here. Integration tests are written to skip (not fail) in that state.

## Git History

The repository currently sits on a single setup commit (`8d240c1 first commit to ensure everything is setup`); the working tree carries the M1 skeleton, the `ml/` pipeline, and the backend API described above. Logical per-feature commits (e.g. `feat: ml pipeline`, `feat: backend analysis API`) are pending — the repo is not a clean per-milestone history yet.

## What Is Deliberately Not Implemented Yet

- No AWS resources, IaC, roles, or credentials of any kind (`infra/` is a README placeholder; Terraform starts at M3).
- No frontend analysis UI — `frontend/src/api.ts` only calls `/health`; the analyze/entities/presigned-upload client functions are the natural next frontend task.
- No `scamshield_core` shared pipeline or async `worker/` (the synchronous backend path covers the same flow for now; the worker arrives in M6).
- No auth, rate limiting, SQS, or CloudWatch alarms.
- S3 lifecycle rules for uploaded screenshots are documented as Terraform's job (`backend/README.md`), not implemented.

## Next Steps

1. Frontend: extend `src/api.ts` with the analyze/entities/presigned-upload calls and wire them into `App.tsx`.
2. Run the integration suite against the compose Postgres (`docker compose up -d db`, then `pytest -m integration`) once Docker is available.
3. M3: Terraform for the VPC, then RDS/IAM/SSM (M4), EC2/ALB (M5).
4. M6: screenshot worker (S3 event → SQS → OCR → analysis) reusing `app/services/ocr.py` and `app/ai.py`.