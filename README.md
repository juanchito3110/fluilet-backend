# Fluilet Backend

FastAPI + async SQLAlchemy/psycopg. Local Spanish mT5 and deterministic refinement.
Only accounts, relationships, activity metadata and numeric telemetry are persisted.
No commercial inference service is used. Android remains a separate repository.

## Local setup

Use Python 3.12 for a reproducible ML environment. The lightweight API/test suite
also runs on the workspace's Python 3.14. CPU/GPU training is a separate install.

```sh
python -m venv .venv
# Activate .venv for your OS, then:
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -c "import secrets; from dotenv import set_key; set_key('.env', 'SECRET_KEY', secrets.token_hex(32))"
```

Set `DATABASE_URL` to a PostgreSQL database using `postgresql+psycopg://` and an
application-specific account. Never commit credentials or use the example password.
For Docker, also generate `POSTGRES_PASSWORD` with URL-safe characters.

```sh
python -m alembic upgrade head
python -m uvicorn app.main:app --loop asyncio --no-access-log
python -m pytest -q --basetemp=.pytest-tmp
ruff check app ml_training tests alembic scripts
```

Existing unmanaged databases require the preflight/stamp procedure in
[security.md](docs/security.md), not an unconditional baseline upgrade.
No tables are created during application startup. OpenAPI is at `/docs`.

## Adaptation

`POST /api/v1/adaptations/text` accepts JSON (`text`, optional `child_id` and
`nivel_simplificacion_nlp`). `POST /api/v1/adaptations/file` accepts the **raw**
PDF/TXT body, with `Content-Type: application/pdf` or `text/plain`; it does not
accept multipart. Maximum request size is 5 MiB, checked even without Content-Length.
The file endpoint accepts level/child ID in the query. Use synthetic documents
when trying requests in Swagger: its browser may retain form contents locally.

A success includes `adapted_text`, `document` metadata, per-chunk numeric metrics,
`meets_readability_target`, `quality_status` (`target_met` or `best_effort`) and
content-free `warnings`. All valid, in-limit texts at levels 1..5 produce a reading,
including a single word, long technical sentences and uneven document partitions.
The safest original is retained when no faithful improvement exists. Below-target
results are delivered with 200; invalid/empty content returns 422, size violations
413, and busy workers 503. Never log request/response bodies in clients or proxies.

Delta >=15 and adapted score >=65 remain the unrounded **quality target** for every
chunk and the whole document, rather than a condition for HTTP success. Originals
strictly >128.535 use maintenance >=85. Unchanged text records delta=0, without
claiming an improvement. Scores are not clamped to 0–100. The automatic lexical
fidelity guard is not a clinical certification or proof of semantic equivalence.

The vocabulary includes context-constrained EASIER pairs and bounded structural
rules. Restrictive relatives, diagnostic populations, numbers and negations are
preserved. Optional model attempts have a total budget of at most eight seconds;
missing weights, unsuccessful generation or timeouts cannot discard a safe reading.
A request processing timeout returns the original with `processing_budget_exceeded`.
Sentence chunks are grouped linearly; an unsplittable sentence remains intact for
rules/original delivery and is skipped by mT5 if its token budget is exceeded.

## Optional local model

API imports and tests do not require PyTorch/Transformers. Install training
requirements in a suitable Python/GPU environment (see `ml_training/README.md`),
then place the trained model and tokenizer in a local checkpoint directory and set
`MT5_CHECKPOINT`. Weights are excluded from Git and Docker contexts. Mount the
checkpoint read-only in production. `MT5_LOCAL_FILES_ONLY=true` prevents downloads;
missing dependencies/cache use deterministic rules and the original-text fallback.
`ALLOW_RULE_BASED_FALLBACK` is retained for configuration compatibility; it cannot
disable the mandatory safe reading fallback.

Official base mT5 provides .bin weights: loading uses PyTorch >=2.6 with
weights_only=True and prefers Safetensors when present. Trained checkpoints are
saved as Safetensors. No remote Python model code is trusted.

Base mT5 is not fine-tuned for simplification. The response records method `rules`, `hybrid` or `original`; inference never claims a trained checkpoint exists when it does not.
Load is lazy; restart the API after installing dependencies/checkpoints to retry a
previously unavailable load. Generation uses deterministic beams; temperature is
not passed with `do_sample=false` because it would have no effect.

