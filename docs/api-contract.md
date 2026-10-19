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
| PATCH /readings/{id} | Tutor/that child; monotonic numeric progress |
| GET /children/{id}/readings | Tutor/that child |
| GET /children/{id}/progress | Tutor; Android SessionProgress fields |

Progress uses `sessionLabel`, `accumulatedMinutes`, `completionPercent`. Reading
updates use `reading_time_seconds`, `completion_percent`, `completed`. The client
must not report more reading time than elapsed wall time (5-second tolerance).
Completion requires 100% and is final. Scores/counts cannot be supplied by clients.
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
endpoints. Readiness checks PostgreSQL and reports the lazy model state/fallback.
API errors never echo rejected field values. 401/403/404 protect identity/ownership;
413 limits size, 415 rejects format, 422 rejects invalid/unacceptable adaptations,
429 rate-limits, 503 rejects worker saturation. All responses use Cache-Control:
no-store. Use TLS and disable body logging in release and debug workflows involving
real user documents.
