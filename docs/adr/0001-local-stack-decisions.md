# ADR 0001 — Local Stack Decisions

- **Status:** Accepted (M1)
- **Date:** 2026-10-08
- **Deciders:** project owner + implementation assistant

## Context

M1 must establish a local development environment that mirrors the production runtime (containers on Linux) so that M3+ deployment ships "the same artifact, bigger machine". Four questions needed answers before writing code:

1. Which Python version do we standardize on?
2. Which PostgreSQL image provides pgvector out of the box?
3. Sync or async SQLAlchemy for the first version?
4. Should schema migrations be a first-class citizen from day one?

## Decisions

### 1. Pin Python 3.12 everywhere

- Containers use `python:3.12-slim`.
- Host-side Python tooling (if any) uses `uv python install 3.12` — **not** the machine's Python 3.14.

**Why:** M2 needs scikit-learn/numpy/scipy/pandas. Those ecosystems lag the newest CPython releases on native wheels; 3.12 is the safe, widely supported target. The host has 3.14.7 installed, which would create silent, hard-to-debug dependency failures later.

**Consequences:** host Python is irrelevant to the project; the occasional 3.12 interpreter may need downloading for host-side scripts.

### 2. Use `pgvector/pgvector:pg16` as the local database image

**Why:** the stock `postgres` image does not include the `vector` extension. We enable `CREATE EXTENSION vector` in the first Alembic migration so M2 can add embedding columns without switching images. `pg16` matches the RDS version family we will use in M4.

**Consequences:** we run PostgreSQL 16 locally and propose the same major version on RDS; no breaking switch later.

### 3. Start with sync SQLAlchemy 2 + psycopg (v3)

**Why:** fewer abstractions to learn; request handlers that call DB code are simple to read; Alembic config stays trivial; the M1/M2 workloads are not I/O-bound enough to justify async complexity. Async adds complexity that distracts from the Cloud Computing learning goals.

**Consequences:** if the worker pipeline (M6) or profiling later shows a bottleneck, we may introduce async or a separate connection strategy — that is an ADR of its own, triggered by evidence, not by fashion.

### 4. Alembic migrations from the first schema

**Why:** reports/entities/verdicts will be modified every milestone (vector columns, reputation fields, campaign counts). Starting migrations now makes every later change reviewable and reproducible, and lets us test migrations in CI.

**Consequences:** schema changes are always additive + migration files, never ad-hoc edits.

## Alternatives considered

| Option | Rejected because |
|---|---|
| Python 3.14 host-only | breaks M2 ML deps; containers standardize anyway |
| Stock `postgres:16` image | no pgvector → we'd rebuild or switch images mid-project |
| Async SQLAlchemy from M1 | more moving parts for a single-user local API; migrate later if needed |
| Raw SQL / no ORM | slower to evolve schema safely across 12 milestones; ORM + Alembic is the standard pairing |
| `asyncpg` driver | ties us to async; psycopg3 works with both sync and async |