# Scam Shield — Implementation Status

*Last updated: 2026-10-11 · Repo-side state verified against the git history and working tree. ML external work noted, not merged.*

## Overall Status

The project is at **M1 — Local Skeleton** (plus the M0 foundation it needs). A full local development environment runs via Docker Compose: FastAPI backend, React frontend, and PostgreSQL + pgvector, with schema migrations and verified tests.

**No AWS resources have been created. No AWS credentials exist anywhere in the repository.** AWS work starts at M3 by plan.

| Milestone | Area | Status |
|---|---|---|
| M0 | Foundation (docs, repo, cost plan, threat model) | **Done** |
| M1 | Local skeleton (React + FastAPI + PostgreSQL + Compose + schema/migrations) | **Done, verified** |
| M2 | Detection engine (`scamshield_core`, rules, ML, similarity, scoring) | **Partial — ML in progress externally** (see §6) |
| M3 | AWS networking (VPC/subnets/route tables/IGW/SGs) | Not started |
| M4 | RDS + IAM + SSM Parameter Store | Not started |
| M5 | EC2 + Docker + ALB + HTTPS | Not started |
| M6 | Screenshot pipeline (S3/SQS/worker/OCR/DLQ) | Not started |
| M7 | Auto scaling + failure testing | Not started |
| M8 | CloudWatch metrics/dashboard/alarms/SNS | Not started |
| M9 | Campaign detection + optional Bedrock explanation | Not started |
| M10 | Terraform + GitHub Actions + OIDC | Not started |
| M11 | Security hardening | Not started |
| M12 | Finalization (tests, demo, cost evidence, teardown) | Not started |

## Directory Breakdown & Progress

### 1. Backend (`backend/`)
**Status:** Skeleton implemented and verified.
**Stack:** FastAPI (Python 3.12 pinned in `python:3.12-slim`), sync SQLAlchemy 2, psycopg v3, Alembic, pydantic-settings.

- `app/main.py` — FastAPI entrypoint, CORS scoped to `http://localhost:5173`, mounted routers.
- `app/api/health.py` — `GET /health`: returns `200 {"status":"ok","database":"connected"}` when the DB answers, `503 degraded` otherwise. Used by the container healthcheck.
- `app/core/config.py` — environment-driven settings (`DATABASE_URL`, `CORS_ORIGINS`); no secrets in code.
- `app/db/` — declarative `Base`, session factory + `get_db` dependency, and the ORM models.
- `app/schemas/` — Pydantic response models.
- `alembic/` — migration environment wired to app settings; one migration applied (**`0001`**).
- `tests/` — 2 unit tests (fake DB) + 1 integration test against the real compose Postgres. **Result: `3 passed`** (run inside the container, Python 3.12.15).
- `scripts/start.sh` — container start script: `alembic upgrade head` then uvicorn.

### 2. Frontend (`frontend/`)
**Status:** Skeleton implemented.
**Stack:** React 18, Vite 5, TypeScript (strict).

- `src/App.tsx` — renders a status card from the backend `/health` call (loading / error / ready states).
- `src/api.ts` — small typed client; API base from `VITE_API_URL`, default `http://localhost:8000`.
- Dev server on `:5173`, `host: true` so Vite is reachable from the host browser; hot reload via bind mount.

### 3. Database (`db` service)
**Status:** Running locally, schema applied, connection verified.
**Stack:** `pgvector/pgvector:pg16` (PostgreSQL 16 with the `vector` extension built in).

- **pgvector 0.8.7** extension enabled by migration `0001` (vector columns arrive in M2).
- Alembic migration `0001` created the scam graph tables:

| Table | Purpose |
|---|---|
| `reports` | One row per submitted message/screenshot; status (`submitted/processing/completed/failed`), source type, risk score |
| `entities` | Scam-side identifiers (URL, UPI ID, phone, …) — the graph *nodes* |
| `report_entities` | Link table report ↔ entity — the graph *edges* |
| `patterns` | Rule-engine detection catalog (populated in M2) |
| `verdicts` | One verdict per report; `scam_likely/suspicious/legitimate/unverified` |

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
**Status:** In progress, externally — not yet merged into this repo.
- A teammate is developing the ML baseline separately (TF-IDF + Logistic Regression classifier with precision/recall/F1 evaluation, per master spec §12). That work is **still on their machine** and has not been reviewed, merged, or committed here — `ml/` currently holds only the placeholder `README.md`.
- Integration checklist before the repo can call this "done": (1) work lands in `ml/` (data/training/evaluation/models) on a feature branch, (2) dependencies pinned in a lockable file compatible with our **Python 3.12** constraint (ADR 0001), (3) evaluation report including precision/recall/F1, confusion matrix, false positives/negatives, and threshold calibration — especially misclassification of legitimate banking/OTP messages, (4) dataset limitations documented (Indian English/Hinglish/Hindi coverage), (5) status document updated. No performance claims are accepted without that report.

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

## Verification Evidence (from the last full run)

| Check | Result |
|---|---|
| `docker compose config` | valid |
| `docker compose up -d --build` | 3/3 containers, backend + db `healthy` |
| `GET http://localhost:8000/health` | `200 {"status":"ok","service":"scamshield-backend","database":"connected"}` |
| `GET http://localhost:5173` | 200 (Vite dev server up) |
| `GET http://localhost:8000/docs` | 200 (Swagger UI) |
| CORS preflight (Origin `http://localhost:5173`) | `Access-Control-Allow-Origin: http://localhost:5173` |
| `pytest -v` (in-container) | `3 passed` |
| Migrations | `alembic_version = 0001`; 5 tables present |
| pgvector | `vector 0.8.7` enabled |

## Git History

7 commits on `main`, one logical unit each:

```
f02471f docs: add implementation status document
3c4bff9 fix: keep tests in backend image so pytest runs in-container
099d71b chore: add docker-compose local stack
0e6b259 feat: add Vite React frontend skeleton
03f3eea feat: add FastAPI backend skeleton with health endpoint and scam graph schema
aea2989 docs: add M0 foundation (requirements, architecture, threat model, cost, ADR)
743486e chore: initialise repository with gitignore, README and module placeholders
```

**Note:** the ML work is being developed outside this repo (not on a branch). It must be merged in as its own feature branch with a `feat: ml ...` commit — never bundled into an unrelated commit.

## What Is Deliberately Not Implemented Yet

- No AWS resources, IaC, roles, or credentials of any kind.
- No analysis pipeline (rules/ML/embeddings) — but the tables it writes to already exist.
- No HTTP reports API — `GET /health` is the only endpoint; `POST /reports` arrives in M2.
- No auth, rate limiting, uploads, S3/SQS/OCR, or CloudWatch.
- ML baseline exists only externally (teammate's machine) — **nothing merged or verified**, and its performance is unclaimed until the evaluation report lands.
- Minor known warning: `TestClient`/httpx deprecation notice in test output (dependency-level, non-blocking).

## Next Steps (M2 — Detection Engine)

1. Build `scamshield_core`: PII redaction, normalization, entity extraction.
2. Explainable rule engine + `patterns` catalog seed.
3. Embedding similarity (`pgvector` columns) + ML baseline (TF-IDF / Logistic Regression) with evaluation.
4. Risk scoring that separates content vs network/reputation evidence.
5. `POST /reports` synchronous pipeline wiring the core into the API, storing reports/entities/verdicts.
6. Unit + integration tests for each stage.

Everything continues to run **locally for $0** until the local architecture is proven.