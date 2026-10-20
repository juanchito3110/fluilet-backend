# Verification — 2026-10-19

Observed locally on macOS arm64, Python 3.14.7 and PostgreSQL 18.6 (Postgres.app).
The readiness, complete hybrid evaluation and local E2E cleanup phase produced:

| Check | Observed result |
|---|---|
| Full suite with TEST_DATABASE_URL, private schemas | 115 passed in 34.96 s |
| Default suite without PostgreSQL | 113 passed; 2 PostgreSQL-specific tests skipped, 13.17 s |
| Adult-owned sessions | Creation, history, progress, completion and immutable score snapshots passed |
| RBAC/IDOR and input injection | Other users cannot read/update sessions or inject owners/scores |
| Existing child contracts | Existing suite plus child snapshot compatibility passed |
| Migration of existing child sessions | Ownership preserved and exact numeric snapshot backfill passed |
| Application PostgreSQL schema | Retains 0003_adult_telemetry; no column changes or new migration in this phase |
| Alembic drift check against application database | No new upgrade operations detected |
| Application schema inspection | Adult ownership and numeric acceptance checks present |
| Python source AST parse, API import and OpenAPI | Passed; 24 OpenAPI paths |
| Ruff lint and formatting | Passed; 45 Python files formatted |
| pip check, lightweight and separate ML environments | No broken requirements |
| Prior EASIER/mT5 training evidence | 120 real LoRA steps; checkpoint hash rechecked and unchanged in this phase |
| Base/checkpoint inference and real hybrid pipeline | Four actual runs: EASIER 0/6 accepted; synthetic diagnostic 8/14 accepted for either model |
| Conditional acceptance compliance | 6/6 strict, 2 maintenance exceptions; 8/8 pass mathematical and lexical gates |
| Actual HTTP readiness + application PostgreSQL | 200, engine_mode=deterministic, model=not_loaded; no weight load |
| Readiness failure paths | Missing database, unavailable configured engine and broken refiner return controlled 503 |
| Physical E2E cleanup, local application PostgreSQL | Atomic DELETE of 3 inactive test users, 1 child, 2 documents, 2 readings, 1 assignment, 2 chunks, 6 refresh tokens |
| Model control markers | Rejected in runtime fidelity and offline readability evaluation |

The numeric evaluation evidence, hashes, reproduction commands, latency and
limitations are in [ml-evaluation.md](ml-evaluation.md) and its linked evidence JSON files. This
checkpoint failed acceptance and was not activated for serving. Corpus, derived
examples, predictions, weights and environments remain in Git-ignored directories.
No Android files were changed. ML used public research data rather than API traffic.

Reproduce from the repository root:

```sh
python -m pytest -q --basetemp=.pytest-tmp
# Set TEST_DATABASE_URL to an explicitly dedicated *_test PostgreSQL database:
python -m pytest -q --basetemp=.pytest-tmp
ruff check app ml_training tests alembic scripts
ruff format --check app ml_training tests alembic scripts
python -m pip check
python -m alembic current
python -m alembic check
```

The dedicated test PostgreSQL used port 55439 and private disposable schemas;
tests did not use the application database. The earlier application migration was a
separate explicit operation on local port 5432; this phase changed no columns.
Cleanup used an exact allowlist, locked and verified inactive users, checked
cascade counts transactionally and verified zero remaining E2E accounts. All seven
application tables were empty afterward. No user content was reconstructed or
retained by cleanup. The application PostgreSQL remains running.

Earlier verification of the base refactor covered 92 PostgreSQL tests, refresh
rotation/replay, streaming TXT/PDF processing, zero-retention SQL/log assertions,
readability/chunk boundaries, Docker Compose configuration and an OSV lookup of
48 lightweight packages. That advisory lookup is a historical point-in-time result,
not a new audit of the ML environment. `scripts/audit_dependencies.py` can repeat
the advisory lookup.

Not executed: GPU training, clinical/human comprehension studies, production-size
document/concurrency benchmarks, Docker image build/start, Windows/Linux runner
jobs or DigitalOcean provisioning/deployment. Remote CI jobs were not dispatched
by this local verification. The base and fine-tuned model evaluation was exploratory;
the small EASIER test set was consulted during diagnostics and is not a blind
holdout. The 14-case synthetic fixture is also a developer diagnostic, not an
independent benchmark or evidence of semantic/clinical efficacy.
