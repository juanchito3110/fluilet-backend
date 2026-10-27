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

## Authorized content retention (26 October 2026)

Content is received in RAM with bounded streaming, then decoded/extracted and
processed without file queues. After successful adaptation, the explicitly
authorized source, output and educational response are stored in
`adaptation_contents`. This supersedes the earlier Zero Retention policy; it is
not a metadata-only database anymore. Raw file bodies avoid Starlette's
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
model buffers are not securely erasable; there is no claim of forensic RAM erasure.
Retained versions persist in PostgreSQL and its storage/backups until deleted. A timed-out native inference thread retains its slot and
input until it actually completes; requests never launch unbounded replacement
threads. PDF workers are terminated on timeout/cancellation. Serving has no prompt
cache. Model weights and explicitly licensed offline training data are not user
uploads and are intentionally separate artifacts.

Host swap/hibernation, crash/core dumps, container checkpoints, snapshots of live
RAM and monitoring agents can persist process memory. Disable these on the VPS,
where the deployment policy requires limiting incidental memory persistence.
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

Migration 0004 separates quality thresholds from telemetry integrity. Documents,
chunks and sessions may record truthful below-target scores, including delta=0.
Non-null snapshots, positive counts, finite bounded scores, the exact delta and
maintenance-exception consistency remain enforced. No text columns are added.
Downgrade refuses when a best-effort snapshot would violate the previous schema;
it never deletes readings to force a rollback. Existing qualifying snapshots and
legacy null snapshots survive an upgrade/downgrade round trip.

Educational progress migration `0004_educational_progress` adds numeric practice
telemetry and normalized category/level snapshots. That revision did not store topics, generated titles,
questions or source/adapted text; revision 0006 now stores authorized lesson content. New summaries retain owner/profile
scoping and derived progress is read-only. Practice counters are client-reported;
score consistency checks do not prove a learner's answers. Question metadata must
remain outside external body logs just like the adapted text. Downgrade refuses to
discard populated educational metadata.

Age-aware questions read birth dates only after the existing active-profile and
owner checks. Responses expose completed years rather than a birth date. Hints,
explanations and age-group choices are included in retained adaptation responses. FluiBot's counters, cards,
catalog and practice suggestions are computed from the already owner-scoped
sessions, with no per-request reward writes or shared learner cache. The game
metadata uses the same client-reported practice figures as the educational summary.


## Encyclopedic retrieval and daily activity

Only the explicitly requested generation topic is sent to the fixed Spanish
Wikipedia Action API host. It uses POST, bounded response streaming (256 KiB),
no redirects, four concurrent slots and a total 3.5-second deadline. User documents
and free-text adaptation bodies are never forwarded to Wikipedia. Disable the
lookup with `WIKIPEDIA_ENABLED=false` where network disclosure of generation topics
is unsuitable. Do not add HTTP body tracing; standard request URLs contain no topic.
Extracts and source metadata are retained in the authorized lesson record and
returned with Cache-Control: no-store.
Source attribution includes the Wikipedia license and revision when available.

Migration `0005_daily_activity` stores session/date activity flags and a content
hash, without titles, topics, article excerpts or questions. Joins use the same
child/adult ownership scope as the summary. Composite keys make repeated updates
idempotent; summaries perform no writes. Historical dates inferred from legacy
session snapshots are explicitly marked. Downgrade refuses to discard newly
observed activity. Hash matching has the same dictionary-attack limitation as
existing document hashes and is not an anonymity guarantee. Mission rewards rely
on client-reported practice; they are not proof of quiz correctness.


## Revision 0006: access and synthetic demo scope

`0006_academic_review` adds retained content versions and nullable unique per-child
demo slots. It does not reconstruct historical uploads. Versions are deduplicated
by document/profile/level/group context and stored transactionally with document
metadata. Source and output use dedicated text columns; the JSON payload retains
questions, definitions, sources and numerical snapshots. GET checks document owner
or library assignment, then profile identity/activity. UUID secrecy is not used as
a permission check. Deleting a document or hard-deleting its owner cascades content;
profile deactivation removes access without claiming physical erasure. Account
DELETE remains deactivation under the existing contract. Database backups may
still contain retained content and require an operator-defined retention policy.

The academic seed is authenticated, tutor-owned and explicitly marks synthetic
comprehension/history. It never silently treats these as measured learner outcomes.
Row locks and unique slots prevent duplicate cohorts. Its dates are anchored on
first creation, and it does not change genuine sessions or profile preferences.
Readability scores are computed from the actual authored lesson pairs. Downgrade
refuses when retained content or demo markers exist; it does not delete content or
history to force a schema rollback. Claim acknowledges already-derived rewards and
has no second payout. No unrelated data or test account is inserted in the manual
application database during automated tests.


## Master/demo identities — revision 0007

The owner explicitly requested fixed academic accounts and physical deletion
capabilities. Startup provisioning is enabled by default and can be omitted with
`DEMO_ACCOUNTS_ENABLED=false`. The two known demonstration passwords and parental
PIN are intentionally public defaults, processed by the same bcrypt/form/JWT
code as every account. The flag controls provisioning, not deletion of existing
accounts. No generated runtime secret or database credential is committed.

Public registration cannot create a master, set its managed marker, or claim
reserved emails. An unmarked conflicting address fails closed instead of being
promoted. Master routes require active stored identity/role/marker/email; a claimed
email or forged client flag is insufficient. JWT role/version checks, refresh
rotation and identity lookup are preserved. Startup restoring a changed demo
password/reactivating its account revokes old tokens. PIN hashes never leave the
API; verification is under the existing authentication throttle.

PostgreSQL transaction advisory locks serialize provisioning and admin mutations;
profile grants additionally lock the owner/profile in the same order as content
persistence. Markers/unique constraints prevent duplicate identities/cohorts.
Resources are bounded, persisted differences over real reward history, explicitly
flagged in the response. Readability scores and birth dates are not falsified.
SQL/body logs remain suppressed. Overview exposes global account/profile metadata
only to the master. Cascade deletions remove profile content, activity, controls,
linked child identities and tokens without deleting shared lessons from other
profiles. The protected master cannot delete itself, including ordinary self-delete
routes. Account/profile deactivation contracts remain unchanged for ordinary users.

The role enum is extended additively. Downgrade refuses to discard populated
master markers, PINs, age overrides or controls. An unused PostgreSQL enum label
is retained on clean downgrade to avoid destructive type replacement.
