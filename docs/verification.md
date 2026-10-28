# Verification — 2026-10-27, v2.2

Final local release: Python 3.14, macOS arm64 and PostgreSQL 18.

| Check | Observed result |
|---|---|
| Full PostgreSQL suite, private test schemas | **562 passed**, 347.16 s |
| Full SQLite suite | **557 passed, 5 PostgreSQL-only skips**, 307.82 s |
| Ruff check and format | 106 source files passed |
| pip check | No broken requirements |
| Alembic check / current | No drift; 0007_master_accounts, eight existing revisions |
| Live port 8000, through app.bootstrap | **200 OK**, DB and adaptation pipeline operational |
| Authenticated retained demo GET | **15/15** actual texts/scores/previews/versions/questions verified |
| Managed demo refresh | Four profiles; 15 readings; UUIDs, practice, dates, answers, gems, XP and streaks preserved; second refresh 0 |
| Hash seed stability | Identical five-level outputs from independent PYTHONHASHSEED=1 and 2 processes |
| Long repeated reading | One 20-copy Text B block: 12.84 s to 0.78 s in local timing |
| Input validation | Clear sanitized 422 messages; unsupported uploads 415; native requests and CORS preflight verified |

The final seed value recorded in model metadata was corrected to 20261027 after
these full runs. Weights, predictions, partitions and thresholds did not change;
checkpoint integrity tests were repeated afterward. No .env, virtual environment,
raw corpus, JSONL or large neural weights are staged. The released CPU JSON is
under 2 MB. Docker/Compose and the container smoke workflow use v2.2. The remote
workflow builds and exercises the actual image; no local Docker daemon or remote
DigitalOcean deployment is claimed here.

**Academic acceptance remains false.** SARI 44.53966472310678 is below baseline
44.54384786845761. Lexical top-1 is 73.25% versus 53.07%; all five score bands
hold for 13/31 catalog articles, 2/6 known EASIER cases, 5/6 controlled inputs and
7/15 demos. All demos meet their assigned level's band, and all these groups have
strict progression. These distinctions and limitations are exposed in model-info
and master overview; passing tests is not an assertion of academic or clinical
validation. See [the measured report](model-retraining-report.md).

## Historical verification records

# Verification — 2026-10-20

Observed locally on macOS arm64, Python 3.14.7 and PostgreSQL 18.6 (Postgres.app).
The clean-runner CI repair and contextual EASIER calibration phase produced:

| Check | Observed result |
|---|---|
| Full suite with TEST_DATABASE_URL, private schemas | 124 passed in 18.03 s |
| Default suite without PostgreSQL | 122 passed; 2 PostgreSQL-specific tests skipped, 12.99 s |
| Adult-owned sessions | Creation, history, progress, completion and immutable score snapshots passed |
| RBAC/IDOR and input injection | Other users cannot read/update sessions or inject owners/scores |
| Existing child contracts | Existing suite plus child snapshot compatibility passed |
| Migration of existing child sessions | Ownership preserved and exact numeric snapshot backfill passed |
| Application PostgreSQL schema | Retains 0003_adult_telemetry; no column changes or new migration in this phase |
| Alembic drift check against application database | No new upgrade operations detected |
| Application schema inspection | Adult ownership and numeric acceptance checks present |
| Python source AST parse, API import and OpenAPI | Passed; 24 OpenAPI paths |
| Ruff lint and formatting | Passed; 46 Python files formatted |
| pip check, lightweight and separate ML environments | No broken requirements |
| Prior EASIER/mT5 training evidence | 120 real LoRA steps; checkpoint hash rechecked and unchanged in this phase |
| Base/checkpoint inference and real hybrid pipeline | Six actual runs: calibrated EASIER 5/6; synthetic 10/14; separate internal audit 0/12, for either model |
| Conditional acceptance compliance | Calibration: 5/5 strict; synthetic: 8/8 strict + 2 maintenance; automatic guards pass on all accepted outputs |
| Actual HTTP readiness + application PostgreSQL | 200, engine_mode=deterministic, model=not_loaded; no weight load |
| Readiness failure paths | Missing database, unavailable configured engine and broken refiner return controlled 503 |
| Previous-phase physical E2E cleanup (2026-10-19) | Atomic DELETE of 3 inactive test users, 1 child, 2 documents, 2 readings, 1 assignment, 2 chunks, 6 refresh tokens |
| Model control markers | Rejected in runtime fidelity and offline readability evaluation |
| Tracked-only clean checkout | Ruff lint/format passed with pinned 0.17.1; explicit third-party datasets classification |
| Current lightweight dependency audit | 48 installed packages, no known advisories returned by OSV |

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
the six EASIER cases now inform rules directly and are a calibration set, not a
holdout. The new 12-document internal audit excludes those cases and remains 0/12. The 14-case synthetic fixture is also a developer diagnostic, not an
independent benchmark or evidence of semantic/clinical efficacy.