The measured lightweight EASIER experiment and its limitations are documented in
[ml-evaluation.md](docs/ml-evaluation.md). Its checkpoint failed acceptance on the
exploratory test sample and remains excluded from the runtime configuration.
The complete hybrid system evaluates a deterministic candidate before generating
with mT5, retains fidelity checks and reports readability targets separately from delivery.
Its quality coverage and conditional compliance are measured
separately on EASIER and on a disclosed synthetic diagnostic fixture.
The six EASIER cases now explicitly inform rule calibration (5/6 accepted); a
separate 12-document internal audit remains 0/12. See the report for the distinction
between calibration coverage, generalization and automatic fidelity checks.

`GET /health/ready` returns 200 when PostgreSQL and the configured pipeline are
operative, including deterministic-only service. It reports `engine_mode` and runs
a small fixed CPU probe without loading model weights. Database or pipeline failure
returns 503. A below-target reading remains available with HTTP 200.

## Independent adult readings

An `ADULTO_INDEPENDIENTE` adapts without `child_id`, starts an owned session with
`POST /api/v1/readings` and `{"document_id":"UUID"}`, and reads their history with
`GET /api/v1/readings`. The existing `PATCH /api/v1/readings/{id}` records progress;
`GET /api/v1/users/me/progress` uses the dashboard's existing progress fields.
Sessions snapshot numeric adaptation metrics without creating a child profile.
Tutor/NINO routes are preserved. Apply Alembic revision `0003_adult_telemetry`
before serving; see [api-contract.md](docs/api-contract.md).

## Tests and deployment

Default tests use in-memory SQLite. To exercise PostgreSQL, set
`TEST_DATABASE_URL` to a dedicated database whose name ends in `_test`. Each test
uses/drops its own private schema. The actual configured application database is
never used by tests. CI covers Python 3.12 on Windows/macOS/Linux and PostgreSQL 18.

Docker Compose supplies a non-root, read-only API, PostgreSQL and a TLS proxy.
Configure certificate files on the VPS at `/etc/fluilet/tls/fullchain.pem` and
`privkey.pem` before starting the proxy. No certificate/domain or VPS was provisioned
by this implementation. Docker builds have ML disabled by default; enable
`INSTALL_ML=true` and mount checkpoint files to use mT5. Budget and benchmark RAM,
CPU and generation latency before choosing VPS capacity.

```sh
docker compose build
docker compose up -d db
docker compose run --rm api python -m alembic upgrade head
docker compose up -d
```

Disable host swap, core dumps and body capture before processing real documents;
read the exact scope/limits in `docs/security.md`. Proxy uploads and responses are
unbuffered, with any incidental temporary buffers on RAM tmpfs. The database volume
contains metadata/accounts only. No Redis/file queue is used.

Observed local verification and remaining operational checks: [verification.md](docs/verification.md).

## Educational lessons and progress

Generate Spanish educational readings with `POST /api/v1/adaptations/generate`:
six categories, contextual Spanish Wikipedia retrieval, 29 factual offline articles,
optional `custom_topic`/`topic`, levels 1..5 and exactly two text-grounded comprehension
questions. Responses include source attribution, a fact and an interactive glossary. Existing adaptation responses gain
only additive lesson fields. Reading sessions accept category, level, comprehension
and TTS telemetry and expose five educational achievements.

See [educational-features.md](docs/educational-features.md) for request shapes,
permissions, scoring and migration details. Adult educational progress uses
`GET /api/v1/readings/progress`; child educational progress uses
`GET /api/v1/children/{id}/progress` and returns the educational JSON by default.
The previous Android list is available at `/api/v1/children/{id}/progress/legacy`.

Questions also adapt to the authorized reader's age (6–8, 9–11 or standard 12+),
with a hint and educational explanation. Progress includes FluiBot's four stages,
six collectible cards, ten accessories priced at 15–120 gems, and suggestions for
the next reading level and voice speed. Rewards include 30 welcome gems and are
recomputed from the learner's sessions, plus three daily missions worth 25/30/40
gems. The alias `/api/v1/profiles/{profile_id}/educational-progress` returns the same
owner-scoped child summary. Apply Alembic revision `0005_daily_activity` for the
content-free daily activity journal; previous legacy progress list routes remain
available. Mission goals reset at UTC midnight while historical bonuses remain.
Unknown topics without an online or local source return a controlled 503 rather
than fabricated lessons. `WIKIPEDIA_ENABLED=false` selects offline operation.
