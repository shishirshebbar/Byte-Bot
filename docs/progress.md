# Byte Bot implementation progress

Entries below are dated historical records. Local `.cache/` screenshots, reports, and timings are excluded from GitHub. Regenerate them using [testing](testing.md) and [demo](demo.md). The latest entry covers the one-approval hackathon upgrade.

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
| [01 Foundation](#2026-11-13--phase-01-foundation-complete) | Complete | 2026-11-13: 7 integration tests, frontend build, and browser smoke passed; see entry below. |
| [02 Guided investigation](#2026-11-13--phase-02-guided-investigation-complete) | Complete | 2026-11-13: 28 tests, build, real CPU OCR, and both browser suites passed; see entry below. |
| [03 Analysis and results](#2026-11-13--phase-03-analysis-and-results-complete) | Complete | 2026-11-13: 59 tests, frontend build, and three browser suites passed; optional live Gemini pending configuration. |
| [04 Reports and follow-up](#2026-11-13--phase-04-reports-and-follow-up-complete) | Complete | 2026-11-13: 74 backend tests, frontend build, and all four browser suites passed; AT-12 and remaining AT-10 verified. |
| [05 Hardening and demo](#2026-11-13--phase-05-hardening-and-demo-complete) | Complete | 2026-11-13: 94 backend tests, frontend build, five browser suites, real CPU OCR, reset races/isolation, and fresh-reset screenshot rehearsal passed. |

Phases 01–05 are complete. Deterministic MVP acceptance passes; optional live Gemini verification remains pending local key/model configuration. The [Paytm hackathon presentation plan](paytm-hackathon-plan.md) tracks the new presentation phases.

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

## 2026-11-13 — Windows local installation and startup

Authorized by the user's “Implement the plan” and “continue the plan” requests. This is installation and verification of the completed MVP, not a new feature phase. Full CPU OCR setup was selected during planning.

### Environment and installation

- Reviewed the repository Markdown guides, existing manifests, lockfile, and application setup. Preserved `AGENTS.md`, dependency versions, migrations, and application source.
- Windows PowerShell, uv-managed Python 3.12.16, Node 22.19.0, npm 11.21.2, Docker 29.9.2, and Compose v5.6.1. Docker Desktop was initially stopped; started the installed executable with `Start-Process -WindowStyle Hidden` and verified the Linux engine.
- `uv venv --python 3.12 --seed .venv` — passed. Created the previously absent `.env` from `.env.example`; no Gemini credentials added. The API uses an explicit process-level fixture override.
- `.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt` — passed after resuming an interrupted installation. `npm --prefix frontend ci` — passed, 29 packages installed, zero reported vulnerabilities.
- `.\.venv\Scripts\python.exe -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu`, followed by `-m pip install -r backend/requirements-ocr.txt` — passed. Verified torch 2.6.0+cpu, torchvision 0.21.0+cpu, and CUDA unavailable. `-m playwright install chromium` — passed.
- `docker compose config --quiet`, `docker compose --env-file .env.example config --quiet`, and `docker compose up -d --wait db` — passed. PostgreSQL is healthy on loopback 55433. Created `bytebot_test` after querying `pg_database`; the initial empty-query PowerShell null handling was corrected without changing application code.
- From `backend/`, `..\.venv\Scripts\python.exe -m bytebot.cli migrate` twice and `seed` twice — all passed.

### Verification

- `.\.venv\Scripts\python.exe -m pytest backend/tests -q` — **94 passed**, 85.07s. Only the guarded separate test database was rebuilt.
- `npm --prefix frontend run build` — passed TypeScript and Vite production bundling. Existing React Router `use client` warnings remain nonblocking. `.\.venv\Scripts\python.exe -m pip check` — passed.
- Started fixture Uvicorn from `backend/` with `-m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log`. Started the frontend with `node node_modules/vite/bin/vite.js` from `frontend/`, equivalent to its npm dev script. Both are hidden background processes; `/api/v1/health` returns ready/database available directly and through the frontend proxy.
- With `BYTEBOT_WEB_URL=http://127.0.0.1:5174` and `PYTHONIOENCODING=utf-8`, ran `browser_smoke.py`, `browser_phase03.py`, and `browser_phase04.py` using the project interpreter — all passed, no page errors. Phase 03 fixture analysis A–E took 1.42, 1.42, 1.44, 1.42, and 1.42 seconds. Verified reports/downloads/statuses, ownership, invalidation, desktop/mobile, keyboard, and fallback behavior.
- Started `node node_modules/vite/bin/vite.js preview` from `frontend/` on 4174 and reran `browser_smoke.py` with that URL — passed against the production bundle. Verified its process identity and stopped only that temporary preview.
- Visually inspected generated desktop results and mobile report screenshots; labels, provenance, controls, and content are readable without horizontal clipping. Local logs and generated artifacts are ignored under `.cache/`.
- From `backend/`, `..\.venv\Scripts\python.exe -m bytebot.cli ocr-prepare` — passed, downloaded and validated CRAFT and English recognition models in `.cache/easyocr`. `.\.venv\Scripts\python.exe backend/tests/ocr_smoke.py` from the root — passed actual CPU OCR: legible synthetic image 13.19s including lazy initialization; unreadable image 1.38s.
- Restarted only the verified Byte Bot Uvicorn process after installing OCR. With the same web URL and UTF-8 shell settings, `.\.venv\Scripts\python.exe backend/tests/browser_phase02.py` and `backend/tests/browser_phase05.py` — both passed without page errors. All five documented browser suites have now passed on Windows without source or test changes.
- Phase 05 fixture analysis times: A 1.36s, B 1.38s, C/D/E 1.39s each, and reviewed Scenario B screenshot 1.39s, all below 20 seconds. Fresh-reset screenshot-to-report/status rehearsal passed in 6.08s including warm CPU OCR and excluding human narration. Verified desktop 1280×900, mobile 390×844, actual keyboard navigation, isolated/repeated reset, old URL/report invalidation, and error recovery. Visually inspected the new mobile history screenshot; controls and all eight transactions fit without horizontal clipping.
- Final `.\.venv\Scripts\python.exe -m pip check`, `git diff --check`, database health, and direct/proxied API checks — passed. Preview port 4174 is no longer listening. Protected MySQL remains on 3306 with the same observed PID 6732.

### Running services and handoff

Installation, build, and deterministic Windows verification are complete. The frontend remains available at **http://127.0.0.1:5174**, with fixture API **8000** and healthy PostgreSQL **55433**. Final API PID is 19572 (virtual-environment launcher 23588); frontend PID is 28932. Service metadata and logs are local ignored files under `.cache/setup/`.

Run `.\.cache\setup\stop-bytebot.ps1` from the repository root to stop only this run's API/frontend. The helper checks recorded process creation times and expected command lines before stopping; `-WhatIf` was verified without stopping services. `docker compose stop db` separately stops Byte Bot's database while preserving its volume. The temporary production preview was already stopped.

Only this progress file changed in tracked source. `AGENTS.md`, application code, tests, dependency manifests/lockfile, and migrations remain unchanged. Live Gemini remains separately pending configuration and was not invoked. No operation targeted protected ports 5000, 5173, 3306 or the original temporary database on 55432.

## 2026-11-14 — Paytm hackathon presentation

- **Phase 0** Saved the [presentation plan](paytm-hackathon-plan.md), retired five superseded guides, preserved the Windows handoff, and verified relative paths and heading links across all 11 Markdown files.
- **Phases 1–3** The root presentation now shares transaction, investigation, report, and incident screens with the standard workspace at `/workspace`. The phone runs the saved case workflow. The presenter panel displays the observed workflow stages, sourced evidence, report readiness, and saved follow-up. The presenter controls use the existing scenario and reset endpoints.

### Verification environment

- Windows PowerShell, Python 3.12, fixture API on 8000, frontend on 5174, production preview on 4174, and a separate local PostgreSQL 18 cluster on loopback 55433. Docker Desktop's Linux engine was unavailable, so `initdb` and `pg_ctl` started the cluster in `.cache/paytm-postgres`. Both Byte Bot databases use UTC. An initial test run on the cluster's default Windows timezone returned 93 passes and one UTC serialization failure. Correcting the local database settings resolved it.
- From `backend/`, ran `..\.venv\Scripts\python.exe -m bytebot.cli migrate` and `..\.venv\Scripts\python.exe -m bytebot.cli seed` successfully. Started `-m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log` with explicit fixture mode. Health reported ready and database available.

### Phase 4 checks

- `npm --prefix frontend run build` passed TypeScript and Vite production bundling. Existing React Router dependency directive warnings were nonblocking.
- `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed all **94 tests** in **32.10 seconds**. The guarded `bytebot_test` database was used for integration tests.
- `.\.venv\Scripts\python.exe backend/tests/ocr_smoke.py` passed for a legible synthetic image (**13.78 seconds**, including initialization) and an unreadable image (**0.65 seconds**).
- With `BYTEBOT_WEB_URL=http://127.0.0.1:4174`, ran `.\.venv\Scripts\python.exe backend/tests/<suite>.py` for `browser_smoke`, `browser_phase02`, `browser_phase03`, `browser_phase04`, `browser_phase05`, and `browser_presentation`. All six passed after restarting the Byte Bot API to clear pooled connections established before the database timezone adjustment. The workspace suites cover all A–E results, real screenshot confirmation, keyboard controls, analysis retry, session isolation, stale report invalidation, and reset recovery. The presentation suite covers panel synchronization, report download and reopen, saved status, evidence deep links, reset recovery, ownership, keyboard-only actions at mobile width, and viewports 1280×720, 1440×900, 390×844, and 320×740.
- The fresh-reset Scenario B run reached the visible **High concern** result in **1.38 seconds** after Analyze. It downloaded the UTF-8 report, saved **Bank Contacted**, and reopened the report in **2.18 seconds** from scenario load. These measure automated actions in fixture mode and exclude narration. Scenario A–E fixture runs stayed below 1.4 seconds, and the alternate warm CPU OCR rehearsal took 3.06 seconds.
- Visually checked the desktop history and findings and the 390 px and 320 px mobile screenshots. Screenshots and timings are local under `.cache/paytm-presentation/`. The [demo walkthrough](demo.md#four-minute-presentation) contains the narrated running order. A timed human presentation remains unverified. Live Gemini verification remains pending a local key and model.
- Presentation Phases 0–4 passed the local implementation and automated verification checks. `git diff --check` passed. The frontend on 5174 and production preview on 4174 remain available. No command targeted the services on 5000, 5173, 3306, or 55432.

## 2026-11-14 — One-approval hackathon upgrade

- **Upgrade Phase 1 complete.** Rehearsed the existing flow three times before editing. Added revision-scoped report approval to the existing analyze endpoint and worker. Migration 005 defaults existing runs to analysis only. Tests verified queued, running, and completed approvals, concurrent requests, ownership, and invalidation. An injected database error rolled back report creation while preserving the assessment, and manual retry recovered it.
- **Upgrade Phase 2 complete.** The phone result exposes priority safety guidance, a private report download, source links, and customer-entered follow-up. The presenter panel uses the current report ID and the saved case status returned by the API. The standard workspace still offers separate analysis and report actions. Verified Scenario B's same-ID, threat, and bank-avoidance findings and the A–E fixture outcomes.
- **Upgrade Phase 3 complete.** All three fixture runs passed the two-action reduction and 20-second readiness gates, downloaded a UTF-8 report, saved **Bank Contacted**, and reopened through **My Incidents**. The [four-minute script and judge Q&A](demo.md#four-minute-presentation) are ready. The local silent fallback recording `.cache/paytm-upgrade/scenario-b-fallback.webm` was played and inspected in Chromium at 1440×900. Duration **25.56 seconds**.

### Scenario B measurements

Automated Windows Playwright runs on the 1280×720 production preview with explicit fixture extraction. Each run reset a fresh browser session and opened the saved Scenario B case. Timing starts at analysis approval and ends once the file is downloaded and **Bank Contacted** is visible as saved. Action counts include selecting and saving that status. Reopening verifies persistence after the timed section.

| Flow | Customer actions | Assessment and report available, seconds by run | Download and follow-up saved, seconds by run |
| --- | ---: | --- | --- |
| Baseline | 6 | 1.44, 1.46, 1.45 | 1.72, 1.71, 1.69 |
| Upgrade | 4 | 1.54, 1.50, 1.52 | 2.26, 1.86, 1.90 |

The baseline actions were analyze, generate report, download, open **My Incidents**, select status, and save. The upgrade actions were approve analysis and report, download, select status, and save. The upgrade removed two customer actions and met the report-readiness target. Its measured automated completion times were slightly higher. Raw results are in `.cache/paytm-upgrade/baseline.json` and `.cache/paytm-presentation/timings.json`.

### Commands and results

- From `backend/`, `..\.venv\Scripts\python.exe -m bytebot.cli migrate` passed twice. Restarted the verified Byte Bot API with `BYTEBOT_EXTRACTION_MODE=fixture` and `-m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log`. The production preview proxy reported ready and the scenario catalog reported fixture mode.
- `.\.venv\Scripts\python.exe -m pytest backend/tests/test_reports.py -q` passed **21 tests**. `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed **100 tests in 107.66 seconds** using the guarded test database.
- `npm --prefix frontend run build` passed. Vite reported the existing nonblocking React Router module directive warnings.
- With `BYTEBOT_WEB_URL=http://127.0.0.1:4174` and `PYTHONIOENCODING=utf-8`, `.\.venv\Scripts\python.exe backend/tests/<suite>.py` passed for `browser_smoke`, `browser_phase02`, `browser_phase03`, `browser_phase04`, `browser_phase05`, and `browser_presentation`. Checked report retry, UTF-8 download, saved follow-up, ownership, invalidation and reset. Checked 1280×720, 1440×900, 390×844, and 320×740, including keyboard-only download and status save at 390 px. Inspected the 1440 px, 390 px, and 320 px result screenshots.
- `.\.venv\Scripts\python.exe backend/tests/ocr_smoke.py` passed real CPU EasyOCR for the legible (**29.97 seconds**, including initialization) and unreadable (**1.47 seconds**) synthetic screenshots. The workspace's warm OCR-to-report browser rehearsal completed in **5.44 seconds**.
- `git diff --check` passed. The Byte Bot frontend, preview, API, and database remained on ports 5174, 4174, 8000, and 55433.

A timed human rehearsal and live Gemini verification remain pending. The automated benchmark measures synthetic workflow completion. Fraud prevention, detection precision, and support handling time remain pilot metrics.

## 2026-11-14 — AI teammate Phases 0 and 1

Branch `teammate-phase-0-1`. Plan: [teammate plan](teammate-plan.md).

- **Phase 0 complete.** Saved the teammate plan, linked it from the README, and updated the boundaries in `AGENTS.md` and the README: actions only against labelled simulated systems, from the playbook, after the Python policy. Added `--bb-*` design tokens to `styles.css` for Phase 4. Grew the scenario catalog from A–E to A–K: money already sent (F), remote-access request (G), instruction injection (H), expected cashback (I), missing details (J), and a ₹75,000 high-value request (K). F–K transactions are on-demand templates copied only when loaded, so the default history keeps eight transactions. Hindi/Hinglish scenarios move to Phase 6 with multilingual extraction.
- **Phase 1 complete.** Supervisor-led LangGraph with deterministic routing, a live decision trace, follow-up questions that pause and resume the investigation, a playbook planner, `agent-policy-1` verdicts, and escalation with priority and SLA. Migration 006 adds `agent_trace`, `follow_up_questions`, `agent_actions`, and `escalations`. New endpoints: `POST /investigations/{id}/follow-ups` and `POST /investigations/{id}/escalate`. Contracts are in [architecture](architecture.md#implemented-teammate-phase-1-contracts-supervisor-agent). Actions are recorded with verdicts; execution against simulated systems is Phase 3.

### Commands and results

- Baseline before edits: `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed **100 tests**.
- After the changes, the same command passed **131 of 132**. The failure was a test assertion that queried the run-keyed `agent_trace` by case ID. After correcting it, `pytest backend/tests/test_demo.py -k reset_repeatability` passed. The new `backend/tests/test_agent.py` passes **20 tests** covering all eleven scenario outcomes, trace order, escalated-case approvals, injection handling, follow-up pause/resume and replay protection, "not sure" and repeated-round escalation, revocation on input change, customer escalation merge and ownership, policy and planner units, and routing.
- Existing tests were updated only for the larger catalog (scenario IDs, per-template amounts, on-demand template counts), for the new agent tables in reset checks, and for the expected `escalation_opened` audit event when unread evidence leaves no assessment.
- `npm --prefix frontend run build` passed (agent and escalation types added; no screen changes yet).
- From `backend/`, `bytebot.cli migrate` twice and `seed` twice passed on the demo database. Restarted only the Byte Bot API on 8000 with `BYTEBOT_EXTRACTION_MODE=fixture`; health reported ready. Through the 5174 proxy, Scenario F returned **High concern / escalated (urgent)** with trace `transaction_context → message_analysis → risk_investigation → gather_context → plan_actions → policy_gate → escalate → incident_resolution`, and Scenario J returned **Unable to assess / needs_customer_info**, skipping planning.
- **Pending:** the six Playwright browser suites were not rerun in this session. `browser_phase03.py` iterates every scenario and now includes F–K.

## 2026-11-14 — AI teammate Phase 3 (simulated systems)

- **Complete.** Added `systems.py`, `actions.py`, migration 007 (`simulated_records`, `declined` state, attempt count, audit events), the consent and undo endpoints, automatic execution of `auto` steps at publish, and an actions section in reports. Contracts are in [architecture](architecture.md#implemented-teammate-phase-3-contracts-simulated-systems). Phase 2 (risk score and intelligence graph) is deferred, following the plan's priority order.
- `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed **137 of 138**. The failure was an audit-order assertion that needed the new automatic `action_executed` event; after updating it, `pytest backend/tests/test_reports.py -q` passed **21**. New `backend/tests/test_actions.py` covers automatic receipts, consent executing once, decline, undo and irreversibility, revision/ownership/state checks, an outage recovered by retry, a visible failure after two outages, and executed steps surviving an input change.
- `npm --prefix frontend run build` passed. From `backend/`, `bytebot.cli migrate` and `seed` passed on the demo database, and the Byte Bot API on 8000 was restarted in fixture mode. Live through the 5174 proxy: Scenario B published with the notification executed (`SIM-NOTE-…`); consenting to the hold returned `executed` with a `SIM-HOLD-…` reference.
- **Pending:** the Playwright browser suites were not rerun. The phone does not yet show consent cards or receipts (Phase 4).

## 2026-11-14 — AI teammate Phase 4 (phone redesign)

- **Built.** The `/` phone now follows the reference designs. `/workspace` keeps its form flow so the earlier suites stay valid, and also shows the assistant and risk panels on results.
  - **History (`phone-history.tsx`):** date groups (Today, Yesterday, dates), round icons with success, pending, and failed badges, an "Unexpected credit" flag, a proactive alert card, received-total chips, search, status filter chips, and a four-item tab bar (Transactions, Scan, Byte Bot, Demo controls).
  - **Assistant (`agent-ui.tsx` `AgentPanel`):** a chat panel with a privacy note, bot bubbles by outcome, quick-reply chips for follow-up questions, consent cards with Approve and Decline, receipts with `SIM-…` references and Undo, an escalation card with priority and SLA, "Talk to a person", and a "Was this helpful?" prompt. The feedback is local only until Phase 7 stores it.
  - **Risk view (`RiskOverview`):** a three-level concern meter (no numeric score until Phase 2), amount, sender, and measured analysis time. Risk factors use ✕/⚠/✓ icons; factors reported by both the customer and the evidence merge into one row with both sources.
  - **Presenter panel:** a supervisor-decision trace and outcome under the four workflow stages.
  - **Backend:** `analysis.duration_seconds` (the sum of recorded stage durations).
  - **Deferred:** chat-first intake that replaces the intake form, the period picker sheet, and the numeric score gauge (Phase 2).
- **Fixes found by verification.** A resumed run can record a stage without a duration, so the total skips null values. `browser_phase03.py` now toggles `already_sent_money`, because Scenario F already starts at "yes".
- **Checks.**
  - `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed **138**.
  - `npm --prefix frontend run build` passed.
  - The Byte Bot API on 8000 was restarted in fixture mode.
  - With `BYTEBOT_WEB_URL=http://127.0.0.1:5174`, `browser_presentation.py`, `browser_smoke.py`, `browser_phase03.py` (all A–K, about 1.4 seconds each), and `browser_phase04.py` passed.
  - Screenshots in `.cache/phase4/` were inspected: history, Scenario B chat before and after approving the hold, risk factors, and Scenario J follow-up chips.
  - `browser_phase02.py` (real CPU OCR) and `browser_phase05.py` (screenshot rehearsal 3.23 seconds) also passed, so all six browser suites pass after Phase 4.

## 2026-11-14 — AI teammate Phase 5 (human console)

- **Complete.** Added migration 008, `console.py`, `console.tsx`, and `console.css`, with human actor support in `actions.py` and the assignee in the customer escalation view. Contracts are in [architecture](architecture.md#implemented-teammate-phase-5-contracts-human-console).
- **Checks.**
  - `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed **143**, including the new `test_console.py`: separate session in both directions, escalated-only access with a masked customer ID, priority ordering, human approve/reject with a `SIM-1930-…` receipt visible to the customer, redacted notes, resolution and re-escalation, the notification feed, integrations, and undo.
  - `npm --prefix frontend run build` passed.
  - From `backend/`, `bytebot.cli migrate` (twice) passed on the demo database, and the Byte Bot API on 8000 was restarted in fixture mode.
  - `browser_presentation.py` passed against 5174.
  - Screenshots in `.cache/phase5/` were inspected: the console case before and after approval, notifications, integrations, and the customer phone showing the human-approved draft as Done.
- **Demo data note.** Seven escalations created by earlier rehearsal sessions in the local demo database were marked resolved, so the queue starts clean. This affected only local demo rows.
- **Pending.** The workspace browser suites were not rerun after Phase 5. Their screens were unchanged in this phase.

## 2026-11-14 — AI teammate Phase 6 (Sarvam AI)

- **Complete.** Sarvam replaces Gemini as the live provider. The key is stored only in the gitignored `.env` (verified absent from source and docs). `.env` now sets `BYTEBOT_EXTRACTION_MODE=sarvam`, and `.env.example` documents `SARVAM_API_KEY` blank.
  - **Added:** `sarvam.py`, `voice_routes.py`, migration 009, Hinglish rules, Scenario L, `voice-ui.tsx` (record or upload a voice note, Listen to guidance in 11 languages), `sarvam_smoke.py`, and `test_voice.py`. Contracts are in [architecture](architecture.md#implemented-teammate-phase-6-contracts-sarvam-ai).
- **API notes found during integration.**
  - `reasoning_effort: none` is rejected despite the docs.
  - `sarvam-105b` took 12.9 seconds with low reasoning; `sarvam-105b-conversations` took 0.4–0.8 seconds, so it is the extraction model.
  - Mayura translated the Hinglish "wapas karo" loosely, so local Hinglish rules and the original-language transcript are kept.
- **Checks.**
  - `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed **153**. One earlier run made a single live Sarvam extraction call with synthetic Scenario A text, because a test built the app from the local `.env`; `conftest.py` now blocks live providers.
  - `npm --prefix frontend run build` passed.
  - `.\.venv\Scripts\python.exe backend/tests/sarvam_smoke.py --live` (synthetic content only): text-to-speech 1.85 seconds, speech-to-text 0.52 seconds (detected `hi-IN`), translation 0.87 seconds. Extraction: B 0.47 seconds (complete), L 0.52 seconds (complete), H 0.37 seconds (complete), G 0.44 seconds (partial; the amount claim was discarded).
  - **Live browser run on 5174 with the API in `sarvam` mode.** A synthetic Hindi voice note generated by Sarvam text-to-speech was uploaded and transcribed and translated in 1.87 seconds. After confirmation, analysis with live Sarvam extraction returned **High concern** in 2.44 seconds. "Listen" in Hindi returned translated guidance with audio. Screenshots are in `.cache/phase6/`.
- **Services.** From `backend/`, `bytebot.cli migrate` and `seed` passed on the demo database. The Byte Bot API on 8000 now runs with `BYTEBOT_EXTRACTION_MODE=sarvam`.
- **Pending.** The Playwright suites were written for fixture mode. Restart the API with `BYTEBOT_EXTRACTION_MODE=fixture` before running them. They were not rerun in this phase.

## 2026-11-14 — AI teammate Phase 2 (risk score and fraud graph)

- **Complete.** Added migration 010, graph seeding and the two-hop query in `intelligence.py`, the score and graph-link findings in `risk_rules.py`, `GET /investigations/{id}/intel-graph`, a gauge, weighted factors, and a fraud-graph view in the phone, and the score in the console. Contracts are in [architecture](architecture.md#implemented-teammate-phase-2-contracts-risk-score-and-fraud-graph).
- **Checks.**
  - `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed **159**. The new `test_graph_score.py` covers two-hop links (K: three incidents), the zero-weight same-ID factor with merged sources (B: 55), the category being unaffected by any weights, the 100 cap, and owner scoping of the graph endpoint.
  - `npm --prefix frontend run build` passed.
  - From `backend/`, `bytebot.cli migrate` and `seed` passed on the demo database. The API on 8000 was restarted in `sarvam` mode.
  - Live in the presentation, Scenario K showed **Needs verification · 60/100** with the mule-ring graph. Screenshots are in `.cache/phase2/`.
- **Pending.** The Playwright suites need the API in fixture mode and were not rerun in this phase.

## 2026-11-14 — AI teammate Phase 7 (evaluation and metrics)

- **Complete.** Added `eval_teammate.py`, `metrics.py`, migration 011, `metrics.tsx`, feedback saving from the chat, and a presenter link. Contracts are in [architecture](architecture.md#implemented-teammate-phase-7-contracts-evaluation-and-metrics).
- **Evaluation results (12 scenarios, A–L).**
  - `.\.venv\Scripts\python.exe backend/tests/eval_teammate.py` (fixture extraction): category accuracy **100%**, escalation precision **100%** and recall **100%**, handled without a person **75%** (F, H, and K escalate by policy), **0** policy violations, injection contained, median **2** customer taps, **12/12** reports prepared.
  - `... eval_teammate.py --sarvam` (live Sarvam extraction, synthetic text only): the same results, with a median analysis of **0.51 seconds**.
- **Checks.**
  - `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed **161**. The new `test_metrics.py` covers owner-scoped strict feedback and outcome counts without personal data.
  - `npm --prefix frontend run build` passed.
  - From `backend/`, `bytebot.cli migrate` passed on the demo database, and the API on 8000 was restarted in `sarvam` mode.
  - `/metrics` was screenshotted at 1440 px and 390 px with no horizontal page overflow (`.cache/phase7/`).
- **Notes.** The live demo tiles count every local demo session, including earlier automated rehearsals; for example, a median analysis of 0.01 seconds reflects in-process fixture runs. Review minutes saved is an estimate, not a measurement.

## 2026-11-14 — AI teammate Phase 8 (security hardening)

- **Complete.** Added `docs/threat-model.md`, migration 012 with the hash-chained ledger and verifier, the console "Ledger verified" badge, `security.py` (rate limits and headers), preview CSP and permissions in `vite.config.ts`, Hinglish and extra English injection patterns, and `test_security.py`. Contracts are in [architecture](architecture.md#implemented-teammate-phase-8-contracts-security-hardening).
- **Test changes.** `test_reports::test_phase03_upgrade_backfill_repeatability` rebuilds the historical audit table, so it now also re-applies migration 012 (the ledger columns belong to that table).
- **Checks.**
  - `.\.venv\Scripts\python.exe -m pytest backend/tests -q` passed **186**. The new `test_security.py` (25 cases) covers:
    - the 8-string English and Hinglish injection corpus and the benign corpus (with one deliberate broad match);
    - injected evidence never lowering the category and never auto-running account steps;
    - six hostile provider outputs contained;
    - ledger edit and deletion detection, and the console ledger status;
    - per-session rate limits, with speech limited separately;
    - security headers.
  - `npm --prefix frontend run build` passed.
  - From `backend/`, `bytebot.cli migrate` passed on the demo database.
  - Restarted only the Byte Bot API (8000, `sarvam` mode) and the preview (4174).
  - **Playwright on the 4174 preview with the strict CSP.** Scenario F analysis, the fraud graph, the console with "Ledger verified", and `/metrics` loaded with **no console errors or CSP violations**. Screenshot: `.cache/phase8/console-ledger.png`.

## 2026-11-14 — Story verification: the four cases

- **Complete.** Repositioned Byte Bot as "verifies the story behind a suspicious payment" and closed the gaps from the coverage check.
  - **Case 1:** `claims.py` adds `POST /api/v1/claim-check`, which searches the owner's own history for the claimed amount and sender. It returns `not_found | not_completed | verified | ambiguous | need_amount` with a verdict and the six-question story. It stores nothing and makes no provider call. The phone has a "Someone says they paid you?" card and a `/check-payment` screen.
  - **Case 3:** new `qr_payment` and `pin_to_receive` markers (English and Hinglish) in `safety.py`; `qr.py` decodes QR codes in memory with OpenCV (already installed with EasyOCR) and parses `upi://pay`. Screenshot uploads keep only the parsed payee and amount. A new decision, `outgoing-payment-mechanism` (High concern), covers QR, PIN-to-receive, and collect requests. Scenario N uses a synthetic refund QR (`backend/bytebot/demo_assets/refund-qr.png`).
  - **Case 4:** the simulated graph gains a sender (`rahul.demo@upi`) linked to three incidents and two repayment recipients; Scenario O. Planner adds a bank ticket when a genuine credit is linked to fraud.
  - **Presentation:** `Assessment` gains display-only `headline` and `story` fields. The phone shows the verdict banner and the six questions. The presenter has "Three worlds" buttons. The fraud graph adds a repayment-recipient column.
- **Fixes found on the way.** Redaction is not idempotent (evidence is redacted on save and again before extraction), so fixture matching now accepts either pass, and the fixture allow-list includes the redacted text.
- **Checks.**
  - `.\.venv\Scripts\python.exe -m pytest backend/tests -q`: **209 passed** across two runs (194 plus 15 `test_demo` cases after updating the scenario list to A–O). The new `test_story.py` (14 cases) covers the four cases, QR parsing, markers and negation, and the six-question story.
  - `eval_teammate.py` (fixture) across A–O: category accuracy **100%**, escalation precision and recall **100%**, handled without a person **80%**, **0** policy violations, **15/15** reports.
  - `npm --prefix frontend run build` passed.
  - From `backend/`, `bytebot.cli seed` added the M–O templates and graph rows to the demo database; the API on 8000 was restarted in `sarvam` mode.
  - Playwright on the 5174 dev server (live Sarvam): world 1 Scam warning, world 3 Dangerous payment action with the story, world 1 verified after the credit exists, and Case 4 Suspicious network with the fraud graph; **no page errors**.
- **Not run.** The seven earlier browser suites (they need a fixture-mode API).
- **Note.** The RBI discussion-paper point from the pitch is not cited in the docs yet; confirm the exact source and wording first.
- **Environment.** PostgreSQL still runs on **55434** because Windows refused to bind 55433; `.env` points there.

## 2026-11-14 — Presentation UI redesign ("Story Board")

- **Complete.** Redesigned the presentation, console and metrics for a 1440×900 screen share (plan: senior UX/UI review). No backend logic changed.
  - **Stage:** one no-page-scroll frame at desktop widths: a dark stage, the light phone scaled to the viewport height, a top bar (tagline, active world, live/fixture mode, links), and a bottom presenter dock (four worlds, scenario selector, Load, Reset, keyboard shortcuts 1–4, Space, R, F).
  - **Story Board** (`stage/`): an empty-state hook, then a CSS-only reveal keyed to each run (agents, the six questions, the verdict with the gauge, the proof panel, supervisor decisions, actions) with Replay; reduced motion shows the final state at once. Proof panels: ledger scan (Case 1, via the new `useClaimSnapshot` bridge), message X-ray (Case 2), money direction parsed from the QR finding (Case 3), and a stage-size fraud graph (Case 4).
  - **Phone results** (presentation mode only): compact verdict, the assessment, the safety warning, then the assistant with consent cards, the report and the case status; the long lists collapse into one Details disclosure. The story and risk overview now live on the stage. The investigation screen shows the review card with **Analyze & prepare report** first.
  - **Design system:** `tokens.css` (brand, stage surfaces, tone tokens for light and stage, type, space, radii, elevation, motion, keyframes, global reduced motion). Contrast fixes: the "Unexpected credit" flag and green amounts now meet AA; teal accents unified to the phone blue.
  - **Console:** fits the viewport with internal scrolling, adds the verdict banner, a visual audit chain, and action toasts. **Metrics:** a hero KPI band, an A–O scenario matrix with a table view, and the most recent evaluation run by default.
- **Tests updated.** `browser_teammate.py` now finds the risk gauge, the stage verdict and the six-step story on the stage. `browser_phase03.py` treats Scenario O as graph-linked (it loops over every fixture scenario and O was added with the four-case work).
- **Checks.**
  - `npm --prefix frontend run build` passed.
  - API restarted in **fixture** mode on 8000; all seven browser suites passed: `browser_smoke`, `browser_phase02` through `browser_phase05` and `browser_presentation` on 5174, and `browser_teammate` on the 4174 preview.
  - A scratch Playwright stage tour of the empty state and worlds 1–4 passed at 1440×900 (dev and preview) and 1280×720, with no page scroll at either size and no page errors. Horizontal overflow checked at 1440, 390 and 320.
  - Backend unchanged, so pytest was not re-run.
