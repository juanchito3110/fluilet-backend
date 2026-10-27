# Android-compatible API contract

Login is unchanged: `POST /api/v1/auth/login`, form-urlencoded `username` and
`password`. Response: `access_token`, `refresh_token`, `token_type: bearer`, plus
additive `role: TUTOR | NINO | ADULTO_INDEPENDIENTE`. `/users/me` returns the trusted
role too. Android must attach Bearer tokens, retain them securely, refresh them and
route according to the server role. Android was inspected at commit `b822b85`.

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
| DELETE /documents/{id} | Adult owner; delete metadata/content/assignments, detach historical readings |
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
flag. Original filenames and storage locations are absent from document metadata. Reading
content is now retained separately in `adaptation_contents` under the same owner.

NLP input accepts integers 1..5 and BASICO=1, INTERMEDIO=3, AVANZADO=5. The response
uses the stored integer; values 2/4 remain available without inventing new Android
enum names. Palette/difficulty strings preserve the original lowercase contract.
Android `b822b85` uses the existing network DTOs and a 190-second adaptation timeout.
It continues to use `document.id` for sessions. The new root adaptation `id` is a
separate UUID. SHA-256 deduplication remains scoped per owner. Re-adaptation updates
latest document telemetry/chunks but retains distinct content versions per
(document, child or adult context, target level, age group). A repeat for the same
context upserts that version. Old pre-retention metadata cannot reconstruct lost
manual text and returns 404 until adapted again.

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
the explicit `age_group` applies, defaulting to `12+`. Questions add `hint` and `explanation`.

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
3.5-second total deadline, then a 31-article factual local bank. Unsupported topics
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


## Academic review contract — 26 October 2026

All text/file/generated adaptations return the following additive fields:

| Field | Meaning |
|---|---|
| `id` | Retained adaptation UUID; distinct from `document.id` |
| `original_text` | Complete cleaned source submitted to NLP, nonempty |
| `adapted_text` | Actual delivered simplification or truthful free-text fallback |
| `original_readability_score`, `readability_score` | Raw, unrounded Szigriszt-Pazos floats |
| `metrics.original_szigriszt_pazos`, `metrics.adapted_szigriszt_pazos`, `metrics.score_delta` | Exact comparable scores and difference |
| `metrics.original_word_count`, `metrics.adapted_word_count` | Counts from each delivered text |
| `metrics.original_sentence_count`, `metrics.adapted_sentence_count` | Sentence counts |
| `metrics.original_average_words_per_sentence`, `metrics.adapted_average_words_per_sentence` | Actual word count / sentence count |
| `target_level`, `age_group` | Requested level and effective `6-8`, `9-11` or `12+` group |
| `fun_fact`, `key_vocabulary`, `comprehension_questions` | Existing real text-grounded enriched fields |

A profile's trusted birthday overrides `age_group`; without a profile it selects
the teaching group without fabricating `child_age_years`. `POST /adaptations`
aliases `/adaptations/text` and accepts `text`, `target_level` or existing
`nivel_simplificacion_nlp`, optional `child_id` and `age_group`. Conflicting level
aliases return 422. Generated lessons require a faithful, actually improved pair;
if Wikipedia's source cannot improve, a known authored local source may replace it
with accurate source attribution. If neither can improve, generation returns a
controlled 503; it never changes punctuation solely to claim a numerical gain.
Free-text best-effort 200 behavior remains unchanged. Tiny free inputs can have
fewer than three distinct meaningful glossary terms.

`GET /adaptations/{id}` loads the entire retained response from PostgreSQL;
owner/tutor/active-child/library authorization is checked again. Document UUIDs
also work as a latest-version alias. Deleted documents cascade-delete content.
Inactive accounts/profiles cannot use these endpoints. Legacy lost content is not
invented. Retention is explicitly authorized for manual text as well as public
lessons; no response/body/SQL parameter logging is enabled.

