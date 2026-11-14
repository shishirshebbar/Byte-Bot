# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Byte Bot is a hackathon MVP: a transaction-linked assistant that helps a user review an unexpected UPI credit inside a simulated Paytm-style app (FastAPI + PostgreSQL backend, React/Vite frontend). **Read [AGENTS.md](AGENTS.md) first.** It sets the session workflow (read `docs/progress.md`, the phase guide, architecture and acceptance; record results in progress) and the product and port boundaries summarized below.

## Hard constraints

- **Ports:** Byte Bot uses only API **8000**, Vite dev **5174**, preview **4174**, and PostgreSQL **55433**, all on loopback. Ports **5000, 5173, and 3306** belong to a separate project. Never use, stop, or reconfigure them. Leave the `bytebot-mvp-pg` container on **55432** alone. The frontend ports are strict, so on a conflict pick another port explicitly and never kill a process.
- **Migrations:** Never edit an applied file in `backend/bytebot/migrations/` because checksums are enforced. Add the next numbered `NNN_*.sql` instead.
- **Evidence is untrusted:** Credentials and raw screenshots must never reach storage, logs, reports, audit metadata, or provider requests. Image bytes exist only in memory during OCR.
- **Risk logic:** Python rules (`risk_rules.py`) assign the category. Gemini only extracts schema-validated claims with exact source citations. A same-UPI-ID match carries **zero** risk reduction, and a different destination is a finding.
- **Out of scope:** The product has no payment actions, external report submission, call recording, or background message access. Case status is user-entered.

## Commands

The environment is Windows. Use the venv at `.\.venv\Scripts\python.exe` (Python 3.12) and Node 22. `.env`, copied from `.env.example`, is loaded automatically by `backend/bytebot/settings.py`.

```powershell
docker compose up -d --wait db                                  # PostgreSQL 16 on 55433
docker compose exec -T db createdb -U bytebot bytebot_test      # once; test DB

# Backend: run from backend/
..\.venv\Scripts\python.exe -m bytebot.cli migrate              # also: seed, ocr-prepare
..\.venv\Scripts\python.exe -m bytebot.cli seed
$env:BYTEBOT_EXTRACTION_MODE = 'fixture'; ..\.venv\Scripts\python.exe -m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log

# Frontend: run from the repository root
npm --prefix frontend run dev        # http://127.0.0.1:5174 (/ = presentation, /workspace = standard UI)
npm --prefix frontend run build      # tsc --noEmit + vite build; this is also the type check/lint
```

