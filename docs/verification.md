# Verification — 2026-10-19

Observed locally on macOS arm64, Python 3.14.7 and PostgreSQL 18.6 (Postgres.app).
The independent-adult telemetry and offline ML evaluation phase produced:

| Check | Observed result |
|---|---|
| Full suite with TEST_DATABASE_URL, private schemas | 103 passed in 18.26 s |
| Default suite without PostgreSQL | 101 passed; 2 PostgreSQL-specific tests skipped, 12.80 s |
| Adult-owned sessions | Creation, history, progress, completion and immutable score snapshots passed |
| RBAC/IDOR and input injection | Other users cannot read/update sessions or inject owners/scores |
| Existing child contracts | Existing suite plus child snapshot compatibility passed |
| Migration of existing child sessions | Ownership preserved and exact numeric snapshot backfill passed |
| Configured application PostgreSQL migration | Applied 0003_adult_telemetry; schema backup stored privately under .git |
| Alembic drift check against application database | No new upgrade operations detected |
| Application schema inspection | Adult ownership and numeric acceptance checks present |
| Python source AST parse, API import and OpenAPI | Passed; 24 OpenAPI paths |
| Ruff lint and formatting | Passed; 44 Python files formatted |
| pip check, lightweight and separate ML environments | No broken requirements |
| Real EASIER preparation and mT5 LoRA fine-tuning | Executed; 120 steps, finite loss, trainable weights changed |
| Base/checkpoint inference and real hybrid pipeline | Executed; 0/6 valid model outputs, 0/6 hybrid acceptances |
| Model control markers | Rejected in runtime fidelity and offline readability evaluation |

The numeric evaluation evidence, hashes, reproduction commands, latency and
limitations are in [ml-evaluation.md](ml-evaluation.md) and its linked JSON. This
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
tests did not use the application database. The application migration was a
separate explicit operation on local port 5432. No document content was copied
by that migration; the new session fields contain identifiers and numeric telemetry.

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
the small test set was consulted during diagnostics and is not a blind holdout.
