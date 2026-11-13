# Phase 01 Foundation

## Prerequisites

Follow the [local setup](../setup.md#install-dependencies) and confirm the user has authorized Phase 01. Start the local Compose database and create the separate test database. Read [architecture](../architecture.md#rest-interface) and PRD FR-01 and FR-07.

## Implementation order

1. Create the FastAPI entry point, environment settings, database pool, and shared API error handling. Load the project-root `.env` for the CLI and server with a declared dotenv dependency. Add database readiness under `/api/v1/health`.
2. Add an ordered SQL migration runner and the initial demo user/session and transaction schema. Record applied migrations and serialize application of pending versions. Create an idempotent seed command that installs the synthetic transaction templates. Include successful, pending, and failed examples.
3. Issue an opaque session cookie on first use. Seed each new session's transactions from templates inside a database transaction, then return the same owned data on later requests. Use parameterized queries and enforce ownership on transaction lookups.
4. Implement the transaction list and detail APIs, then add the React entry point, router, API client, and both screens. Show amount, sender, UPI ID, timestamp, reference, and actual status. Leave the **Ask Byte Bot** case-creation flow for Phase 02.
5. Add migration, seed, ownership, and transaction API integration tests. Configure pytest so `backend/tests` can run from the project root, and keep the test database separate from the demo database.

## Expected files and contracts

- `backend/bytebot/main.py`, `cli.py`, settings, database and session modules, and `migrations/001_foundation.sql`.
- Synthetic transaction templates, transaction API schemas and routes, and tests in `backend/tests/`.
- `frontend/src/main.tsx`, transaction screens, shared shell, and typed API client.
- Follow [storage and evidence](../architecture.md#storage-and-evidence) for amounts and timestamps. CLI entry points are `python -m bytebot.cli migrate` and `python -m bytebot.cli seed`, run from `backend/`.

## Verification and exit checklist

Run the [application launch commands](../setup.md#start-the-applications), `python -m pytest backend/tests` from the project root using the project virtual environment, and `npm --prefix frontend run build`.

- [ ] Applying migrations and seeds twice leaves data consistent and creates no duplicates.
- [ ] A new browser session can browse seeded transactions and reload a detail page.
- [ ] Success, pending, and failed labels reflect the database records.
- [ ] A second cookie jar receives `404` for the first session's transaction ID.
- [ ] Test and build results are recorded in [progress](../progress.md).
