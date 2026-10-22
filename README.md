# Scam Shield

AI-powered fraud detection platform for SMS, UPI, WhatsApp, and phishing scams built around a shared **scam intelligence graph**.

> **Current Status: integrated local stack configuration and security hardening implemented; AWS deployment remains deferred.**
> The `ml/` package provides the DistilBERT/MiniLM pipeline, and the FastAPI backend exposes text and screenshot (OCR) analysis, pgvector matching, entity tracking, presigned uploads, and SSM-backed production configuration. The local Compose stack uses Postgres/pgvector, MinIO and a mock SNS publisher. Docker/AWS end-to-end execution still requires a Docker-enabled environment.

---

## The Problem & Vision

Scam messages — fake payment requests, phishing links, prize scams, loan fraud, impersonation — are typically reported in isolation. The same scammer (using identical UPI IDs, phone numbers, or reworded messages) targets hundreds of victims before authorities or providers connect the dots.

Scam Shield solves this by creating a centralized, real-time **scam intelligence graph**:
1. **Ingests** suspicious messages and screenshots via API, email polling, or user upload.
2. **Extracts** high-risk entities (UPI IDs, phone numbers, phishing URLs, impersonated institutions).
3. **Classifies** messages with NLP/ML models to determine scam category and risk level.
4. **Matches** message semantics using vector embeddings (`pgvector`) against known scams to catch paraphrased variants.
5. **Updates** the shared intelligence graph, linking related reports and flagging high-frequency fraudulent entities.
6. **Alerts** stakeholders via CloudWatch and SNS when a fraud campaign crosses alert thresholds.

---

## Target Cloud Architecture

```
                    ┌─────────────────┐
                    │   EventBridge    │ (scheduled trigger)
                    │   + Lambda       │
                    └────────┬─────────┘
                             │ polls inbox
                             ▼
┌──────────┐        ┌─────────────────┐        ┌──────────┐
│ Frontend │───────▶│   EC2 (Docker)   │───────▶│   RDS    │
│ (React)  │  HTTP  │   FastAPI app    │  SQL   │PostgreSQL│
└──────────┘        │                  │        │+pgvector │
                    │  - Entity extract│        └──────────┘
                    │  - ML inference  │
                    │  - Graph queries │
                    └────────┬─────────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
             ┌─────┐    ┌─────────┐  ┌──────────┐
             │ S3  │    │CloudWatch│  │   SNS    │
             │(OCR │    │ (alarms) │  │ (alerts) │
             │input)│   └──────────┘  └──────────┘
             └─────┘
```

---

## Repository Layout

```
scam-shield/
├── backend/          FastAPI analysis API (SSM, S3, SNS, OCR, pgvector) + Alembic migrations
├── frontend/         React + Vite + TypeScript single-page app
├── scamshield_core/  Shared analysis pipeline (populated in M2)
├── worker/           Async screenshot worker (populated in M6)
├── ml/               Trained models (DistilBERT + MiniLM) and the scamshield_ml package
├── infra/            Terraform for AWS (populated in M3)
├── docs/             Requirements, architecture, threat model, cost, ADRs, status
├── scripts/          Developer helper scripts
└── tests/            Integration / e2e tests (added from M2)
```

Only files needed for the active milestone are populated, keeping the repository clean and modular.

---

## Run the whole app locally

### Prerequisites
- Docker Desktop (with WSL2 backend on Windows) **running**
- Git

Containers manage Python, Node, Postgres and MinIO dependencies internally, so
local runtimes are not required.

### 1. Create the one local configuration file

From the repository root:

```sh
cp .env.example .env
```

PowerShell equivalent:

```powershell
Copy-Item .env.example .env
```

`.env` is local-only and ignored by Git. It is the single source of truth for
the Compose database, API origin, MinIO endpoint/bucket and local SNS mock.
Do not use these development credentials or HTTP endpoints in AWS.

### 2. Start the complete stack
```sh
docker compose up -d --build
```

This starts Postgres + pgvector, MinIO, the bucket initializer, FastAPI and
the Vite frontend. The backend applies Alembic migrations before serving.