Daily mission DTO fields exactly match Android's `id`, `title`, `description`,
`reward_gems`, `progress`, `target`, and add `completed` and `claimed`. Since the
server automatically credits a completed mission once per date, `claimed` equals
`completed`. POST `/profiles/{profile_id}/daily-missions/{mission_id}/claim` returns
the full progress object; completed missions return 200 without a second payout,
pending missions 409 and unknown missions 404. Existing 25/30/40 rewards and mission
objectives remain unchanged. `current_streak_days` counts consecutive UTC days
through today or yesterday; legacy `streak_days` retains its distinct-date count.

POST `/profiles/{profile_id}/seed-demo` is for the owning tutor only. It returns
`EducationalProgress` plus `demo_lessons` containing six complete retained readings.
It seeds Real Madrid, Biología Marina, Agujeros Negros, Antiguo Egipto, Robots e
Inteligencia Artificial and **El Viaje del Pequeño Faro**, an original fictional
tale that explicitly distinguishes its characters from real lighthouse facts.
Seven completion dates span the first invocation's last seven UTC dates, levels
1..4, synthetic comprehension 65/75/80/85/90/100/100, and measured NLP score pairs.
The repeated football practice on day seven is measured at level 4. `demo_data`
and each history/session `is_demo` identify synthetic practice; demo slots are
unique per child. No real session or profile preference is overwritten, and dates
are not rolled forward on repeat calls. Base rewards alone exceed 260 gems and
700 XP. Concurrent requests serialize under owner/profile locks. The same version
is reused for repeated lesson preparation.

**Android scope:** `b822b85` was read only. Its DTO accepts `fun_fact` and
`key_vocabulary` (`word`, `definition`, `example`) and all existing mission names.
It does not parse `original_text` or `claimed`, nor call the new endpoints. Its
local claim logic can add a reward already included by the server. The backend's
idempotent claim cannot remove that client-local duplicate: the client must consume
server `claimed` and avoid a local second payout before claiming end-to-end reward
synchronization. New response fields are additive and ignored by its current Gson
DTOs. Backend tests cover the wire contract, not an unmodified emulator's new UI.


## Master accounts and curated phases — 27 October 2026

`0007_master_accounts` adds `master_admin` as an internal role. Existing public
TUTOR/ADULTO registration and all previous role strings are unchanged. The internal
role and reserved demo emails are rejected by public registration. Login/refresh
responses add `is_master_admin`; `/users/me` and the additive `/auth/me` expose it
and `has_parental_pin`. Master authorization checks the stored role **and** managed
identity, not an email supplied by a client. No password/PIN hash is exposed.

Startup ensures two marked academic accounts and four phase profiles. Read
[demo-accounts.md](demo-accounts.md) for the exact credentials and preservation
policy. New master routes are `GET /admin/overview`, POST `/admin/ensure-demo-accounts`,
POST `/admin/profiles/{id}/grant`, DELETE `/admin/profiles/{id}`, DELETE
`/admin/tutors/{id}`, POST `/admin/tutors/{id}/reset-pin`. All require the real master;
tutor/adult/child roles receive 403. The maestro's deletion returns 400. Deletions
are physical cascades, unlike existing self/profile deactivation routes.

Profile/progress responses add `age_group` and `current_level`; progress also adds
`has_admin_adjustments`. Profile controls persist signed gem/XP differences,
optional exact level/streak and reward unlock overrides. Totals may now be zero
instead of always at least 30 after a master adjustment. Readability snapshots,
measured completion counts and birth dates are never rewritten to simulate grants.
The optional age override affects teaching and questions, while reported calendar
age stays truthful. Normal future practice still earns rewards above the adjusted
balance. Existing Android fields remain available; this update does not add client
screens or client handling of the new master role.

POST `/auth/verify-parental-pin` is authenticated as tutor, accepts a 4–6 digit PIN,
and returns a validity boolean. Existing authentication rate limiting also covers
this route. All default academic passwords/PINs are hashed and use the normal
login verifier; there is no hardcoded demo-login bypass.