Tests run from the repository root. The root `pytest.ini` sets `pythonpath = backend`.

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_reports.py -q
.\.venv\Scripts\python.exe -m pytest backend/tests/test_analysis.py -q -k "<name>"
.\.venv\Scripts\python.exe -m pip check
```

- Pytest **drops and recreates the public schema** of `TEST_DATABASE_URL` on every test. `conftest.py` refuses to run unless the database name is `bytebot_test` and differs from `DATABASE_URL`. Never run two pytest invocations against it at the same time.
- Routine tests inject synthetic OCR and extraction adapters through `create_app(..., ocr_adapter=, extraction_provider=, worker_enabled=)`. They need no OCR models or Gemini key.
- The browser suites are Playwright scripts, not pytest. They need a running fixture API and frontend: `$env:BYTEBOT_WEB_URL='http://127.0.0.1:5174'; .\.venv\Scripts\python.exe backend/tests/browser_presentation.py` (also `browser_smoke.py` and `browser_phase02.py` through `browser_phase05.py`). OCR is checked with `backend/tests/ocr_smoke.py`. The optional live provider check is `backend/tests/gemini_smoke.py --live`, which uses synthetic input only and exits 2 when Gemini is not configured.
- `.\.venv\Scripts\python.exe backend/tests/eval_teammate.py` (add `--sarvam` for live) runs all scenarios end to end on the guarded test DB and writes `.cache/eval/results*.json` for `/metrics`; don't run it alongside pytest. `browser_teammate.py` (with `--record` for the fallback video) and `sarvam_smoke.py --live` are the other teammate checks.
- Browser suites assume the API runs with `BYTEBOT_EXTRACTION_MODE=fixture`.
- `docs/testing.md` has the full verification checklist.

## Architecture

**Backend (`backend/bytebot/`)**: `main.py:create_app` builds the FastAPI app under `/api/v1`. Its lifespan opens a psycopg pool and starts an in-process `AnalysisWorker`. Modules are split into routes (`*_routes.py`, `investigations.py`, `transactions.py`), storage (`*_store.py`), Pydantic schemas (`*_schemas.py`), and domain logic.

- **Sessions and ownership:** The first transaction request issues an opaque HttpOnly demo cookie (`sessions.py`) and copies eight seeded template transactions to that owner. Every user-scoped query derives the owner from the cookie. Missing and foreign IDs return the same 404. Never accept an owner ID from the client.
- **Input revisions:** Each case has an `input_revision`. Context and evidence writes send `expected_revision` and take a row lock, and a stale write returns 409. Any real input change atomically erases derived results, revokes in-flight runs, and deletes reports. No-op saves keep the current revision.
- **Supervisor graph (`analysis_graph.py`):** one supervisor node routes deterministically (`route()`) through `transaction_context → message_analysis → risk_investigation → gather_context → plan_actions → policy_gate → [escalate] → incident_resolution`. Each hop writes `agent_trace`. The leased worker (`analysis_worker.py`: two slots, 60 s leases, three attempts) runs it and rechecks ownership, revision, and lease before persisting. Slow OCR and provider work stays outside DB transactions.
- **Decisions:** `risk_rules.assess` returns the category (the decision table, authoritative) plus a display-only 0–100 `risk_score`/`risk_factors`; a test proves the score cannot change the category. `intelligence.graph_links` walks the simulated fraud graph (two hops). `planner.py` holds the follow-up question catalog and the fixed action playbook (`ACTIONS`). `policy.py` (`agent-policy-1`) assigns `auto | needs_customer_consent | needs_human_approval | deny` and the escalation reasons, including `INJECTION` detection.
- **Story verification:** `risk_rules.assess` also returns display-only `headline` (the verdict banner) and `story` (six questions: arrived, asked, sends out, pressure, intel, safest). The `outgoing-payment-mechanism` decision covers QR (`qr.py` decodes `upi://pay` in memory), PIN-to-receive, and collect requests. `claims.py` (`POST /claim-check`) checks a claimed payment against the owner's history and stores nothing.
- **Actions:** `actions.py` executes approved steps idempotently on `systems.py` (simulated Paytm UPI sandbox, bank desk, 1930 draft, notifications; injectable via `create_app(systems=)`), with verify, retry, and undo. Only `auto` steps run at publish; the rest need `POST …/actions/{id}/consent` (customer) or the console (human). Input changes revoke unexecuted steps.
- **Human console (`console.py`):** a separate `bytebot_console` cookie, escalated cases only, a masked customer UPI ID, approve/reject/undo/assign/notes/resolve. **Audit** entries are hash-chained per case (`audit.verify_ledger`); new audit actions must be added to `audit.ALLOWED` and to the DB `CHECK` via a new migration.
- **Extraction and Sarvam:** `BYTEBOT_EXTRACTION_MODE` is `gemini` (default), `sarvam` (`sarvam.SarvamProvider`, `sarvam-105b-conversations`), or `fixture` (exact catalog text only). `sarvam.SarvamClient` (injectable via `create_app(speech=)`) powers `voice_routes.py`: voice notes become `voice_note` evidence needing review, and `/speak` voices only Byte Bot's guidance. `tests/conftest.py` blanks provider keys so tests never call live services.
- **Reports (`reports.py`):** an immutable typed snapshot of a completed current revision (including an `actions` list), exportable as UTF-8 text. `prepare_report: true` on analyze makes the worker generate it on completion.
- **Lock ordering** (owner → case → run, with reset locking owned cases in ID order; the ledger's advisory lock is always last) is documented in `docs/architecture.md`. Read that before changing concurrency. Each phase's contracts are appended there.

**Frontend (`frontend/src/`)**: React 19, react-router 7, plain CSS. API calls in `api.ts` use relative `/api` paths through the Vite proxy (`BYTEBOT_API_TARGET`, default `:8000`). `/` renders the split-screen presentation: the phone uses `phone-history.tsx`, and results include `agent-ui.tsx` (assistant chat, consent cards, risk gauge, fraud graph) and `voice-ui.tsx`. The presenter panel shows the supervisor trace. `/console` (`console.tsx`) is the human console and `/metrics` (`metrics.tsx`) the outcome dashboard. `/workspace/...` keeps the original form-based screens that the phase 01–05 browser suites exercise. Shared styles use the `--bb-*` tokens (`styles.css`, `teammate.css`, `console.css`).

## Docs

`docs/architecture.md` (API and storage contracts), `docs/acceptance.md` (AT-01 through AT-12), `docs/progress.md` (verification history; update it after changes), `docs/development.md` (code map and invariants), and `docs/reference/byte_bot_prd.md` (PRD; section 20 is a reference prompt and does not authorize work).