### 3. Service Endpoints

| Service | URL | Notes |
|---|---|---|
| **Frontend UI** | [http://localhost:5173](http://localhost:5173) | Vite + React application |
| **Backend Health** | [http://localhost:8000/health](http://localhost:8000/health) | Verifies app & database connectivity |
| **Interactive API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI for backend endpoints |
| **MinIO console** | [http://localhost:9001](http://localhost:9001) | Local-only object-store inspection |

### 4. Exact local demo flow

1. Open the frontend and paste a scam message such as:

   ```text
   Congratulations! You won a prize. Pay Rs. 500 to fraud123@okaxis now.
   ```

2. Confirm the result shows the scam verdict and extracted UPI entity.
3. Submit a reworded variant:

   ```text
   Urgent prize winner notice: send Rs. 500 to fraud123@okaxis to receive your reward.
   ```

   The result's **Similar reports** section should show the prior scam report
   when the local pgvector similarity threshold is met.
4. Repeat the same entity report until the fifth report. `.env` enables the
   local SNS mock; the fifth report sets `alert_triggered=true`, and the
   backend test verifies that `alerts.publish_alert()` was called.
5. Select **Screenshot**, choose a real PNG/JPEG containing the scam text, and
   wait for the direct upload → MinIO → backend fetch → Pillow validation →
   Tesseract OCR → AI pipeline → verdict flow to complete.

The local stand-ins are:

| Production service | Local stand-in | What is actually tested |
|---|---|---|
| RDS PostgreSQL + pgvector | `pgvector/pgvector:pg16` | SQL schema, persistence, vector similarity |
| Private S3 | MinIO | Presigned PUT, object fetch, image validation, cleanup |
| SNS | In-process mock enabled by `SNS_MOCK_ENABLED=true` | Threshold decision and publish call |
| SSM Parameter Store | `.env` | Configuration shape only; AWS IAM/SSM is not exercised |
| Textract | Tesseract in the backend image | Local OCR only; Textract behavior is not exercised |

Real AWS S3, SNS, SSM, RDS networking, IAM, HTTPS/ALB and VPC controls only
work after production infrastructure is provisioned and configured.

### 5. Developer Commands

```sh
# Run database migrations (also executes on container startup)
docker compose exec backend alembic upgrade head

# Run backend test suite (unit + integration against postgres)
docker compose exec backend pytest

# Open a psql shell into the local database
docker compose exec -T db psql -U scamshield -d scamshield

# Stop all containers (retains database volume)
docker compose down

# Stop containers and reset database volume
docker compose down -v
```

To inspect the local MinIO bucket:

```sh
docker compose exec minio-init sh -c 'mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" && mc ls local/scamshield-local'
```

---

## Project Documentation

Detailed project specifications and decision records are maintained in [`docs/`](./docs):

- [docs/IMPLEMENTATION_STATUS.md](./docs/IMPLEMENTATION_STATUS.md) — Current implementation status, database schema, test verification, and external ML integration checklist.
- [docs/architecture/overview.md](./docs/architecture/overview.md) — Comprehensive target architecture and cloud design.
- [docs/requirements.md](./docs/requirements.md) — Functional and non-functional requirements.
- [docs/threat-model.md](./docs/threat-model.md) — STRIDE security threat model.
- [docs/cost.md](./docs/cost.md) — AWS Free Tier and budget breakdown.
- [docs/adr/0001-local-stack-decisions.md](./docs/adr/0001-local-stack-decisions.md) — Architectural decision record for local technology stack.

---

## Security & Secrets Management

- **Zero credential leaks:** No `.env` or credential files are ever committed. See [`.env.example`](./.env.example) for the canonical local variables.
- The Compose stack uses a local development-only password for localhost testing.
- Cloud deployment will use AWS SSM Parameter Store and IAM least-privilege roles; see [`SECURITY.md`](./SECURITY.md) and [`infra/iam/ec2-runtime-policy.json`](./infra/iam/ec2-runtime-policy.json).
