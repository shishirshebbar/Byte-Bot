# Phase 05 Hardening and demo

## Prerequisites

Phases 01–04 pass. Read PRD Sections 17–19 and the [acceptance matrix](../acceptance.md). Use separate browser sessions for the reset and ownership checks.

## Implementation order

1. Add a scenario selector for the five synthetic cases. Load their transactions, guided answers, and evidence through the normal case interfaces. Allow the demo to replay the same input after reset. Use fixed extraction fixtures only for the unmodified synthetic scenario inputs and identify fixture mode in the UI. New or edited evidence uses the normal extraction and fallback path.
2. Add a session-scoped reset. Restore that session's seeded transactions and clear its case, evidence, report, and audit state. Invalidate in-flight runs so a completed background request cannot repopulate the reset session. Verify that other sessions retain their data.
3. Run the complete acceptance suite. Test the browser at desktop and mobile widths with keyboard-only navigation, visible focus, readable evidence labels, and announced progress states.
4. Verify EasyOCR on real synthetic image files. When a local Gemini key and model are configured, exercise one live structured extraction with synthetic text. Record the provider mode, result, and timing.
5. Document actual run, test, seed, and reset commands. Time the seeded flow from Analyze to a visible result, after evidence submission. Rehearse the demo from a fresh reset.

## Expected files and contracts

- Scenario fixtures and selector UI, scenario loader, and session-scoped reset handler.
- Browser smoke tests, reset integration tests, and any changes needed to satisfy the acceptance matrix.
- Updated [README](../../README.md) and [progress](../progress.md) with measured results and the state of live-provider checks.

## Four-minute walkthrough

1. Reset the session and open Scenario B from transaction history.
2. Select **Ask Byte Bot** and show the original transaction facts.
3. Confirm the contact and repayment details. Upload the scenario screenshot, review the OCR text, and confirm it.
4. Start analysis and show the progress states. Explain why the threat and bank-avoidance evidence drive High concern even with the same UPI ID.
5. Generate and download the report, reopen it from **My Incidents**, then update the case status.

## Verification and exit checklist

Use the project virtual environment to run `python -m pytest backend/tests`. Install the browser test runtime with `python -m playwright install chromium`, then run the browser suite against the local app. Run `npm --prefix frontend run build`.

- [x] All 12 PRD acceptance cases and five seeded scenarios pass.
- [x] Reset is repeatable, scoped to the current session, and safe during an analysis.
- [x] Desktop, mobile, and keyboard checks pass.
- [x] Record observed seeded analysis time against the under-20-second target.
- [x] Record the real OCR check, live Gemini outcome or credential gap, and a fresh-reset demo rehearsal in [progress](../progress.md).

Completed 2026-11-13. See the Phase 05 progress entry for exact commands, timing, regression coverage, and the separately pending optional live-provider check. Scenario B's screenshot can be generated using the README command; select manual evidence mode before the first load.
