# Android-compatible API contract

Login is unchanged: `POST /api/v1/auth/login`, form-urlencoded `username` and
`password`. Response: `access_token`, `refresh_token`, `token_type: bearer`, plus
additive `role: TUTOR | NINO | ADULTO_INDEPENDIENTE`. `/users/me` returns the trusted
role too. Android must attach Bearer tokens, retain them securely, refresh them and
route according to the server role; its current mock repositories do none of this.

Public registration accepts TUTOR/ADULTO_INDEPENDIENTE (legacy lowercase too).
NINO registration is forbidden publicly. A tutor creates a child profile, then
`POST /children/{id}/account` with email/password to bind a real NINO identity.
`POST /children/{id}/session` with `{}` or `{"pin":"1234"}` issues child-scoped
tokens from an authenticated owning tutor. Child login can also use the same form
endpoint. Inactive profiles/tutors cannot authenticate as children.

All following routes are prefixed `/api/v1`:

| Route | Access / behavior |
|---|---|
| POST /auth/register, /auth/login, /auth/refresh | Public credential exchange |
| POST /auth/logout | Authenticated; revoke all sessions/access versions |
| POST /auth/password | Adult; current_password/new_password, revoke sessions |
| GET /users/me | Authenticated identity |
| PATCH, DELETE /users/me | Adult; update name / deactivate |
| GET, POST /children | Tutor-owned active profiles / create |
| GET /children/me | Authenticated NINO; own accessibility/profile data |
| GET, PATCH, DELETE /children/{id} | Owning tutor; DELETE is deactivation |
| POST /children/{id}/account, /session | Owning tutor |
| POST /adaptations/text | Adult; JSON text, optional child_id and level |
| POST /adaptations/file | Adult; raw body PDF/TXT, query child_id and level |
| GET /documents, /documents/{id} | Adult-owned or assigned to authenticated child; metadata only |
| DELETE /documents/{id} | Adult owner; delete metadata/assignments, detach historical readings |
| GET /children/{id}/library | Tutor/that child; assigned metadata |
| POST /children/{id}/library | Tutor; document_id from own activity |
| DELETE /children/{id}/library/{document_id} | Owning tutor |
| POST /children/{id}/readings | Tutor/that child; assigned document_id |
| GET, PATCH /readings/{id} | Tutor/that child or independent owner; monotonic numeric progress |
| POST, GET /readings | Independent adult; start/list own sessions |
| GET /users/me/progress | Independent adult; Android SessionProgress fields |
| GET /children/{id}/readings | Tutor/that child |
| GET /children/{id}/progress | Tutor; educational progress object |
| GET /children/{id}/progress/legacy | Tutor; previous Android SessionProgress list |

Legacy progress uses `sessionLabel`, `accumulatedMinutes`, `completionPercent`. Reading
updates use `reading_time_seconds`, `completion_percent`, `completed`. The client
must not report more reading time than elapsed wall time (5-second tolerance).
Completion requires 100% and is final. Readability scores/counts cannot be supplied by clients.
Document telemetry includes scores, delta, original/adapted counts and the exception
flag. Original filenames, text and storage locations are absent.

NLP input accepts integers 1..5 and BASICO=1, INTERMEDIO=3, AVANZADO=5. The response
uses the stored integer; values 2/4 remain available without inventing new Android
enum names. Palette/difficulty strings preserve the original lowercase contract.
The current Android code has no network DTO for new endpoints: integration is
still required in its read-only repository. Its 15-second timeout may be too short
for local inference; benchmark before choosing a client timeout.

No GET endpoint retrieves an earlier document's content. Devices must resend
content when needed. SHA-256 deduplication is scoped per owner. A successful
re-adaptation updates that document's latest numerical telemetry/chunks rather
than duplicating records. Metadata survives content disappearance by design.

`/health/live` and `/health/ready` are intentionally public, content-free operational
endpoints. Readiness checks PostgreSQL and a fixed synthetic adaptation probe,
without loading weights or generating with mT5. An operative deterministic fallback
is ready even when the optional model is unavailable/not yet loaded. JSON includes
`database`, `pipeline`, `engine_mode` (`deterministic`, `hybrid`, `mt5_refinement`,
or `unavailable`), plus the lazy `model` state and `rules_fallback` when checked.
503 identifies an unavailable database or no operative configured pipeline;
input-specific 422 rejections and transient inference saturation do not make the
service globally unready. Readiness is an operational check, not a quality claim.
API errors never echo rejected field values. 401/403/404 protect identity/ownership;
413 limits size, 415 rejects format, 422 rejects malformed/empty content or invalid fields,
429 rate-limits, 503 rejects worker saturation. All responses use Cache-Control:
no-store. Use TLS and disable body logging in release and debug workflows involving
real user documents.

## Independent adult telemetry

