# Verification — 2026-10-19

Observed locally on macOS, Python 3.14.7 and isolated PostgreSQL 18.6 (Postgres.app).
No application database or Android file was changed. The weak local JWT secret was
rotated in the Git-ignored .env and that file restricted to owner read/write.

| Check | Observed result |
|---|---|
| Full suite with TEST_DATABASE_URL, private schemas | 92 passed |
| Default suite without PostgreSQL | 90 passed; 2 PostgreSQL-specific tests skipped |
| Migration of legacy schema with synthetic metadata | Passed, including oversized-record preflight/transaction rollback |
| Alembic drift check after legacy upgrade | No new upgrade operations |
| Concurrent refresh rotation/replay | One rotation succeeds; replay revokes sessions |
| Raw TXT and subprocess PDF processing | Passed, with controlled invalid-document responses |
| Double condition, maintenance boundary, syllables/chunks | Passed |
| No document content in captured SQL/logs | Passed for synthetic test requests |
| Import and AST parse | Passed; AsyncEngine and 22 OpenAPI paths |
| Ruff lint and formatting | Passed |
| pip check | No broken requirements |
| OSV advisory lookup for installed lightweight environment | 48 packages, no known advisories returned |
| docker compose config -q | Passed using a synthetic configuration password |

The dependency lookup is point-in-time and covers the installed lightweight API
and test environment, not an uninstalled ML/GPU environment. JWT implementation
was migrated to PyJWT 2.15.1; Mako upgraded to 1.4.3; python-jose, ecdsa, rsa, pyasn1
and uvloop were removed from the local venv. Runtime requirements exclude uvloop.

Reproduce from the repository root:

```sh
python -m pytest -q --basetemp=.pytest-tmp
# Set TEST_DATABASE_URL to an explicitly dedicated *_test PostgreSQL database:
python -m pytest -q --basetemp=.pytest-tmp
ruff check app ml_training tests alembic scripts
ruff format --check app ml_training tests alembic scripts
python scripts/audit_dependencies.py
python -m pip check
```

Not executed: GPU training, real-corpus model evaluation, real-model generation,
Docker image build/start (desktop daemon unavailable), Windows/Linux runner jobs,
DigitalOcean provisioning/deployment, TLS issuance or host swap/monitoring checks.
CI is configured for Windows/macOS/Linux Python 3.12 and PostgreSQL 18, but those
remote jobs have not been dispatched. Actual ML weights and corpus are deliberately
not included. The application's existing database still needs the reviewed migration
procedure in security.md before running the new API against it.
