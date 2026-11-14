# Verification

Use the [setup guide](setup.md) first. Run commands from the repository root with the project Python environment. Use synthetic evidence only. Commands below describe how to verify a checkout; dated results are in [progress](progress.md), and expected behavior is in [acceptance](acceptance.md).

## Backend and frontend

Create the separate `bytebot_test` database once as described in setup, then run:

```bash
.venv/bin/python -m pytest backend/tests -q
.venv/bin/python -m pip check
npm --prefix frontend run build
docker compose --env-file .env.example config --quiet
```

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m pip check
npm --prefix frontend run build
docker compose --env-file .env.example config --quiet
```

Pytest repeatedly drops and rebuilds the test database's public schema. Its guard requires database name `bytebot_test` and a different host/port/database identity from `DATABASE_URL`. Never point it at a database holding data you need, and do not run separate pytest invocations against that same database concurrently.

Coverage includes migration rollback/checksums/repeatability, seeds, actual payment statuses, ownership denial, input validation/redaction, revision conflicts, analysis races/leases/fallback, report invalidation, audit privacy, and session-reset isolation. Routine tests inject synthetic OCR/provider adapters and do not require OCR downloads or a live Gemini key. The completed MVP baseline is **94 tests**; counts may grow as development continues.

The frontend build runs TypeScript checking and Vite bundling. Existing dependency-level React Router `use client` warnings are nonblocking; build errors must be fixed.

## Migrations and seeds

For a developer-controlled demo database, from `backend/`:

```bash
../.venv/bin/python -m bytebot.cli migrate
../.venv/bin/python -m bytebot.cli migrate
../.venv/bin/python -m bytebot.cli seed
../.venv/bin/python -m bytebot.cli seed
```

PowerShell uses `..\.venv\Scripts\python.exe` for each command. Migrations must preserve applied checksums and the second run must apply no changes. Repeated seeds must not duplicate templates or alter owned records. These commands may apply pending migrations and insert missing templates; use the automated tests for isolated assertions:

```bash
.venv/bin/python -m pytest backend/tests/test_foundation.py -q
```

Do not edit applied migrations to make a checksum failure disappear. Add the next numbered migration instead.

## Browser acceptance

Start a fixture API on 8000 and the frontend on 5174 using [setup](setup.md#start-the-applications). Real OCR dependencies/models are required for the complete Phase 02 and Phase 05 screenshot journeys.

Install the browser once:

```bash
.venv/bin/python -m playwright install chromium
```

On Linux hosts missing browser system libraries, use Playwright's `install-deps chromium` command with the permissions required by that host.

```bash
BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_smoke.py
BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase02.py
BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase03.py
BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase04.py
BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_phase05.py
BYTEBOT_WEB_URL=http://127.0.0.1:5174 .venv/bin/python backend/tests/browser_presentation.py
```

In PowerShell, set `$env:BYTEBOT_WEB_URL = 'http://127.0.0.1:5174'`, then invoke each script with `.\.venv\Scripts\python.exe`. Pass the frontend origin. The first five scripts exercise `/workspace` and the presentation script exercises `/`. Use port 4174 for a production preview after building.

| Suite | Main coverage |
| --- | --- |
| Foundation smoke | History, successful/pending/failed details, ownership, navigation, retries, mobile |
| Phase 02 | Intake, OCR review/removal/fallback, redaction, stale edits, unsaved navigation |
| Phase 03 | A–E categories, progress/reuse/retry, input invalidation, provenance, ownership |
| Phase 04 | UTF-8 report snapshots/downloads, six statuses, ownership, stale reports, privacy |
| Phase 05 | Scenario selection, isolated/repeated reset, screenshot-to-report rehearsal, keyboard/mobile |
| Presentation | Three fresh Scenario B runs, one-approval report, UTF-8 download, report retry, saved follow-up and reopen, panel synchronization, ownership, reset, keyboard operation, four viewport sizes |

The presentation suite records timings in `.cache/paytm-presentation/timings.json`. Its Scenario B measurement starts with the approval on the saved case and ends when the report has downloaded and **Bank Contacted** is saved. It checks report reopening after the measurement.

Browser suites create synthetic session data in the running demo database. They do not reset the whole demo database. Screenshots, synthetic images, downloaded reports, and timings are local ignored artifacts under `.cache/phase01/` through `.cache/phase05/`. Regenerate them locally; they are not part of the published source. Historical progress descriptions of those files record earlier inspections, not publicly accessible attachments.

## Real OCR

After [OCR setup](setup.md#optional-local-ocr):

```bash
.venv/bin/python backend/tests/ocr_smoke.py
```

This checks actual CPU EasyOCR with legible/unreadable synthetic images. Server inputs remain in memory. For the manual screenshot walkthrough, generate a synthetic PNG using [the demo instructions](demo.md#screenshot-walkthrough).

## Optional live Gemini

With both local Gemini settings configured:

```bash
.venv/bin/python backend/tests/gemini_smoke.py --live
```

The check submits only an in-memory synthetic message and saves no evidence/provider response. It prints model, status, extracted kinds, and duration. Missing key/model returns **PENDING** with exit code **2** and makes no provider request. Record a configured live outcome separately; fixture timings do not measure Gemini performance.

## Recording results

Update [progress](progress.md) with exact commands, environment/provider mode, passed cases, timing, and pending verification. Keep the [acceptance matrix](acceptance.md) aligned with current tests. Do not label historical browser/OCR runs as newly executed. A phase is complete only after its documented exit criteria pass.
