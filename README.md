# Byte Bot

Byte Bot is an AI fraud-resolution teammate for unexpected UPI credits in a simulated Paytm-style app. It goes beyond answering questions. It understands the payment and the customer's story (including Hindi and Hinglish voice notes via Sarvam AI), decides with explainable rules, takes consented actions on simulated Paytm, bank, and 1930 systems, and hands off to a human console only when policy requires it.

**Status:** AI-teammate phases 0–9 are complete. The last full verification passed 186 backend tests, the frontend build, seven browser suites on the production preview, and real CPU OCR. Across 12 end-to-end scenarios, the evaluation shows 100% category accuracy, 100% escalation precision and recall, 75% handled without a person, and 0 policy violations, both offline and with live Sarvam extraction. See [progress](docs/progress.md) and the [demo script](docs/demo.md).

## Features

- **One main agent and four specialists.** A LangGraph supervisor routes Transaction Context, Message Analysis, Risk Investigation, and Incident Resolution. It asks only the follow-ups that change the decision and records a live decision trace.
- **Decides safely.** Python rules assign the category. An explainable 0–100 score and weighted factors explain it, and the score never changes the category. A same-UPI-ID match never reduces concern. A simulated fraud graph finds two-hop links to reported incidents.
- **Acts across systems.** A fixed playbook (dispute hold, block UPI ID, decline collect, bank dispute ticket, 1930 complaint draft, notification) is gated by a versioned policy: automatic, customer consent, human approval, or deny. Execution is idempotent and verified, with receipts and undo.
- **Escalates only when needed.** Money already sent, prompt injection, high value, conflicting or unreadable evidence, unanswerable questions, or a customer request. A human console has a queue, handoff brief, approvals, notes, and a tamper-evident ledger.
- **Indic-first with Sarvam AI.** Voice notes (speech-to-text and translation, with the original words kept), spoken guidance in 11 languages, live extraction, and Hinglish scam rules.
- **Measurable.** An evaluation harness, a `/metrics` dashboard, and in-chat feedback.
- **Secure by design.** Redaction and masking before any provider call, ownership on every operation, a strict schema and citation validation, rate limits, a strict CSP, and a [threat model](docs/threat-model.md).
- **The original MVP remains.** Synthetic transactions, guided intake, OCR with review, immutable UTF-8 reports, case statuses, and session reset.

This is a hackathon MVP using seeded payments, simulated intelligence, and simulated account systems. A supervisor agent asks follow-up questions, plans policy-gated steps, and escalates to a person when needed. It does not move real money, submit reports externally, record calls, or read background messages. Never enter real credentials or use real customer evidence for development.

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
git clone https://github.com/shishirshebbar/Byte-Bot.git
cd Byte-Bot
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

Open **http://127.0.0.1:5174** for the split-screen Paytm-style presentation, **/console** for the human teammate console, and **/metrics** for outcomes. Choose **Load / reopen scenario**, then **Ask Byte Bot** and **Analyze & prepare report** in the phone. The [standard workspace](http://127.0.0.1:5174/workspace) is available for testing and the alternate screenshot walkthrough. See the [demo walkthrough](docs/demo.md).

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

- [AI teammate plan](docs/teammate-plan.md) (active): supervisor agent, simulated actions, human console, Sarvam, metrics
- [Paytm hackathon presentation plan](docs/paytm-hackathon-plan.md) (complete)

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
