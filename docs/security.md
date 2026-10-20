# Security and privacy implementation boundaries

## Database migration

New empty PostgreSQL databases: `python -m alembic upgrade head`.
Existing unmanaged databases: take an approved **metadata-only** backup, inspect
that all six tables/types/constraints match 0001_baseline, check for orphan links
and negative reading durations, then `python -m alembic stamp 0001_baseline` followed
by `python -m alembic upgrade head`. Do not stamp an unknown or partially matching
schema. Migration 0002 is intentionally forward-only because resurrecting retained
file locations conflicts with policy. It fails rather than deletes documents over
the new 5 MiB limit; reconcile those legacy metadata records explicitly first.
Legacy scores/hash remain NULL because no retained text exists to recompute them.
All legacy refresh tokens are revoked. Auth versions/mandatory JWT claims require
fresh login. Old enum labels TUTOR/ADULTO_INDEPENDIENTE are preserved; NINO is added.
Original filename/storage_path columns are removed. Audit/remove any files in
legacy storage/backups separately; dropping a column cannot delete external files.
Never run migrations against a database just because its credentials exist in .env.

## Zero retention

Content is received in RAM with bounded streaming, then decoded/extracted and
processed without file queues or DB text columns. Raw file bodies avoid Starlette's
multipart spooling entirely; multipart is rejected before parsing. PDF extraction
uses a killable process, 10-second deadline, page/decoded-text limits and Linux
CPU/address-space limits. Windows/macOS retain input/page/time limits; Linux is the
production target for the address-space cap. Embedded resources are not executed,
password PDFs/scans with no extractable text fail closed. There is no OCR service.

SQLAlchemy hides bind parameters. API validation errors remove rejected input,
field-name surprises and exception context. Unexpected application errors are
sanitized at the ASGI boundary without logging tracebacks. The PDF worker disables
logging/output. Request bodies, model candidates and response text must never be
captured by external logging/APM/debug tools. Do not enable SQL echo, HTTP BODY
logging, profiler-local capture or debug tracebacks for real documents.

Request-local references are released after work completes. Python strings/native
model buffers are not securely erasable; this is non-persistence, not a claim of
forensic RAM erasure. A timed-out native inference thread retains its slot and
input until it actually completes; requests never launch unbounded replacement
threads. PDF workers are terminated on timeout/cancellation. Serving has no prompt
cache. Model weights and explicitly licensed offline training data are not user
uploads and are intentionally separate artifacts.

Host swap/hibernation, crash/core dumps, container checkpoints, snapshots of live
RAM and monitoring agents can persist process memory. Disable these on the VPS,
including encrypted swap if the policy literally forbids any content reaching disk.
The provided containers disable core dumps, use a read-only API filesystem and
RAM tmpfs for incidental proxy/runtime temporaries. The operator must verify host
settings and monitoring/backups; application code cannot guarantee those settings.
SHA-256 is deterministic and can reveal a match to guessed known content; it is
not anonymization or protection against dictionary attacks. Hashes are scoped by
owner for deduplication and should not be exposed to unrelated users.

## Access and abuse

JWT uses PyJWT 2.15.1 with an explicit HS256 allowlist; python-jose and its
ecdsa/rsa dependency chain are removed. See the published advisories
https://github.com/advisories/GHSA-3qf3-8w2g-rqmx and
https://github.com/advisories/GHSA-wj6h-64fc-37mp. Their asymmetric-key scenarios
were not demonstrated against the HMAC-only configuration; removing the packages
also avoids depending on that affected implementation.

Bcrypt costs 13..16, enforces 72 UTF-8 bytes, and upgrades older costs on successful
login. JWT validates signature/issuer/audience/type/UUID/expiry/role/auth-version.
Refresh tokens are hashed, rotated under a user-row lock and a replay revokes all
sessions. Logout/password change increment the account auth version, invalidating
existing access tokens immediately. Account state/child relationship are checked
on every authenticated request. Tutor-created NINO accounts cannot manage tutor
resources, upload documents or self-register.

Login failures are generic and blocked after five failures for 15 minutes. Local
IP rate buckets contain no usernames/content; Nginx adds IP limits across workers.
The supplied proxy does not forward arbitrary client IP headers, and Uvicorn does
not trust them. Consequently its in-process fallback limiter sees the proxy as one
client in Docker; Nginx enforces per-client limits. Tune the aggregate API quota to
expected traffic or configure a strictly trusted proxy topology, never trust
arbitrary X-Forwarded-For. One API worker is intentional: model/semaphore budgets
are per process. Multiple workers duplicate model RAM and require capacity/rate
planning. Authentication/form requests share the 5 MiB transport limit.

## Remaining operational validation

Provision TLS and a DNS name, restrict ports, use a separate least-privilege runtime
DB account after migrations, rotate secrets, review retention of account metadata,
verify restore procedures and benchmark concurrency/RAM before admitting real
users. There is no claim of OWASP certification, clinical validation or completed
DigitalOcean deployment. Android must remove BODY logging/cleartext and integrate
server-derived roles/token storage; it was not modified here.

Dependency auditing: `python scripts/audit_dependencies.py` sends only installed
package names/versions to the public OSV advisory service. CI runs this on Linux.
An unavailable/incomplete service fails the check; it never reports a clean audit
from missing results. This is a point-in-time known-advisory check, not a proof of
absence of vulnerabilities. Mako is constrained to patched 1.4.3; the legacy
1.4.1 installation was covered by GHSA-5639-2j2p-m4mx (Windows traversal).

Migration 0003 adds independent-adult ownership and immutable-at-API numeric reading
snapshots. It preserves existing child IDs and backfills scores from related
metadata documents, with no content reconstruction. A database XOR constraint
requires exactly one child/user owner. Downgrade refuses to erase adult sessions.
