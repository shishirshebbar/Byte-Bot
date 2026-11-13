# Phase 04 Reports and follow-up

## Prerequisites

Phase 03 passes. Read PRD FR-13, FR-14, and FR-16, [report architecture](../architecture.md#analysis-and-reporting), and [AT-12](../acceptance.md#prd-acceptance-cases).

## Implementation order

1. Add report and audit persistence. Capture investigation creation, evidence submission and removal, analysis completion, report generation, and status updates. Backfill earlier audit events only when the required facts are already available. Keep audit metadata free of raw evidence and credential values.
2. Generate a report snapshot for the current assessment revision. Include a report ID and generation timestamp, original transaction facts, the user's statements, redacted evidence, findings with provenance, category, unknowns, and recommended next steps. Render HTML for review and a UTF-8 text attachment from the same stored snapshot.
3. Implement **My Incidents** with creation date, current category when available, user-managed status, and links to reopen cases. Use the PRD statuses Open, Bank Contacted, Reported, Awaiting Response, Resolved, and Closed. The user records actions taken outside the app.
4. Use the post-loss guidance when the user reports sending money. Recommend preserving evidence and contacting their bank and official reporting channels. Keep any recovery outcome uncertain.
5. Make the revision invalidation path clear in the browser. A changed case can be analyzed again and used to generate a fresh report. Reject report retrieval for stale snapshots.

## Expected files and contracts

- Report and audit migrations, snapshot builder, UTF-8 formatter, and owner-scoped report and incident routes.
- React report view, text-download control, My Incidents list, and status controls.
- Report content, status, invalidation, audit, and ownership tests. Use the [Phase 04 endpoints](../architecture.md#rest-interface).

## Verification and exit checklist

Run `python -m pytest backend/tests` with the project virtual environment and `npm --prefix frontend run build`. Generate, download, and reopen a report in the browser.

- [x] The report and download include every AT-12 field, including ₹ text rendered correctly.
- [x] A user can set all six case statuses and reopen the case with the saved status.
- [x] Audit events have the expected action and timestamp, with no sensitive payloads.
- [x] Editing or deleting evidence makes the previous assessment and report unavailable on the server.
- [x] Post-loss guidance appears when applicable, and a second session cannot retrieve or update the case.
- [x] Record AT-12 and the remaining AT-10 coverage in [progress](../progress.md).

Implementation and verification completed 2026-11-13; see the [Phase 04 progress entry](../progress.md#2026-11-13--phase-04-reports-and-follow-up-complete). Optional live Gemini verification remains separately pending local configuration from Phase 03. Phase 05 is not started.
