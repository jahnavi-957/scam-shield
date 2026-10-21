# Scam Shield — Backend

FastAPI service that wraps the `ml/ AI module
(`scamshield_ml.analyze_message`), persists results to
PostgreSQL (RDS), stores screenshots in S3, sends SNS
alerts, and reads secrets from AWS SSM Parameter Store.
Runs as a Docker container on a single EC2 instance
inside a private VPC.

## Quickstart (local development)

```sh
# from the repo root — create the shared local config once
cp .env.example .env

# Postgres (pgvector) + MinIO + backend + frontend
docker compose up -d --build

# migrations are applied automatically by the backend container
# (alembic upgrade head runs before uvicorn starts)

# run the test suite from the repo root
cd backend
pip install -e ".[dev]"
pytest tests/ -v                      # unit tests
pytest tests/ -v -m integration       # needs the compose Postgres
```

The compose Postgres is exposed on `127.0.0.1:5433` for
host-side tooling. Copy the repository-root `.env.example` to `.env` so
Compose, the frontend and backend share one local configuration; do not create
a second backend-only environment file.

Local screenshot uploads use MinIO at `http://localhost:9000`.
`S3_PUBLIC_ENDPOINT_URL` is deliberately different from the backend's
internal `S3_ENDPOINT_URL` so presigned URLs generated inside Compose are
reachable by the host browser.

## API

| Endpoint | Purpose |
|---|---|
| `POST /analyze/text` | Analyse raw text; returns verdict + entity report counts |
| `POST /analyze/screenshot` | OCR an S3-uploaded screenshot, then analyse |
| `GET /uploads/presigned-url` | Presigned S3 PUT URL for direct frontend upload |
| `GET /entities?value=...` | Report history for a UPI ID / phone / URL ("search before you pay") |
| `GET /health` | Liveness + DB connectivity (for monitoring) |

`POST /analyze/text` flow: persist message → run the AI
pipeline → persist verdict + 384-dim embedding → pgvector
near-duplicate check → for each extracted UPI/phone/URL:
find-or-create entity, count windowed reports, fire the SNS
alert exactly at the threshold, increment the lifetime
counter. The response includes `prior_reports` (reports on
the most-reported entity, excluding the current one),
`near_duplicates` (message IDs of similar past reports)
and `alert_triggered`.

## Configuration: local dev vs EC2

| | Local | EC2 |
|---|---|---|
| Secrets (DB URL, S3 bucket, SNS ARN) | repository-root `.env` (local only) | **SSM Parameter Store** |
| DB | compose Postgres on `localhost:5433` | RDS in a private subnet |
| Model weights | mounted `ml/model/` | pulled from S3 at startup |
| OCR | Tesseract (in the image) | Tesseract (in the image); `OCR_ENGINE=textract` to upgrade |

On EC2 set `SSM_ENABLED=true`; at startup the app fetches
`/scam-shield/<environment>/{database_url,s3_bucket,sns_topic_arn}`
from SSM (with decryption) and overlays them on the env
values. The AWS *region* comes from env / instance metadata
— it cannot come from SSM, because you need a region to
build the SSM client in the first place.

### Why SSM over `.env` in production (viva point)
Secrets never touch the repo, the Docker image, or the EC2
filesystem; the instance role grants `ssm:GetParameters` on
just the `/scam-shield` path (least privilege); rotation
and CloudTrail auditing come for free.

## Architecture decisions (viva talking points)

- **Presigned upload URLs** — the frontend uploads
  screenshots *directly to S3*: image bytes never route
  through the small EC2 instance (saves memory and
  bandwidth), and the URL is a time-limited (5 min)
  capability for exactly one object, one verb, one content
  type. The backend only ever handles the S3 key.
- **pgvector for embeddings** — cosine similarity against
  past reports runs inside RDS (`embedding <=> query`),
  so the EC2 instance never pays for embedding math.
  The extension is enabled by migration 0001 and the
  compose stack uses the `pgvector/pgvector:pg16` image,
  so dev matches the cloud exactly. IVFFlat with
  `lists = 16` is right at student scale; HNSW is the
  upgrade path past ~100k reports.
- **Alert threshold logic** — `should_alert` fires when
  the windowed report count reaches the threshold
  (default 5 reports / 24 h). It fires on *exactly* the
  Nth report (the check is `count >= threshold` after the
  current report is linked). `last_alert_at` is a
  cooldown: while it sits inside the window, further
  reports don't re-alert (a burst of 20 reports → one
  alert); the rule re-arms once the window slides past
  `last_alert_at` and the count still qualifies.
- **Connection pooling** — one gunicorn worker,
  `pool_size=5 + max_overflow=5` = at most 10
  connections, deliberately small against an RDS
  instance's ~100 `max_connections`. `pool_pre_ping`
  heals private-subnet network blips; `pool_recycle`
  drops connections before RDS's idle timeout. The
  repository layer retries transient `OperationalError`s
  3× with exponential backoff (0.5 s / 1 s / 2 s).
- **Model weights from S3, not the image** — retraining
  only re-uploads to S3; every container pulls the new
  weights on its next start. No image rebuild. If the
  download fails, the ml package's rule-based classifier
  serves requests (degraded, not down).
- **SNS/S3 failures never block a verdict** — an SNS
  publish failure is logged with a redacted correlation context and count
  and the analysis still returns; the alert cooldown is
  set regardless, preventing an alert-retry storm.
- **Single gunicorn worker** — each worker loads the ML
  models into RAM, so one worker is the right sizing for
  a small EC2 instance; gunicorn still gives crash-restart
  supervision.
- **AI failures → generic 500** — the adapter
  (`app/ai.py`) converts any model exception into
  `AIPipelineError`; the client gets a clean 500, the
  real error is logged server-side with a stack trace.

## S3 lifecycle (production infrastructure)

Screenshots under the `uploads/` prefix are deleted after the OCR attempt by
the application. Production infrastructure must also add a private-bucket
lifecycle rule that expires abandoned objects after 24 hours. Terraform is not
implemented in this repository yet; see `SECURITY.md` for the current gap.

## Deployment sketch (EC2)

```sh
docker run -d -p 8000:8000 \
  -e ENVIRONMENT=prod -e SSM_ENABLED=true -e AWS_REGION=us-east-1 \
  -e MODEL_S3_BUCKET=<your-bucket> \
  scamshield-backend
```

The EC2 instance role needs: `ssm:GetParameters` on
`/scam-shield/*`, `s3:GetObject`/`PutObject` on the
uploads bucket and model prefix, and `sns:Publish` on the
alert topic. The RDS instance stays in a private subnet —
the app reaches it over the VPC's internal network only.

## Tests

- `tests/test_alert_threshold.py` — pure unit tests of
  the alert rule (fires exactly at the Nth report).
- `tests/test_repository.py` — persistence, idempotent
  entities, windowed counts, pgvector similarity.
- `tests/test_analyze_endpoint.py` — full endpoint flow
  with a **mocked** AI pipeline (loading the real models
  in tests would be far too slow).
