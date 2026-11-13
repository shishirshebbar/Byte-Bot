# Byte Bot implementation progress

Entries below are dated historical records. Local `.cache/` screenshots, reports, and timings are intentionally excluded from GitHub; regenerate them using [testing](testing.md) and [demo](demo.md). The latest entry records repository preparation.

## Preparation

The interrupted first implementation attempt left frontend and backend dependency manifests, a frontend lockfile and HTML shell, and empty app, migration, and test directories. The preparation pass adds the local setup configuration, copied PRD, and agent guides.

The earlier attempt also started a temporary PostgreSQL container named `bytebot-mvp-pg` on loopback port `55432`. It may still be running. Check the port before starting Compose, and follow the [README port instructions](../README.md#prerequisites) if needed. No live Gemini credentials were configured during preparation.

### Preparation checks

- `docker compose --env-file .env.example config --quiet` passed. The rendered config specifies PostgreSQL 16, loopback port `55432`, a named volume, and a health check. This check starts no services.
- `npm --prefix frontend ls --depth=0` passed. Installed Python package versions matched the pinned base, OCR, and development requirements in the existing Python 3.12 virtual environment.
- The PRD copy matches the original byte for byte. A read-only documentation check verified relative links, all five phase guides and exit checklists, AT-01 through AT-12, and seeded scenarios A through E.
- Feature source, migration, and test directories are empty. Application, OCR, and live Gemini verification are tracked by the implementation phases.

## Phase status

| Phase | Status | Exit evidence |
| --- | --- | --- |
| [01 Foundation](phases/01-foundation.md) | Complete | 2026-11-13: 7 integration tests, frontend build, and browser smoke passed; see entry below. |
| [02 Guided investigation](phases/02-guided-investigation.md) | Complete | 2026-11-13: 28 tests, build, real CPU OCR, and both browser suites passed; see entry below. |
| [03 Analysis and results](phases/03-analysis-and-results.md) | Complete | 2026-11-13: 59 tests, frontend build, and three browser suites passed; optional live Gemini pending configuration. |
| [04 Reports and follow-up](phases/04-reports-and-follow-up.md) | Complete | 2026-11-13: 74 backend tests, frontend build, and all four browser suites passed; AT-12 and remaining AT-10 verified. |
| [05 Hardening and demo](phases/05-hardening-and-demo.md) | Complete | 2026-11-13: 94 backend tests, frontend build, five browser suites, real CPU OCR, reset races/isolation, and fresh-reset screenshot rehearsal passed. |

Phases 01–05 are complete. Deterministic MVP acceptance passes; optional live Gemini verification remains pending local key/model configuration. No additional feature phase is authorized.

## Update template

Copy this checklist into a dated progress entry after an implementation pass.

- Phase and status
- Files and behavior delivered
- Commands run and results
- Acceptance cases verified and evidence links
- Pending checks, dependencies, or decisions
- Next authorized step

## 2026-11-13 — Phase 01 Foundation complete

Authorized by the user's “Implement the plan” instruction after review of the Phase 01 plan. Port 55433 was explicitly selected during planning.

### Delivered

- FastAPI entry point, root dotenv settings, lifespan-managed psycopg pool, database readiness, safe API errors, and non-cacheable API responses.
- Serialized, checksum-checked SQL migrations with atomic version tracking; initial users, hashed opaque sessions, templates, and owner-scoped transaction schema. Amounts use integer paise; timestamps use `timestamptz`.
- Explicit migrate/seed CLI and three idempotent synthetic templates. Session creation atomically copies successful, pending, and failed incoming transactions; repeated requests preserve owned records.
- Typed list/detail APIs with parameterized ownership queries. Foreign and unknown valid IDs return identical 404 responses. Cookie is HttpOnly, SameSite=Lax, and configurable Secure for HTTPS.
- React history/detail screens with real database statuses, INR formatting, IST timestamps, direct reload and navigation, loading/error/retry states, and demo provenance. Pending/failed wording never claims funds were received.
- Root pytest configuration, integration tests, reusable browser smoke script, and updated README instructions. Existing manifests, lockfile, HTML shell, TypeScript configuration, Vite proxy, and Compose configuration were reused; only python-dotenv was added to base requirements.

### Commands and results

Commands ran from the project root unless noted:

- `uv python install 3.12` — passed; Python 3.12.16 available through uv. The initial environment had Python 3.14 and no project virtual environment.
- `uv venv --python 3.12 .venv` — passed.
- `uv pip install --python .venv/bin/python -r backend/requirements-dev.txt python-dotenv==1.2.1` — passed.
- `uv pip install --python .venv/bin/python pip` — passed; enables README pip commands in this uv-created environment.
- Local `.env` created from the example with `BYTEBOT_DB_PORT`, `DATABASE_URL`, and `TEST_DATABASE_URL` ports all set to 55433. No provider credentials configured.
- `docker compose config --quiet` — passed.
- `docker compose up -d --wait db` — passed; PostgreSQL 16 healthy at `127.0.0.1:55433`.
- `docker compose exec -T db createdb -U bytebot bytebot_test` — passed; separate test database created.
- From `backend/`: `../.venv/bin/python -m bytebot.cli migrate` twice, then `../.venv/bin/python -m bytebot.cli seed` twice — all passed.
- `.venv/bin/python -m pytest backend/tests -q` — **7 passed**, final run 0.50s. Covers fresh/repeated/concurrent migration application, rollback and checksum rejection, seed repeatability, session persistence across app restart, statuses/amounts/timestamps, cookie flags/hash storage, cross-session 404, malformed IDs, invalid cookie replacement, missing-template atomicity, database constraints, and safe database-failure responses. Tests only reset the explicitly guarded `bytebot_test` database.
- `npm --prefix frontend run build` — passed TypeScript and Vite production build. Vite emitted dependency-level React Router `use client` directive warnings; bundle generation succeeded.
- From `backend/`: `../.venv/bin/python -m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log` — API started successfully.
- `npm --prefix frontend run dev -- --host 127.0.0.1` — frontend started successfully at `http://127.0.0.1:5173/`.
- Initial browser attempt found no installed Chromium; `.venv/bin/python -m playwright install chromium` passed.
- `.venv/bin/python backend/tests/browser_smoke.py` — passed successful/pending/failed details, direct reload, browser back/forward, cross-session unavailable detail, API error/retry, keyboard link focus, and mobile overflow checks; no page errors. Desktop viewport 1280×900; mobile 390×844.
- Visually inspected desktop history (local artifact `.cache/phase01/history-desktop.png`) and mobile detail (local artifact `.cache/phase01/detail-mobile.png`); readable status labels, complete facts, and no clipped content. Mobile history (local artifact `.cache/phase01/history-mobile.png`) also captured. These local generated artifacts are ignored by version control.
- `docker compose ps` — new database healthy on 55433. `docker ps --filter name=bytebot-mvp-pg --format '{{.Names}} {{.Status}} {{.Ports}}'` — original temporary container remains running on 55432, untouched.

### Exit criteria and next step

All Phase 01 exit criteria passed: migration/seed repeatability, fresh-session browsing and reload, all actual status labels, cross-session transaction isolation (Phase 01 portion of AT-10), and recorded test/build results. FR-01 and Phase 01 transaction-facts portion of FR-07 delivered; analysis of unavailable facts remains Phase 03.

No Phase 01 verification is pending. The API, Vite server, and new Compose database are left running for review. No Git metadata exists in this workspace, so no commit was created. Guided intake, evidence, analysis, reports, incident management, and reset remain deferred. Next step is Phase 02 only after authorization.


## 2026-11-13 — Phase 02 Guided investigation complete

Authorized by the user's “Implement the plan” instruction following the Phase 02 plan. Only Phase 02 was implemented.

### Delivered

- Migration 002 adds one investigation per owned transaction, a composite owner/transaction foreign key, saved typed context, evidence, revision counters, timestamps, and constrained evidence review states. Migration 001 remains unchanged.
- Create/reopen, read, context save, JSON text submission, multipart screenshot submission, correction/confirmation, and physical evidence removal APIs. The case response includes authoritative transaction facts, context, evidence, and `analysis=null`. All resource operations use lookup-only demo-session ownership. Missing/foreign resources and evidence attached to another case return the same safe 404.
- Context preserves yes/no/unknown, unanswered versus explicitly empty multi-select answers, contact channels, destination claims, pressure tactics, and whether money was already sent. Revision-checked writes serialize under a row lock; stale changes return 409 without modifying data, while identical saves preserve the revision. OCR happens outside the database transaction, with ownership and revision rechecked before saving.
- Credential-labelled text is normalized and conservatively redacted before storage or responses. This removes the remainder of the credential-bearing paragraph and possible adjacent values before the label; saved text can be reviewed and corrected. No evidence text, filenames, or raw OCR exceptions are logged.
- Bounded memory-only multipart parsing avoids the installed framework's default temporary-file spooling. Static JPEG/PNG content is decoded and verified; limits are 5 MiB per image, 6 MiB for the multipart body, and 16 million decoded pixels. No raw image, original filename, storage path, or EXIF metadata is persisted.
- Lazy English CPU EasyOCR with cached CRAFT detection and English recognition models, request-time downloads disabled, serialized reader access, safe unreadable/unavailable notices, and manual-entry fallback. A busy reader offers manual entry. The injectable adapter supports deterministic routine tests. A confirmed-evidence selector excludes all unreviewed screenshots for future Phase 03 use.
- React Ask Byte Bot entry, saved guided questions, attached authoritative transaction card with all three statuses, voluntary message/call-summary input, browser-local image preview, OCR review/edit/confirm, explicit replacement/removal, saved/error announcements, stale-tab recovery, and unsaved-edit protection for links, browser navigation, and unload. Object URLs are revoked on close, replacement, removal, and unmount.
- Reused Phase 01 infrastructure and frontend dependencies/lockfile. Added focused tests, synthetic image generators, real OCR smoke, browser acceptance, README setup/retention instructions, and implemented API contract documentation. Existing migration rollback/checksum tests now copy every applied migration rather than assuming a single migration.

### Commands and results

Commands ran from the project root unless noted:

- `.venv/bin/python -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu` — passed; installed torch 2.6.0+cpu and torchvision 0.21.0+cpu for Python 3.12.16 on Linux.
- `.venv/bin/python -m pip install -r backend/requirements-ocr.txt` — passed; installed EasyOCR 1.7.2 and its local OCR dependencies. The optional requirements now pin the CPU package pairing; install CPU wheels first as documented.
- From `backend/`: `../.venv/bin/python -m bytebot.cli ocr-prepare` — passed; downloaded CRAFT detection and English recognition weights to `.cache/easyocr`. No evidence was involved in model preparation.
- From `backend/`: `../.venv/bin/python -m bytebot.cli migrate` twice, then `../.venv/bin/python -m bytebot.cli seed` twice — all passed against the existing demo database on 55433.
- `.venv/bin/python -m pytest backend/tests -q` — **28 passed**, final run 2.33s. Covers fresh/repeated/concurrent migrations, upgrade from migration 001 with session/transaction preservation, seed repeatability, all actual transaction statuses, create/reopen concurrency, saved/restarted context, unknown/no distinction, no-op saves, stale/concurrent revisions, edits during OCR, evidence lifecycle and limits, confirmed-input gating, JSON/multipart validation, chunked bodies without Content-Length, byte/dimension boundaries, corrupt/mislabeled/animated/unsupported images, OCR failure/busy fallback, credential redaction variants, cookie ownership, all new cross-session endpoints, and database ownership constraints. Upload tests make temporary-file helpers fail to verify that uploads over 1 MiB do not use disk spooling. Credential canaries are checked against persisted data, responses, and captured logs. Only the guarded `bytebot_test` database is reset.
- The first regression run exposed the existing test's assumption that only migration 001 existed; the fixture was corrected. Browser verification caught ambiguous populated-control labels; explicit accessible names were added. Navigation assertions now wait for the confirmation decision. Final checks below pass.
- `.venv/bin/python backend/tests/ocr_smoke.py` — passed real CPU English OCR on synthetic, in-memory images. Final run: legible image **2.74s** (including lazy initialization), unreadable blank image **0.37s**. Legible output contained the expected return request and 5000; the blank returned no invented text and `unreadable`. No input images written to disk.
- From `backend/`: `../.venv/bin/python -m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log` — started the updated API successfully. The existing Vite server on 5173 was reused.
- `.venv/bin/python backend/tests/browser_phase02.py` — passed with the live API and real CPU OCR. Covers saved intake/reload, paste/call/screenshot methods, redaction display, OCR correction/confirmation, blank-image manual fallback, removal of all methods with persisted absence after reload, object-URL cleanup, stale-save recovery preserving local drafts, cancelled link and browser-back navigation with unsaved edits, foreign direct-link denial, successful/pending/failed intake, keyboard focus, and mobile overflow. No page errors.
- `.venv/bin/python backend/tests/browser_smoke.py` — Phase 01 regression passed: transaction states, reload, browser navigation, mobile overflow, keyboard focus, cross-session denial, API error/retry, and no page errors.
- `npm --prefix frontend run build` — passed TypeScript and Vite production build. Existing dependency-level React Router `use client` directive warnings remain nonblocking.
- `.venv/bin/python -m pip check` — passed, no broken requirements.
- `docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'` — Compose PostgreSQL healthy on 55433; original `bytebot-mvp-pg` still running on 55432 and untouched.
- Visually inspected the synthetic desktop investigation (local artifact `.cache/phase02/investigation-desktop.png`) and mobile investigation (local artifact `.cache/phase02/investigation-mobile.png`): readable controls, correct provenance/status labels, reachable evidence actions, and no clipped horizontal content. Browser artifacts and OCR models are local ignored files.

### Exit criteria and next step

All Phase 02 exit criteria pass. FR-02–FR-06 are delivered; AT-07 verifies OCR correction/manual fallback and confirmed-input selection, and the Phase 02 portion of AT-10 verifies ownership for investigation/context/evidence reads and writes. Actual analysis gating is Phase 03, which must use the confirmed-evidence selector and reject unreviewed screenshots before starting analysis.

No Phase 02 verification is pending. The updated API, existing Vite server, and Compose database are left available for review. Only synthetic browser/test evidence was used; no live Gemini request or provider credential was needed. Analysis orchestration, extraction, intelligence, risk results, reports, incident tracking, audit events, and reset remain deferred to their documented phases. Next step is Phase 03 after separate authorization. No Git metadata exists in the workspace, so no commit was created.

## 2026-11-13 — Phase 03 Analysis and results complete

Authorized by the user's “Implement the plan” instruction following the Phase 03 plan. Only Phase 03 and its agreed port configuration changes were implemented.

### Delivered

- Migration 003 adds revision-bound durable runs, unique investigation/revision identity, lease fencing, stage checkpoints and numeric durations, extracted signals, risk assessments, and exact simulated intelligence entity/incident relationships. Migrations 001–002 remain unchanged. Seeds are idempotent and preserve session data.
- Analyze API with strict expected revision, lookup-only owner checks, safe 404s, screenshot review gating, and 202 responses. Concurrent requests reuse one run. Completed current runs are reused; failed current runs requeue explicitly with the same ID and a cleared attempt budget. Investigation GET includes current run/stage/notices/result only.
- Two lifespan-owned worker slots claim database work in a consistent case-then-run lock order using SKIP LOCKED. Idle polling is one second; leases last 60 seconds with 10-second renewal. Recovery resumes saved stages, and three interrupted claims require explicit retry. Every write is fenced by owner, current revision, token, and unexpired lease. Provider work holds no database connection.
- One typed LangGraph with Transaction Context, Message Analysis, Risk Investigation, and Incident Resolution nodes. Gemini structured extraction uses separate prompts/schemas, exact citation and value checks, an eight-second deadline and one retry for timeout/invalid output, with SDK retries disabled. Missing credentials and exhausted extraction preserve inputs and produce supported fallback assessments or Unable to assess.
- Confirmed redacted evidence is mapped to opaque references and identifier placeholders before provider use. Transaction references, known unrelated personal details, credentials, and raw screenshots stay out of requests. Values, unsupported citations, and positive fragments cut from negated requests are rejected. Raw provider errors/responses are never logged or persisted. Safe local request enums preserve supported warning intent before redaction without retaining values; bare labels and safety advice do not trigger High concern. These are conservative English prototype checks, not comprehensive detection.
- Versioned Python decision table delivers all four categories, actual payment status, distinct urgency/threat/isolation counting (bank avoidance and secrecy share isolation), zero same-ID risk reduction, local requested-destination comparison, exact labelled simulated matches, no-match limitations, and post-loss guidance. An identifier merely mentioned is not treated as the repayment destination. Findings reference their user/transaction/evidence/intelligence/rule sources; no fraud probability or definitive accusation is displayed.
- Every actual input change atomically erases derived outputs, signals, and assessments, revokes active leases, and restores intake state. Evidence removal deletes its text and dependent content. An old worker cannot restore results; no-op saves preserve them. Phase 04 must add report invalidation to the same transaction when report storage exists.
- React saved-only Analyze control, progress, results, provenance/source links, safe warnings, limitations, retry, reload/navigation, and responsive keyboard-accessible screens. Unsaved input and unreviewed screenshots block analysis. Corrected a reload race so old intake controls disappear before saved state is fetched again.
- Explicit synthetic extraction fixture mode for exact predefined inputs, labelled in results and rejecting unknown fixture inputs. No fixture fallback silently imitates live Gemini. Added opt-in synthetic-only Gemini smoke script; existing dependency manifests/lockfile and installed pinned LangGraph/GenAI packages were reused.
- Byte Bot frontend moved to loopback **5174**, preview **4174**, both strict. API remains **8000**, PostgreSQL **55433**. Updated browser test base URLs, Compose/example defaults, README, architecture, and agent port instructions. **No actions were taken against ports 5000, 5173, or 3306 or their services.** The original temporary PostgreSQL on 55432 remains untouched.

### Commands and results

Commands ran from the project root unless noted:

- Read-only listener inspection before work confirmed the other project's Flask on 5000 (PIDs 257501/257549), Vite on 5173 (PID 257430), and MySQL on 3306. Byte Bot's own API was on 8000, Compose PostgreSQL on 55433, and 5174/4174 were free. Only the verified Byte Bot API process was restarted to load new code.
- From `backend/`: `../.venv/bin/python -m bytebot.cli migrate` twice and `../.venv/bin/python -m bytebot.cli seed` twice — passed. Repeated again after implementation, all passed. Existing demo sessions were preserved.
- `.venv/bin/python -m pytest backend/tests -q` — **59 passed**, final run **6.78s**. Includes all prior checks plus A–E, all categories/statuses/unavailable facts, exact/no intel matches, same-ID neutrality, pressure deduplication, insufficient context, post-loss guidance, concurrent analyze reuse, missing/foreign sessions, screenshot gating, stale revisions, no-op preservation, physical derived-content deletion, lease expiry/token fencing/checkpoint recovery, actual app restart, attempt exhaustion, retry, heartbeat/durations, two-slot capacity, and evidence removal during an awaited provider call. Privacy/citation checks cover credentials in storage/responses/logs/provider input, identifier masking next to punctuation, malicious evidence, fabricated values/citations, negated substrings, safety advice, invalid output/timeout retry counts, exhausted provider fallback, and unknown fixture rejection. Historical migration tests seed only the schemas available at their simulated phase; upgrade from Phase 02 preserves a real case and evidence. Only guarded `bytebot_test` is reset.
- `npm --prefix frontend run build` — passed TypeScript and production Vite bundle. Existing dependency-level React Router `use client` warnings remain nonblocking.
- From `backend/`: `BYTEBOT_EXTRACTION_MODE=fixture ../.venv/bin/python -m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log` — running the implemented API in explicitly labelled synthetic mode for review. No provider key was used.
- `npm --prefix frontend run dev` — frontend running at **http://127.0.0.1:5174/**. A second invocation exited 1 with “Port 5174 is already in use”, verifying strict binding with no fallback port or process termination.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_smoke.py` — passed Phase 01 regression with no page errors.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase02.py` — passed saved intake, real CPU OCR, screenshot confirmation gating, removal, conflicts, unsaved navigation, ownership, desktop/mobile, and keyboard regression; no page errors.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase03.py` — passed A–E, saved-only Analyze, result reload/navigation, progress/retry (controlled responses at their UI boundary), invalidation, foreign reads/analyze, actual pending/failed results with independent warnings, keyboard and desktop/mobile overflow checks; no page errors. Synthetic Analyze-to-visible-result timings: **A 1.33s, B 1.33s, C 1.34s, D 1.33s, E 1.34s**. Environment: local Linux, Python 3.12, Node 22, PostgreSQL 16, two worker slots, desktop 1280×900 and mobile 390×844. All are below the 20-second target; these are fixture timings, not live Gemini performance.
- Browser verification initially caught ambiguous duplicate-provenance heading locators and React Strict Mode's repeated initial fetch in a controlled progress test; assertions now account for both. The actual intake reload race was corrected in the UI. Final browser runs pass.
- `.venv/bin/python -m pip check` — passed, no broken requirements. `docker compose config --quiet` and `docker compose --env-file .env.example config --quiet` — passed.
- `.venv/bin/python backend/tests/gemini_smoke.py --live` — **PENDING**, exit 2 because both local Gemini key/model are absent. No network request was made. This optional check remains separate from deterministic acceptance.
- Final `ss -ltnp` inspection confirmed the same other-project Flask/Vite PIDs still listening on **5000/5173**, MySQL still listening on **3306**, Byte Bot on **8000/5174/55433**, and original temporary PostgreSQL on **55432**. Both database containers remained healthy/running.
- Visually inspected synthetic desktop results (local artifact `.cache/phase03/results-desktop.png`) and mobile results (local artifact `.cache/phase03/results-mobile.png`); readable category/guidance, provenance and limitations, reachable links, no horizontal clipping. Artifacts remain local and ignored.

### Exit criteria and next step

Phase 03 deterministic exit criteria pass. FR-07–FR-12 and the applicable portions of AT-01–AT-06, AT-08–AT-11 are verified. AT-05 report wording, AT-10 incident/report ownership, and report-related privacy/deletion checks remain in Phase 04. Optional live Gemini verification remains pending local configuration and must record model/outcome/timing when run.

The API is available on 8000 in synthetic fixture mode, frontend on 5174, and Compose PostgreSQL on 55433. Protected services on 5000, 5173, and 3306 were not interrupted. Reports, incident tracking, audit events, scenario selector/reset, and full demo hardening remain deferred to Phases 04–05. Next step is Phase 04 only after separate authorization. No Git metadata exists in this workspace, so no commit was created.


## 2026-11-13 — Phase 04 Reports and follow-up complete

Authorized by the user's “Implement the plan” instruction following the Phase 04 plan. Only Phase 04 was implemented; Phase 05 remains pending.

### Delivered

- Migration 004 adds case status and its separate optimistic revision, immutable revision-bound report snapshots, and case-linked audit events. Migrations 001–003, existing manifests/lockfile, sessions, transaction fixtures, and seed behavior are reused. No dependencies were added.
- Owner-scoped incident list and status update endpoints, using investigation IDs as incident IDs. Lists include cases before analysis, newest creation first, with the current category or null. All six statuses are supported; no-op writes do not advance revision or audit. Concurrent stale status updates return `409 stale_status`. Status changes preserve results/reports and do not claim any external action.
- Report generation/retrieval and UTF-8 text attachments from one persisted snapshot. Snapshot includes report/case/run identity, timestamp and input revision, status at generation, original transaction facts and actual status explanation, typed user statements, confirmed redacted evidence, validated extracted signals with INR amount formatting, assessment and provenance, rule version, simulated-intelligence details, unknowns, limitations, extraction notices, and recommendations. Report generation makes no provider request. Repeated/concurrent generation reuses the same ID and timestamp.
- Report creation and input writers share the existing case row lock. Every actual input revision change physically deletes reports in the same transaction that clears assessments, signals, and run outputs. Both race orderings are tested; stale report retrieval/download is rejected. No-op input saves preserve reports. Previously downloaded files remain with the user.
- Atomic audit capture for case creation, actual context/evidence changes, evidence removal, fenced analysis completion, report generation, and status changes. Metadata schemas allow only typed UUIDs, revisions, evidence type and status enums; no raw text, filenames, identifiers, credential values, or provider payloads. Backfill records only surviving creation/submission/completion facts at original persisted timestamps and explicitly marks them; repeated migration produces no duplicates. No audit viewer was added.
- React My Incidents navigation/list, status controls on list and case screens, stale-status recovery that preserves intake drafts, result-to-report generation, HTML review and text download, loading/error/retry/analysis-needed states, safe escaped evidence display, focus/navigation revalidation, and server-checked downloads with reviewed-report identity checks. The report starts with category and primary guidance. Post-loss guidance is reused from Phase 03. No report submission or financial action exists.
- README and architecture document new contracts, retention and invalidation, statuses, audit backfill, export behavior, and verification. Phase 04 checklist and acceptance coverage updated.

### Commands and results

Commands ran from the project root unless noted:

- Read-only `ss -ltnp` and `docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'` inspection confirmed the other project's Flask on 5000 (PIDs 257501/257549), Vite on 5173 (PID 257430), and MySQL on 3306. Byte Bot was on API 8000, Vite 5174, and PostgreSQL 55433; the original temporary `bytebot-mvp-pg` remained on 55432. Protected services were not stopped, restarted, or reconfigured.
- From `backend/`: `../.venv/bin/python -m bytebot.cli migrate` twice, followed by `../.venv/bin/python -m bytebot.cli seed` twice — all passed against the existing demo database on 55433. Existing sessions and saved cases were preserved. Audit backfill was applied once by the checksum-checked migration runner.
- `.venv/bin/python -m pytest backend/tests/test_reports.py -q` — **15 passed**. Covers report contents/UTF-8/idempotency, all status values/no-ops/reopen, concurrent status conflicts, owned lists/unanalysed cases/current-only category, input changes and physical report/result deletion, regeneration, both report/input race orderings, concurrent report creation, pending/failed warnings and post-loss guidance, safe audit actions/timestamps/allowlists, credential canaries in responses/storage/logs, foreign/absent sessions, validation/gating/extraction fallback, corrected OCR-only snapshots, and populated Phase 03 upgrade/backfill/repeatability.
- `.venv/bin/python -m pytest backend/tests -q` — **74 passed**, final run **10.19s**. Includes all previous phase regression checks. Only the guarded `bytebot_test` database is reset by these tests.
- `npm --prefix frontend run build` — passed TypeScript and Vite production build. Existing React Router dependency `use client` warnings remain nonblocking.
- From `backend/`: `BYTEBOT_EXTRACTION_MODE=fixture ../.venv/bin/python -m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log` — updated API running successfully in explicitly labelled synthetic fixture mode. Only the verified Byte Bot backend process was restarted. Existing Byte Bot Vite on 5174 and both database containers were reused.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_smoke.py` — passed transaction/history/ownership/keyboard/mobile/error-retry regression; no page errors.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase02.py` — passed saved intake, real CPU OCR, review/removal/conflict/navigation/ownership regression; no page errors.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase03.py` — passed A–E, analysis reuse/progress/retry/invalidation, ownership, pending/failed warnings, keyboard and responsive checks; no page errors. Fixture Analyze-to-visible-result timings: A 1.33s, B 1.33s, C 1.33s, D 1.34s, E 1.34s. These are local synthetic fixture timings, not live Gemini performance.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase04.py` — passed report review/download/reload, UTF-8 ₹ and snapshot content, all six statuses with reload, stale-status conflict recovery, case reopening, foreign report/download/status denial, focus-based invalidation, download denial after deletion, regeneration, post-loss guidance, inert malicious evidence with credential redaction, pending/failed report wording and safety warnings, retrieval failure/retry, keyboard focus, and desktop/mobile overflow checks. Final run had no page errors.
- `.venv/bin/python -m pip check` — passed, no broken requirements. `docker compose config --quiet` and `docker compose --env-file .env.example config --quiet` — passed.
- The first backend run caught a paise/string schema mismatch in extracted report amounts; the snapshot builder now formats amount signals as INR before validation. The first new browser run caught an ambiguous implicit label for the status selector; an explicit accessible label fixed it. Final tests and browser checks pass.
- Visually inspected synthetic desktop report (local artifact `.cache/phase04/report-desktop.png`), mobile report (local artifact `.cache/phase04/report-mobile.png`), and mobile incidents (local artifact `.cache/phase04/incidents-mobile.png`): readable facts/provenance/limitations, visible download/focus, reachable status controls, and no horizontal clipping. Synthetic text downloads are also in ignored `.cache/phase04/`.

### Exit criteria and next step

All Phase 04 exit criteria pass. FR-13, FR-14 and FR-16 are delivered. AT-12 verifies complete stored/report/download contents; remaining AT-10 verifies incident/report ownership without side effects. Report portions of AT-05 (pending/failed wording), AT-09 (credential exclusion and inert evidence), and the Phase 04 audit/status/invalidation/post-loss checks pass.

Byte Bot remains available at **http://127.0.0.1:5174** with the API on 8000 and PostgreSQL on 55433. Ports 5000, 5173, and 3306, and temporary PostgreSQL on 55432, remain untouched. No Phase 04 check is pending. Optional live Gemini verification remains separately pending key/model configuration from Phase 03; no provider request was made during Phase 04. Phase 05 scenario controls/reset/full demo hardening require separate authorization. No Git metadata exists in this workspace, so no commit was created.

## 2026-11-13 — Phase 05 Hardening and demo complete

Authorized by the user's “Implement the plan” instruction following the Phase 05 plan.

### Delivered

- Public synthetic A–E catalog, session-owned atomic loader, and history selector with manual-evidence option. Five distinct successful ₹5,000 scenario transaction templates coexist with the original successful/pending/failed payments. First loading uses shared normal answer/evidence validation, redaction, revision, ownership, and audit helpers, then stops at transaction details. Reopening returns the saved case unchanged, including edits and completed work. No automatic analysis/report generation or provider mode switching occurs.
- Idempotent seeds add missing templates without changing existing sessions. New sessions have eight transactions. Upgraded sessions gain only the requested missing scenario transaction on load, or all eight on reset. Migrations 001–004 and dependency manifests/lockfile are unchanged; no new schema or dependencies were necessary.
- Session-scoped reset with confirmation and failure/retry/status UI. Reset retains cookie/owner, locks owner then cases in deterministic order, deletes owned cases and all cascading context/evidence/runs/signals/assessments/reports/audit events, and recreates eight transactions with new IDs in one transaction. Other sessions and shared intelligence/templates remain intact. Missing-template validation precedes deletion; any failure rolls back all changes.
- Case creation/loading share the owner lock before any case lock. Existing writers keep case-before-run ordering. Deleted cases count as lost worker leases, so delayed provider completion, heartbeat, stage writes, publication, failure handling, screenshot persistence, report generation, and status writes cannot restore deleted state. Existing unsaved-navigation protection applies when reaching reset through history.
- Fixture selection now checks canonical confirmed synthetic text before identifier masking. Altered destinations/messages cannot accidentally receive a predefined extraction. Unknown evidence in explicit fixture mode uses the documented unavailable-extraction/local fallback; Gemini mode remains the normal configured provider path.
- Desktop/mobile/keyboard/error/retry verification, synthetic Scenario B image generator, and an end-to-end fresh-reset screenshot rehearsal. Mobile header height now fits its wrapped badge/navigation. README, architecture, acceptance matrix, and Phase 05 checklist describe actual interfaces, reset semantics, setup/test/reset commands, and rehearsal steps.

### Commands and results

Commands ran from the project root unless noted:

- Before work, `ss -ltnp` and `docker ps --format '{{.Names}} {{.Status}} {{.Ports}}'` confirmed protected Flask on 5000 (PIDs 257501/257549), protected Vite on 5173 (PID 257430), MySQL on 3306, Byte Bot API on 8000, Vite on 5174, Compose PostgreSQL on 55433, and original temporary PostgreSQL on 55432. No actions were taken against the protected services or original container.
- From `backend/`: `../.venv/bin/python -m bytebot.cli migrate` twice, then `../.venv/bin/python -m bytebot.cli seed` twice — all passed. Migration checksums remain unchanged; the five new templates were inserted once. Existing demo records were preserved. Integration tests also cover repeated/concurrent migrations, repeated seeds, and loading a missing scenario into an older three-transaction session without changing its original records.
- `.venv/bin/python -m pytest backend/tests/test_demo.py -q` — **20 passed**, 2.62s. Covers A–E loaded outcomes, reopening after edits, independent/manual cases, concurrent loads without duplicate evidence/audits, repeat reset and full cascade deletion, cookie retention, other-session state/report preservation, missing sessions/strict payloads, rollback, upgraded-session compatibility, every stale worker write, reset during awaited provider and OCR, both creation/reset and status/report/reset lock orderings, concurrent resets/loading, and rejection of edited fixture messages/destinations.
- `.venv/bin/python -m pytest backend/tests -q` — **94 passed**, 12.15s. All prior rule/API/privacy/ownership/report/invalidation/upgrade tests pass. Test database reset remains guarded to `bytebot_test`, separate from the demo database.
- `npm --prefix frontend run build` — passed TypeScript and production Vite build, including after the mobile-header adjustment. Existing React Router dependency `use client` warnings remain nonblocking.
- `.venv/bin/python -m pip check` — passed. `docker compose config --quiet` and `docker compose --env-file .env.example config --quiet` — passed.
- Verified API PID 331256's command and working directory, then restarted only that Byte Bot process. From `backend/`: `BYTEBOT_EXTRACTION_MODE=fixture ../.venv/bin/python -m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log` — running as PID 359609. Existing Byte Bot Vite and database services were reused.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_smoke.py` — passed original transaction/status/navigation/reload/ownership/error-retry checks; no page errors.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase02.py` — passed saved context, text/call evidence, real screenshot OCR/review/manual fallback, credential redaction, removal/preview cleanup, conflicts, unsaved navigation, ownership, and keyboard/mobile checks; no page errors.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase03.py` — passed A–E, saved-only analysis, progress/retry/reload, invalidation, ownership, pending/failed independent warnings, and responsive/keyboard checks. Analyze-to-visible-result times were **1.33s for each A–E**; no page errors.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase04.py` — passed UTF-8 report contents/download/reopen, six statuses/conflicts, ownership, stale-report invalidation, post-loss guidance, inert malicious evidence, pending/failed wording, and desktop/mobile/focus checks; no page errors.
- `.venv/bin/python backend/tests/ocr_smoke.py` — real CPU English EasyOCR passed: legible synthetic screenshot **2.53s**, unreadable **0.36s**. No OCR input image is stored by the server.
- `.venv/bin/python backend/tests/gemini_smoke.py --live` — **PENDING**, exit 2: local Gemini key/model absent. No network/provider request was made. This remains separate from deterministic acceptance.
- `BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase05.py` — passed selector A–E, exact saved-case reuse, keyboard-only selector/CTA/analysis, visible focus, reset confirmation cancellation/failure/retry/repeat, isolated browser ownership, old URL/report invalidation, manual-mode real Scenario B OCR/review/confirmation, report download/reopen/status, mobile action reachability, and catalog/load failure retries; no page errors. The first keyboard assertion assumed Enter would close a collapsed native select; Enter actually opened it. The test now uses Home followed by Tab to follow the native control's behavior.
- Final Phase 05 Analyze-to-visible-result timings: **A 1.28s, B 1.28s, C 1.29s, D 1.29s, E 1.29s; reviewed Scenario B screenshot 1.29s**. All meet the under-20-second target. Environment: local Linux, Python 3.12, Node 22, PostgreSQL 16, explicit fixture extraction, two worker slots, desktop 1280×900/mobile 390×844. These are fixture timings, not live Gemini performance.
- Fresh-reset automated Scenario B rehearsal passed in **2.68s**, including warm CPU OCR, review/correction, analysis, UTF-8 download, My Incidents reopening, and Bank Contacted status save. It excludes human narration and is a functional rehearsal of the four-minute walkthrough, not a measured human presentation. Human review in the automation replaces OCR line breaks/recognition differences with the exact synthetic message before confirming.
- Visually inspected desktop history (local artifact `.cache/phase05/history-desktop.png`) and mobile history (local artifact `.cache/phase05/history-mobile.png`). Controls, labels, provenance and focus are readable; no horizontal overflow. Header spacing was adjusted to contain wrapped mobile navigation/badge. The final browser suite/build passed after this adjustment. Timings (local artifact `.cache/phase05/timings.json`), synthetic Scenario B screenshot and report download remain ignored under `.cache/phase05/`.
- Extended Phase 05 browser coverage traverses the actual mobile tab order without mouse actions or programmatic focus for Scenario D: selector → load → Ask Byte Bot → Analyze → generate/download report → My Incidents → select/save Bank Contacted → reopen report. Focus outlines and action reachability pass. One invocation exited 143 before reporting; the rerun with `PYTHONUNBUFFERED=1 BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase05.py` passed the complete extended suite with the final timings above.
- Final listener/container inspection confirmed protected Flask on 5000 (now PIDs 366133/366163), Vite on 5173 (unchanged PID 257430), MySQL on 3306, Byte Bot on 8000/5174/55433, and original temporary PostgreSQL on 55432; both database containers remain running, with Compose PostgreSQL healthy. Flask PIDs differ from the initial inspection; no command in this task targeted that service. Only verified Byte Bot API PID 331256 was terminated by this task.

### Exit criteria and remaining verification

All Phase 05 deterministic exit criteria pass. FR-15 is implemented; AT-01 through AT-12 pass using the combined rule/API/browser matrix documented in acceptance. Session reset is repeatable, isolated, rollback-safe and fenced against in-flight work. The complete fresh-reset screenshot-to-report/status journey passes at desktop/mobile sizes with keyboard/focus/status checks, and measured fixture analysis is under 20 seconds.

Byte Bot remains available at **http://127.0.0.1:5174**, with explicit fixture API on 8000 and PostgreSQL on 55433. This task did not stop, restart, or reconfigure services on 5000, 5173, 3306 or temporary PostgreSQL on 55432. Optional live Gemini remains pending local key/model configuration; no deterministic acceptance item is pending. There is no Git metadata in this workspace, so no commit was created. Further product changes require a new user request.


## 2026-11-13 — GitHub repository preparation

Authorized by the user's “Implement the plan” after choosing preparation and push to the public repository `https://github.com/krishnacsn/byte`. The target was empty, and the local workspace previously had no Git metadata. This is documentation and repository preparation, not a new product phase.

### Delivered

- Concise README with project status, features, clone/setup/start commands, code layout, and documentation index.
- New [setup](setup.md), [testing](testing.md), [development](development.md), and [demo](demo.md) guides. They cover Linux/macOS and PowerShell, pinned dependency groups, environment variables, migrations/seeds, explicit fixture mode, optional CPU OCR/Gemini, ownership/concurrency/evidence invariants, all five browser suites, and reset/report rehearsal.
- All 11 pre-existing Markdown documents retained, including the original PRD and all phase guides; four development guides bring the total to 15. Fixed Phase 01 launch/setup links. Historical `.cache/` attachments now appear as named local artifact paths rather than broken GitHub links. Earlier verification statements remain historical records.
- Runtime, development, and OCR requirements annotated without changing package versions. Frontend manifest/lockfile unchanged. Python direct pins are explicitly distinguished from a transitive lockfile.
- Sanitized `.env.example` documents cookie security and optional shell-only frontend/browser targets. Local `.env` remains byte-for-byte unchanged. Ignore rules exclude local environment overrides, dependencies, builds, model/browser caches, exports/uploads, logs, backups, credentials, and editor files while including the example and SQL migrations.
- Git initialized on `main` with `origin` pointing to the supplied HTTPS repository and the existing local author identity. Reviewed upload set: 91 files, including 15 Markdown documents, approximately 0.53 MB. No license was selected and no runtime or schema behavior changed.

### Commands and results

- `.venv/bin/python -m pytest backend/tests -q` — **94 passed**, 12.36s. Only the existing guarded `bytebot_test` database was rebuilt; the demo database was not migrated or seeded during publishing preparation.
- `npm --prefix frontend run build` — passed TypeScript and Vite production bundling. Existing dependency-level React Router `use client` warnings remain nonblocking.
- `.venv/bin/python -m pip check` — passed, no broken requirements.
- `docker compose --env-file .env.example config --quiet` — passed without starting or changing services.
- Python standard-library upload inspection — passed secret-pattern, large-file, absolute-workstation-path, and all relative Markdown link/anchor checks. Only sanitized demo database credentials are published. Application modules, tests, migrations, frontend source/lockfile, and local `.env` were compared against pre-edit SHA-256 hashes and remain unchanged.
- `git check-ignore` — confirmed local `.env`/overrides, installed dependencies, build output, cache screenshots, report/upload/backup paths, credential files, and logs are excluded. `.env.example` and versioned SQL migrations remain included.
- `git diff --cached --check` — passed after documenting the unchanged original PRD's intentional Markdown hard breaks/final blank line in `.gitattributes`. No whitespace changes were made to that reference document. Staged file statistics, all 15 Markdown paths, and the exact staged blobs were reviewed before committing.
- `git ls-remote origin` — target still empty before initial publication. GitHub metadata and local CLI authentication confirmed the public target and push access. Initial publication uses an ordinary upstream push to `main`, without force.

### Verification boundaries

Browser journeys, real OCR, live Gemini, and demo migration/seed commands were not rerun during repository preparation; their earlier dated outcomes remain above. Optional live Gemini remains pending local key/model configuration. No service was stopped, restarted, or reconfigured; protected ports 5000, 5173, 3306 and temporary PostgreSQL 55432 were left untouched. Generated evidence, reports, caches, and credentials are not part of the repository.
