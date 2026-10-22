# Scam Shield security audit and operating policy

**Audit date:** 2026-10-21  
**Scope:** AI module, FastAPI backend, React frontend, local Compose stack and
production deployment requirements.  
**Status vocabulary:** **Done** means implemented in the repository;
**Deferred** means intentionally requires a future production component;
**Gap** means not yet implemented and should not be described as protected.

This document is a truthful status record for the graded demo. Local controls
are not evidence that AWS networking, IAM, HTTPS, RDS or S3 production
controls have been provisioned.

## 1. Integration contract audit

| Area | Status | Evidence / current behavior |
|---|---|---|
| AI verdict shape | Done | `ml/scamshield_ml/pipeline.py` defines `ScamVerdict`; `backend/app/ai.py` maps the stable fields used by `AnalysisResponse`. |
| Text response contract | Done | `AnalysisResponse` is the Pydantic response model and frontend `AnalysisResponse` mirrors it. |
| Screenshot response contract | Done | Screenshot uses the same response model as text after OCR. |
| Similar-report evidence | Done | Backend filters matches to prior scam analyses and frontend renders `near_duplicates`. |
| Presigned upload flow | Done locally | Frontend requests a PUT URL, uploads to MinIO/S3, posts the generated key, backend validates bytes, runs OCR and invokes the same analysis flow. |
| Screenshot entry point | Done | Landing page and header expose the screenshot flow. |
| API error contract | Done | Backend returns `{code, detail}`; validation details are typed; frontend normalizes string and FastAPI list details. |
| Unexpected frontend failures | Done | `GlobalErrorBoundary` provides a calm recovery screen. |
| Async screenshot queue | Deferred | The current demo is synchronous after the direct upload. SQS, report status, worker retries and DLQ remain a production milestone. |

## 2. Input validation and injection

| Check | Status | Control or remaining issue |
|---|---|---|
| Empty/null text rejected | Done | `AnalyzeTextRequest` has a Pydantic minimum length and the route rejects whitespace-only input. |
| Maximum text length | Done | Pydantic max length is 10,000 characters and the runtime configuration is checked again. |
| Screenshot key validation | Done | Pydantic accepts only `uploads/<uuid>.png` or `.jpg`. |
| Presign content type | Done | Pydantic `Literal` allows only `image/png` and `image/jpeg`. |
| Screenshot size | Done | S3 download is bounded and Pillow validation repeats the byte limit. |
| Screenshot actual type | Done | Pillow parses and verifies PNG/JPEG content; extension and S3 metadata are not trusted. |
| Image dimensions/pixel count | Done | Width, height and pixel count are bounded; decompression-bomb warnings are rejected. |
| SQL injection | Done | Repository access uses SQLAlchemy expressions and bound parameters. No raw SQL concatenation was found. |
| User text rendering | Done | No `dangerouslySetInnerHTML`, `innerHTML` or equivalent server-controlled HTML rendering was found. React JSX escapes text. |
| URL fetching/SSRF | Done | Submitted URLs are extracted as strings; the application does not fetch them. |
| Model prompt injection | Not applicable currently | The inference path is deterministic classifier/rules/embeddings, not an LLM prompt. If an LLM is added, message text must remain data inside a strict prompt. |

## 3. File upload security

| Check | Status | Control or remaining issue |
|---|---|---|
| Narrow generated keys | Done | Keys are generated UUIDs under `uploads/`; callers cannot choose arbitrary paths. |
| PUT-only capability | Done | Presigned URLs use S3 `put_object` and bind the content type. |
| Expiry | Done | Settings and the endpoint cap expiry at 300 seconds. |
| Object overwrite protection | Done locally / Gap publicly | UUIDs make accidental collisions unlikely, but unauthenticated callers can still request many keys. Authentication and quotas are still needed before public exposure. |
| Server-side upload validation | Done | Object is bounded, parsed and verified before OCR. |
| Upload cleanup | Done | Screenshot objects are deleted after the OCR attempt; a bucket lifecycle rule is still required as crash recovery. |
| Public bucket protection | Deferred | Local MinIO is private by default. AWS S3 Block Public Access, bucket policy, encryption and lifecycle must be implemented in Terraform before deployment. |