## CI repair evidence

The [b8360e2 Actions run](https://github.com/juanchito3110/fluilet-backend/actions/runs/39360655050)
failed Ubuntu portable at Ruff and PostgreSQL at container creation before checkout.
The matrix then canceled the other portable jobs. A tracked-only checkout reproduced
I001 in ml_training/train.py: the ignored local datasets/ directory made Ruff treat
the third-party datasets package as first party. Explicit isort classification and
a common import block fix this in both environments. Ruff is pinned to 0.17.1.

The service health command now uses double quotes, matching GitHub's documented
PostgreSQL example, instead of single quotes in Docker options. Ubuntu is pinned
to 24.04, Actions are updated to checkout 7.0.1/setup-python 7.0.0, portable fail-fast
is disabled and UTF-8/optional-model configuration is explicit. No lint, test,
migration, pip check or advisory check was disabled to obtain a passing result.

Local Docker execution is unavailable because its daemon is stopped. The fixed
service initialization and the Python 3.12 Windows/macOS/Linux jobs must be checked
in the Actions run triggered by this push; local checks above use Python 3.14.7.


## Factual lessons and daily missions — 2026-10-25 (Mexico City)

This update was verified locally with Python 3.14.7:

- Full PostgreSQL suite: **396 passed** on the dedicated test instance at port
  55439, using private schemas; no test learner was added to the application DB.
- SQLite portable suite: **394 passed, 2 skipped** (PostgreSQL-only checks).
- Ruff checks/formatting and `pip check`: passed.
- Application PostgreSQL: schema-only private backup, upgrade to
  **0005_daily_activity**, and `alembic check` with no drift.
- Server restarted on port **8000**; `/health/ready` returned 200, operational
  PostgreSQL and `engine_mode=deterministic`. OpenAPI exposes the new topic/level
  aliases, source, vocabulary, fact, daily missions and profile progress alias.
- Separate real Wikipedia API lookups selected Real Madrid Club de Fútbol and
  Biología marina. Automated tests remain offline with mocked Wikipedia transport;
  they cover five-candidate disambiguation, source attribution, timeout, API
  failures and bounded responses.

Regression coverage includes actual club/marine/Egyptian/Olympic facts at levels
1, 3 and 5, glossary terms present in the delivered reading, two grounded questions,
unknown-topic 503 without filler or retention, age-sensitive safe clause boundaries,
mission ownership for child/adult, midnight resets with historical gems, late quiz,
repeated PATCH/GET and content-hash deduplication after document re-upload.
Migration tests exercise inferred legacy backfill and refuse destructive downgrade
when new daily activity exists. These are software correctness checks, not an
independent factual audit of Wikipedia or a clinical comprehension study.


## Academic review contract — 26 October 2026

- Android `b822b85` inspected read-only. Glossary, fact and mission wire names
  match; original/claimed consumption and client-local reward reconciliation are
  explicitly identified as remaining Android work in `academic-demo.md`.
- Explicit owner authorization superseded Zero Retention for originals, adapted
  readings and their complete educational responses. `adaptation_contents` stores
  versions by document/profile/level/group. Tests verify database retrieval after
  ORM identity eviction, isolated versions, deletion cascade, owner/profile/library
  access, and absence of content in unrelated tables or logs.
- Full PostgreSQL suite: **420 passed**. SQLite: **417 passed, 3 skipped**
  (PostgreSQL-only migration, row-lock concurrency and database constraints).
- Ruff, format checks and `pip check`: passed.
- Dedicated PostgreSQL test instance used private disposable schemas, never the
  application profile history. Seed tests verify six retained lessons, seven
  consecutive dates, real measured NLP scores, explicit demo flags, ascending
  synthetic comprehension, stage 4, more than 260 gems, idempotent claims, repeated
  and concurrent seeds, and preservation of genuine readings/preferences.
- Application schema-only private backup verified; migration
  **0006_academic_review** applied; `alembic check` reports no drift. No previously
  discarded source is reconstructed. No application profile was seeded implicitly.
- API restarted on port **8000**; readiness **200**, PostgreSQL operational and
  deterministic engine operational. OpenAPI verifies comparison, retrieval,
  seed-demo and claim endpoints.

See `academic-demo.md` for the actual local score comparison. Those improvements
remain below the combined readability target and are honestly marked best effort.
Synthetic comprehension and rewards are demonstration data, not validation of
educational or clinical efficacy. Full client UI synchronization cannot be claimed
without consuming the added original/claimed fields in Android.


## Managed academic accounts and master administration — 27 October 2026

- Full PostgreSQL suite: **429 passed**. SQLite: **425 passed, 4 skipped**
  (PostgreSQL-only migrations/constraints/cross-session concurrency).
- Real form login tests cover the tutor and master, normal public registration,
  master claim denial at registration, email-only privilege denial and all admin
  route access checks. Startup and concurrent restoration create one cohort and
  preserve manual accounts/profiles, passwords, practice and resource changes.
- Phase tests verify four profiles, stages 1..4, exact 45/160/340/900 gems and
  40/190/460/980 XP, 1/3/6/12 configured streaks, 1/3/5/6 completed readings,
  Valentina's 95 percent synthetic comprehension and unlocked rewards, and all
  fifteen real retained lesson comparisons/questions/glossaries/facts.
- Master tests cover all four stage changes, signed grants, level/teaching-age
  overrides, zero-balance validation, future earned resources, one-time unlock
  rewards, hashed parental PIN reset/verification, physical profile/user cascades
  including linked NINO identities/tokens, and protected-master deletion.
- Migration tests verify additive MASTER_ADMIN enum, schema consistency, safe
  legacy upgrade and refusal to downgrade populated master/demo controls. Ruff,
  format check and `pip check` passed.
- Active local PostgreSQL: private schema-only backup verified; migration
  **0007_master_accounts** applied; `alembic check` reports no drift. Reserved
  demo addresses were absent before provisioning; existing manual users were not
  converted or deleted.
- Server restarted on **8000**. Startup created the two accounts and four phase
  profiles in the active database. Actual HTTP form login verified TUTOR/false and
  master_admin/true, parental PIN validity, global overview and all four exact
  phase summaries. All fifteen retained demo readings were fetched over HTTP and
  verified complete and at their own profile levels. Explicit restoration then
  returned **200 with identical profiles/history/resource totals**.
- Readiness returned **200**, database and deterministic engine operational,
  optional model still not loaded. No test account or synthetic history was added
  to the application database beyond the expressly requested managed demo cohort.

`docs/demo-accounts.md` explains why the requested resource/streak presets require
explicit adjustments over the normal reward formula. `has_admin_adjustments`
discloses them; no readability score or birth date is falsified. Synthetic account
history is not evidence of clinical efficacy. Android was not modified.

## Pedagogical rewriting and five-level comparisons — 27 October 2026

- Full PostgreSQL suite: **474 passed**. SQLite: **470 passed, 4 skipped**
  (PostgreSQL-only checks). After the final contextual single-occurrence guard,
  all **45 pedagogical engine tests** passed again. Ruff, format checks and
  `pip check` passed.
- Coverage includes the complete 31-article bank, all five measured previews,
  exact source preservation, three adaptation POST routes and version retrieval,
  honest local/remote attribution, legacy read-only enrichment, contextual SGSS
  selection, missing corpus fallback, syntax/negation/date guards, and idempotent
  demo refresh with unchanged practice and resource totals.
- The local SGSS file yielded **5,130 rows**, **7,876 indexed candidates** and
  **397 curated pairs**. The 120-step checkpoint was inventoried without loading
  its weights or automatically activating an unsuccessful training experiment.
- Reproducible evaluation found strict five-level progression on **31/31 local
  calibration articles**. The separate six-case EASIER sample achieved the legacy
  double condition on **5/6** at level 1, but strict progression on **0/6**.
  Neither sample is a held-out generalization or comprehension validation;
  exact pedagogical score/length bands are not universally attained. See
  [the measured report](pedagogical-simplification.md).
- All **15 marked readings** in active PostgreSQL were refreshed. Adaptation IDs,
  dates, comprehension, gem/XP balances and streak configuration were preserved;
  the second refresh made zero changes. Genuine unmarked practice was excluded.
- The existing JSON columns retain the added comparisons/previews. Schema remains
  **0007_master_accounts**; `alembic check` reports no new operations.
- Server restarted on **8000**, readiness **200**, database and deterministic
  pipeline operational. Authenticated HTTP retrieval verified all fifteen retained
  demo versions, actual measured gains, populated replacements and five previews.
- Docker includes only the shared lightweight CSV reader in addition to runtime
  code. Corpus/checkpoint mounts remain optional and excluded from Git/image
  context. No Docker image build was performed in this environment.

## Dataset v2, fitted contextual ranker and live checkpoint — 27 October 2026

- Full PostgreSQL suite: **494 passed**. Full SQLite: **490 passed, 4 skipped**.
  Twenty new tests cover fitted/checksummed weights, deterministic data building,
  partition separation, morphology, all twelve fixed diagnostics, real TXT/PDF
  inference, authenticated model-info routing and exclusion of held-out SGSS
  labels/frequencies. Existing route tests also verify model provenance and the
  master overview. Ruff, formatting and `pip check` passed.
- Dataset v2: **3,220 pairs**, train/validation/test **2,588/404/228**; full
  unfiltered v1 derivation **7,704**, previous smoke selection **34**. The v2
  includes 900 explicitly synthetic morphological examples and 36 syntactic
  parallels. The known six diagnostic documents and their observed families
  are quarantined from fitting. The split audit is over recorded source,
  document and family keys, not a universal semantic-duplicate detector.
- Real CPU SGD: **20 epochs, 52 fitted coefficients**. Train loss
  **0.485250 → 0.431136**, validation loss **0.469675 → 0.418884**. Changed finite
  weights and byte-identical local/released checkpoint copies were verified.
  This is a logistic candidate ranker, not a new mT5 fine-tune.
- Re-executed archived baseline `b342076` using the same SGSS and inputs.
  End-to-end progression: EASIER **0/6 → 6/6**, newly authored controlled inputs
  **0/6 → 6/6**. New-input SARI **79.669 → 83.120**, average gain
  **23.695 → 26.574**. Exact bands and double-condition acceptance are separate:
  v2 **5/6** EASIER and **2/6** new inputs satisfy the latter.
- The isolated initial-weight/trained-weight ablation on 228 examples is
  **44.544 → 44.501 SARI**; candidate-classification F1 is **0.391**. The report
  discloses that the learned weights did not improve aggregate SARI. Known
  diagnostics and small controlled inputs do not prove open-domain or clinical
  generalization. Unsupported inputs retain truthful best-effort delivery.
- All **15 retained managed lessons** were regenerated with v2 provenance.
  Only one reading needed a changed numeric snapshot; other scores stayed the
  same. Dates, responses, completion, reading times, gem/XP balances and streaks
  were preserved. Repeating refresh changed zero readings.
- Active PostgreSQL remains at **0007_master_accounts**; `alembic check` reports
  no new operations. No column or migration was needed.
- Server restarted on **8000**, readiness **200**. Actual authenticated HTTP
  verified model-info, master overview and all fifteen retained versions with
  `context-ranker-es-v2`, populated replacements and progressive previews.
- `checkpoints/retraining_metrics.json` is explicitly versioned. Corpus,
  derived JSONL, environments, secrets and large weights remain ignored. The
  small released JSON ranker uses LF line endings for portable fingerprints.

See [model-retraining-report.md](model-retraining-report.md) for reproducible
commands, all measured comparisons, source attribution and limitations.


## v2.1 requested-level contract, joint fit and deployment bootstrap

- Full PostgreSQL: **538 passed**. SQLite: **533 passed, 5 skipped**. Six bootstrap
  tests passed again after using `sys.executable`. Ruff/format and `pip check`
  pass. API cases cover levels 1..5 on every text/generation/file route, age-only
  1/3/5 selection, explicit teaching age over profile defaults without changing
  birthdays, conflicting aliases, and retained version isolation.
- Joint dataset: **4,738 pairs**, partitions **4,108/402/228** with recorded-key
  leakage checks. Actual training: **35 SGD epochs + 25 residual-tree rounds**,
  31 features, 155 linear coefficients and shared depth-3 residual trees. Policy
  and SARI mixture fit validation only; the frozen baseline executes fc12a7a.
- Critical acceptance remains **false**: baseline SARI **44.543848**, trained
  **44.529243**. Lexical top-1 improves **53.07% → 61.84%**, band distance improves
  **22.506362 → 22.456644**. Neither metric is substituted for failed SARI.
- Strict progression: local bank **31/31**, known EASIER **6/6**, controlled inputs
  **6/6**. All five score bands: **4/31**, **1/6**, **0/6**, respectively. Managed
  demo target levels meet their score band on **13/15** readings. This is known
  diagnostic/developer calibration, not independent comprehension validation.
- All **15 managed retained lessons** now use v2.1; **11 numeric snapshots** changed.
  Dates, reading times, answers, resources and streak settings were verified
  unchanged. Repeat refresh made zero changes. HTTP retrieval verified the real
  primary text/score against each requested preview and retained content.
- Local server started through `app.bootstrap`, readiness **200**. Authenticated
  model-info/admin overview returned v2.1 with the released checksum and unmet
  acceptance flag. Model loading validates JSON weights/trees, explicit paths and
  optional SHA pins; source-layout testing succeeds without corpus/Torch/NumPy.
- Production startup serializes `alembic upgrade head` before exec; eight actual
  revisions were applied twice in an empty private PostgreSQL schema and checked
  for drift. Head remains **0007_master_accounts**, no new columns/migration.
- Production requires private tutor/master credentials instead of public academic
  defaults. Local development retains the requested defaults. Compose rendering
  and shell syntax pass. Docker's local daemon is unavailable; a new Linux CI job
  builds the real image and smoke-tests migrations, demo login, checkpoint hash
  and version retention on ephemeral PostgreSQL 18 with a read-only API container.
- Corpus derivatives, secrets, environments and large weights stay ignored. The
  small v2.1 JSON release and numeric `checkpoints/retraining_metrics.json` are
  intentionally versioned. Android and DigitalOcean accounts were not modified.

See [the v2.1 report](model-retraining-report.md) and [deployment notes](../deploy/README.md).
