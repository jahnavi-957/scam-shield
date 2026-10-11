# Scam Shield

AI-powered fraud detection platform for SMS, UPI, WhatsApp, and phishing scams built around a shared **scam intelligence graph**.

> **Current Status: M1 skeleton + ML pipeline + Backend API — complete and verified locally.**
> The `ml/` package ships a fine-tuned DistilBERT classifier and MiniLM embedder (100 tests passing). The FastAPI backend implements the full analysis API — text and screenshot (OCR) ingestion, pgvector near-duplicate detection, entity tracking with SNS alert thresholds, S3 presigned uploads, and SSM-backed configuration — with Alembic migrations and a 30-test suite. No AWS resources created yet.

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

## Local Development Quick Start

### Prerequisites
- Docker Desktop (with WSL2 backend on Windows) **running**
- Git

Containers manage Python and Node dependencies internally, so local runtimes are not required.

### 1. Start the Local Stack
```sh
docker compose up -d --build
```

### 2. Service Endpoints

| Service | URL | Notes |
|---|---|---|
| **Frontend UI** | [http://localhost:5173](http://localhost:5173) | Vite + React application |
| **Backend Health** | [http://localhost:8000/health](http://localhost:8000/health) | Verifies app & database connectivity |
| **Interactive API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Swagger UI for backend endpoints |

### 3. Developer Commands

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

- **Zero credential leaks:** No `.env` or credential files are ever committed. See `backend/.env.example` for required local variables.
- The Compose stack uses a local development-only password for localhost testing.
- Cloud deployment will use AWS SSM Parameter Store / Secrets Manager and IAM least-privilege roles starting in M4.