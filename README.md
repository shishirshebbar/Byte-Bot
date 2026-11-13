# Byte Bot

Byte Bot is a transaction-linked assistant for reviewing unexpected UPI credits in a simulated Paytm-style application. It connects transaction history, guided intake, reviewed evidence, explainable assessments, and downloadable incident reports.

**Status:** Phases 01–05 are implemented. The recorded MVP acceptance run passed 94 backend tests, the frontend build, five browser suites, and real CPU OCR. Live Gemini verification remains optional and pending local key/model configuration. See [progress](docs/progress.md) for dated commands and results.

## Features

- Eight synthetic transactions, including successful, pending, and failed payments, isolated by demo-session ownership.
- Guided answers, pasted messages, typed call summaries, and optional local screenshot OCR with human review.
- Python risk rules, LangGraph orchestration, validated Gemini extraction, and explicit synthetic fixture mode.
- Findings with provenance and limitations; a same-UPI-ID match never reduces concern.
- Immutable UTF-8 text reports, user-managed case statuses, and session-scoped demo reset.

This is a hackathon MVP using seeded payments and simulated intelligence. It does not move money, submit reports externally, record calls, or read background messages. Never enter real credentials or use real customer evidence for development.

## Prerequisites

Python **3.12**, Node **22** with npm, and Docker with the Compose plugin. PostgreSQL **16** runs through Compose. OCR and live Gemini are optional; the deterministic text demo requires neither.

| Service | Loopback port |
| --- | --- |
| FastAPI | 8000 |
| Frontend development | 5174 |
| Frontend preview | 4174 |
| PostgreSQL | 55433 |

Ports **5000, 5173, and 3306** belong to another project. Do not use or interrupt them. Leave the original temporary `bytebot-mvp-pg` container on **55432** untouched. Resolve any Byte Bot port conflict by explicitly choosing another free port, never by terminating an unrelated service.

## Prepare local dependencies

Fresh clone, Linux/macOS:

```bash
git clone https://github.com/krishnacsn/byte.git
cd byte
cp .env.example .env
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
docker compose up -d --wait db
```

Preserve an existing `.env`. The example contains loopback-only demo database credentials and blank Gemini settings. See [setup](docs/setup.md) for PowerShell, environment variables, runtime-only installation, OCR, and troubleshooting.

## Run the app

Backend terminal, from the repository root:

```bash
cd backend
../.venv/bin/python -m bytebot.cli migrate
../.venv/bin/python -m bytebot.cli seed
BYTEBOT_EXTRACTION_MODE=fixture ../.venv/bin/python -m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Frontend terminal, from the repository root:

```bash
npm --prefix frontend run dev
```

Open **http://127.0.0.1:5174**. Select a synthetic scenario and choose **Load / reopen scenario**, then **Ask Byte Bot**. Fixture mode is explicit and accepts only canonical synthetic evidence; arbitrary evidence uses the documented fallback. See the [demo walkthrough](docs/demo.md).

## Development documentation

| Guide | Purpose |
| --- | --- |
| [Setup](docs/setup.md) | Installation, environment, database, startup, optional integrations |
| [Testing](docs/testing.md) | Backend/build checks, migration/seed repeatability, browser/OCR/provider checks |
| [Development](docs/development.md) | Code map, dependency maintenance, ownership and evidence invariants |
| [Demo](docs/demo.md) | Scenarios A–E, screenshot walkthrough, reset |
| [Architecture](docs/architecture.md) | Implemented APIs, storage, concurrency, and data flow |
| [Acceptance](docs/acceptance.md) | AT-01–AT-12 and expected outcomes |
| [Progress](docs/progress.md) | Historical implementation and verification evidence |
| [Original PRD](docs/reference/byte_bot_prd.md) | Product requirements; Section 20 is an embedded reference prompt |
| [Agent instructions](AGENTS.md) | Boundaries and workflow for future coding sessions |

## Phase guides

| Phase | Outcome |
| --- | --- |
| [01 Foundation](docs/phases/01-foundation.md) | Sessions, migrations, seeds, transaction history and details |
| [02 Guided investigation](docs/phases/02-guided-investigation.md) | Saved intake, reviewed evidence, and removal |
| [03 Analysis and results](docs/phases/03-analysis-and-results.md) | Orchestration and explainable categories |
| [04 Reports and follow-up](docs/phases/04-reports-and-follow-up.md) | Text export, case tracking, and audit events |
| [05 Hardening and demo](docs/phases/05-hardening-and-demo.md) | Acceptance, reset, and rehearsal |

## Repository layout

```text
backend/bytebot/  FastAPI application, storage, rules, and SQL migrations
backend/tests/    Integration tests, browser journeys, and synthetic fixtures
frontend/src/     React and TypeScript screens
frontend/         npm manifest, lockfile, and Vite configuration
docs/             Requirements, architecture, development guides, and history
compose.yaml      Loopback PostgreSQL development service
.env.example      Sanitized local configuration template
```