`ADULTO_INDEPENDIENTE` uses `POST /api/v1/readings` with `{"document_id":"UUID"}`
and `GET /api/v1/readings?offset=0&limit=100` for their own history. No child profile,
birth date, diagnosis, tutor link or library assignment is fabricated. Adaptation
already accepts this role without child_id. Only owned document metadata can be
used. Tutor/NINO identities cannot create sessions through this adult endpoint.

`GET /api/v1/readings/{id}` and the existing PATCH authorize the child/tutor or the
independent owner, respectively. `GET /api/v1/users/me/progress` returns the same
SessionProgress shape as `/children/{id}/progress/legacy`. Child reading routes retain
their contracts. The default child progress response is now the educational object.
ReadingRead adds nullable reader_user_id and numeric score/count snapshots; child_id
is still populated on every child session, and is null only for independent adults.
The database requires exactly one identity source per session. API callers cannot
supply owner IDs or scores. Snapshots survive re-adaptation/deletion of documents;
legacy sessions receive available document metrics during migration, otherwise NULL.

## Best-effort readings (21 October 2026)

Valid text at every NLP level 1..5 is delivered with HTTP 200 even when its
readability target is unmet. No minimum of 20 words applies to the reading API.
The existing `adapted_text`, `document` and `chunks` fields remain compatible.
Additional response fields:

- `quality_status`: `target_met` or `best_effort`.
- `meets_readability_target`: true only when document **and every chunk** meet
  the unrounded delta >=15 and score >=65, or the existing maintenance exception.
- `warnings`: codes such as `readability_target_not_met`, `original_text_retained`,
  or `processing_budget_exceeded`; these never contain user text.

Document, chunk and reading telemetry also exposes a derived
`meets_readability_target` (null for legacy scores). A reading snapshot still
preserves its actual numeric scores if a document is later re-adapted or deleted.
A 200 response indicates a usable reading response, not a quality certification.

The original is retained if no candidate passes the fidelity guard or improves
its score. Input/format/authentication/resource limits and ownership checks still
apply. Apply Alembic revision `0004_best_effort` before serving this version;
it updates telemetry CHECK constraints without adding text storage or columns.

## Educational extension

[educational-features.md](educational-features.md) documents lesson generation,
two comprehension questions on all adaptation responses, optional reading practice
telemetry, progress summaries and five achievements. Child progress now returns
the educational object by default; the previous Android `SessionProgress[]` response
is available at `/children/{id}/progress/legacy`.
`GET /readings/progress` is the independent adult summary and is registered before
`/readings/{reading_id}` so the static path is not parsed as a UUID. `/adaptations/document`
is an additive raw PDF/TXT alias of `/adaptations/file`.

## Age-aware questions and FluiBot

All adaptation responses now include `question_age_group` (`6-8`, `9-11`, `12+`)
and nullable `child_age_years`. The age is calculated from the authorized profile's
birth date, in completed calendar years on the UTC service date. Without `child_id`,
the standard `12+` group applies. Questions add `hint` and `explanation`.

Both educational progress responses add `streak_days`, `total_gems`, `total_xp`,
`total_stars`, `current_rank_title`, `next_rank_stars`, `mascot`, six
`collectible_cards`, ten `shop_catalog` entries and `pedagogical_summary`.
The previous educational fields and both legacy list routes retain their behavior.
Rewards are derived from the authorized history: 30 welcome gems, 50 gems/100 XP
per completion and 25 gems/50 XP per correct answer. `total_stars` aliases gems;
rank thresholds refer to XP. Each shop `unlocked` flag expresses affordability.
See [educational-features.md](educational-features.md) for exact tiers and formulas.

## Factual sources, vocabulary and daily missions

`POST /adaptations/generate` accepts `custom_topic` and `target_level` alongside
`topic` and `simplification_level`; conflicting aliases return 422. Optional topic
resolution uses category context, five Spanish Wikipedia search candidates and a
3.5-second total deadline, then a 29-article factual local bank. Unsupported topics
without an available source return a sanitized 503. Existing free-text adaptation
quality thresholds continue to allow best-effort 200 responses.

Adaptation responses add `fun_fact` and `key_vocabulary` (`word`, `definition`,
`example`). Generated lessons also add `resolved_topic` and `source` containing
provider, title, URL, license information and optional revision ID. Source is null
for uploaded/free text. Generated lessons have 3–4 glossary entries; extremely
short free text may have fewer distinct useful terms.

`GET /profiles/{profile_id}/educational-progress` aliases the tutor-owned child
summary. It and the existing modern summaries add `daily_missions`, with three
items: reading completion (25 gems), at least one correct quiz answer (30), and
practice on two distinct readings (40). Items expose `id`, `title`, `description`,
`reward_gems`, `progress`, `target`, `completed`. Current goals use UTC dates;
`total_gems` includes historical completed mission bonuses once per mission/day.
XP formulas and legacy progress lists remain unchanged. Apply `0005_daily_activity`.