## 4. Rate limiting and abuse prevention

| Check | Status | Control or remaining issue |
|---|---|---|
| Per-IP analysis limit | Done for one process | In-memory limiter defaults to 20 analysis requests per 60 seconds and returns `429` with `Retry-After`. |
| Presign abuse quota | Gap | Presign issuance is not separately rate-limited and there is no authentication. Add an edge/API quota before public deployment. |
| Multi-worker/shared limit | Deferred | The in-process limiter does not coordinate across Gunicorn workers or EC2 instances. Use an ALB/WAF/API gateway or shared Redis limiter in production. |
| Request body limit | Done | Middleware checks declared `Content-Length` and counts streamed ASGI body bytes before application parsing. |
| Classifier concurrency/timeouts | Deferred | Screenshot work is synchronous. The planned worker/SQS design should provide bounded concurrency, visibility timeout, retries and DLQ. |

## 5. Secrets and credentials

| Check | Status | Control or remaining issue |
|---|---|---|
| Hardcoded production credentials | Done | No AWS access keys, private keys or production connection strings were found in tracked source. |
| Local secrets | Done | Root `.env.example` is the canonical local template; `.env` is Git-ignored and excluded from Docker contexts. Values are development-only. |
| Production secret source | Done in code / Deferred infrastructure | `ENVIRONMENT=prod` with `SSM_ENABLED=true` fails closed if SSM is unavailable or required parameters are missing. The actual SSM parameters and role still need provisioning. |
| SSM fail-open behavior | Done | Production no longer falls back to local environment/default secret values after SSM errors. |
| EC2 IAM policy | Done as reviewed artifact / Deferred provisioning | See [`infra/iam/ec2-runtime-policy.json`](./infra/iam/ec2-runtime-policy.json). Replace placeholders only during deployment. |
| Database credentials | Deferred | Production should use a dedicated migration role and runtime role; the current Compose password is only for localhost. |

### Authentication and authorization

**Gap before public deployment.** The local graded-demo API is intentionally
single-user and currently has no authentication or authorization dependency.
Anyone who can reach it can submit reports, request upload capabilities and
query entity history. Do not expose the current endpoints directly to the
Internet; add an authenticated identity/tenant boundary and per-user quotas
before public or multi-user deployment.

### IAM policy review

The reviewed policy grants only:

- `ssm:GetParameters` under `/scam-shield/prod/*`;
- `s3:GetObject`, `PutObject`, and `DeleteObject` under the upload prefix;
- `s3:ListBucket` only for the upload and pinned model prefixes;
- `s3:GetObject` only for the pinned model version;
- `sns:Publish` only to the configured alert topic.

It does **not** grant `s3:*`, `ssm:*`, administrator access, IAM changes,
RDS administration, EC2 administration or access to unrelated SNS topics.

## 6. Network and transport security

| Check | Status | Control or remaining issue |
|---|---|---|
| CORS origin | Done in application | Origins are configured explicitly; wildcard methods/headers were removed and credentials are disabled. Local origin is `http://localhost:5173`. |
| Security headers | Done in application | Adds `X-Content-Type-Options`, `X-Frame-Options`, CSP, `Referrer-Policy` and `Permissions-Policy`; HSTS is enabled for production. |
| Production frontend API transport | Done in frontend build logic | Production defaults to same-origin requests or accepts only an explicit HTTPS URL. HTTP is permitted only for local development. |
| HTTPS termination | Deferred | ALB certificate, HTTP-to-HTTPS redirect, TLS policy and HSTS deployment must be provisioned in AWS. |
| RDS public accessibility | Deferred | The code cannot enforce VPC placement. Terraform must set RDS `publicly_accessible=false` and allow 5432 only from the backend security group. |
| Docs exposure | Deferred | `/docs` is useful locally. Production should protect or disable Swagger/OpenAPI for an unauthenticated public deployment. |

## 7. Data privacy and retention

### What is stored now

- The backend sends the original submitted text to the AI pipeline because
  entity extraction and classification need the original input.
- The database stores a redacted message copy. Common URLs, emails, UPI IDs
  and phone numbers are replaced before persistence.
- The database stores extracted scam-side entities because they are the core
  intelligence-graph feature requested by the product.
- The database stores an embedding for near-duplicate matching. Embeddings are
  derived data and can still carry information about source text; this is a
  residual privacy risk that should be reviewed before high-sensitivity use.
- No requester identity or IP address is written to reports, entities or
  analysis records. The IP is held transiently as an in-memory rate-limit key
  and is not logged.
- SNS/log output omits raw entity values. SNS alert content may contain the
  scam-side identifier needed for investigation; it must be access-controlled
  and retained according to the production alert policy.

### Intended retention policy

1. Screenshot objects: delete immediately after the OCR attempt; enforce a
   private S3 lifecycle expiry of **24 hours** for abandoned objects.
2. Redacted messages, analysis results and embeddings: retain for **90 days**
   for the demo intelligence graph, then purge them together.
3. Aggregate entity reputation counters: retain for **365 days**, then expire
   or archive them without source message content.
4. Operational logs and SNS alerts: retain for **30 days** unless the
   production incident policy requires a documented exception.
5. Backups must follow the same deletion schedule where the provider allows it;
   backup expiry must be configured separately from row deletion.

### Current retention gap

The application currently deletes processed screenshots but does not yet run a
scheduled database purge or enforce AWS lifecycle/IaC policies. The intended
policy above must not be represented as already active until those controls
are provisioned.

## 8. Dependency and build security

| Check | Status | Evidence / remaining issue |
|---|---|---|
| Backend non-root container | Done | `backend/Dockerfile` runs as `appuser`. |
| Frontend non-root container | Done | `frontend/Dockerfile` creates and uses `appuser`. |
| Secrets excluded from image context | Done | Root, backend and frontend `.dockerignore` files exclude `.env`, keys, datasets and generated assets. |
| Lockfile used by frontend image | Done | Frontend image uses `package-lock.json` with `npm ci`. |
| Dependency vulnerability scan | Partial / action required | `npm audit --audit-level=moderate` reports 11 findings in the existing frontend toolchain, including high `braces` transitive issues and a moderate Vite/esbuild issue. After the model-stack update, `pip-audit -r ml/requirements.txt` and the generated backend dependency list report no known vulnerabilities. The ranges now move to Pillow 13+, Transformers 5.10+ and Sentence-Transformers 5.6+, but model compatibility, Python lock/hash pinning and a clean SBOM scan still must be verified. |
| Python dependency pinning | Gap | `pyproject.toml` and `ml/requirements.txt` use ranges rather than a fully hash-locked environment. Add a generated lock/SBOM and `pip-audit`/OSV scan before production. |
| Base image pinning | Gap | Compose and Docker base images are versioned where practical but not digest-pinned. Add digest pinning and image scanning in CI. |
| Production frontend artifact | Deferred | The current frontend image is intentionally a local Vite dev server. A production deployment needs a multi-stage static build/serving image. |

## 9. Known gaps ranked before the graded demo

### Must resolve before a public or AWS demo

1. Provision and verify private RDS, S3 Block Public Access, bucket lifecycle,
   security groups, HTTPS/ALB and the IAM policy with real ARNs.
2. Add authentication/authorization and a shared rate limit before exposing
   unauthenticated analysis and upload endpoints to the Internet.
3. Add the scheduled database retention purge and verify backup retention.
4. Run Python dependency scanning and decide how to handle the reported npm
   transitive vulnerabilities.

### Important but acceptable for the local graded demo

5. Replace synchronous screenshot analysis with the planned SQS worker,
   idempotency key and report-status polling path.
6. Add upload one-time consumption/idempotency so replaying an `s3_key` cannot
   create duplicate reports.
7. Make entity creation, alert cooldown and report increments atomic under
   concurrent requests.
8. Add model artifact signatures/immutable versions and fail readiness when a
   production model is missing instead of silently using the fallback.
9. Add browser/e2e automation for the MinIO upload/OCR path; the current
   repository has backend unit coverage and Compose instructions but no
   Playwright/Cypress suite.
