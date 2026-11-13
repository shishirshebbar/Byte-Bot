# Byte Bot acceptance and demo checks

This matrix tracks the [PRD's acceptance cases](reference/byte_bot_prd.md#17-acceptance-test-scenarios) and the implementation plan. The phase column identifies when each check is first implemented. Phase 05 reruns the full matrix.

## PRD acceptance cases

| ID | Fixture and expected result | Check | Phase |
| --- | --- | --- | --- |
| AT-01 | Scenario A. Unexpected ₹5,000, repayment request, another UPI ID, and urgency. Show each finding, Needs verification for this fixture, and bank-verification guidance. | Rules, API, browser | 03 |
| AT-02 | Scenario B. Same ID, threat, and bank avoidance. Show High concern, the matching destination and its limits, both pressure findings, and safe guidance. | Rules, API, browser | 03 |
| AT-03 | Scenario C. Same ID and polite repayment request with no intel match. Show Needs verification and uncertainty. | Rules, API | 03 |
| AT-04 | Scenario D. Expected credit from a known contact without a repayment request or suspicious evidence. Show No strong indicators found and its limitations. | Rules, API | 03 |
| AT-05 | Pending transaction. Keep its status visible and use Unable to assess. The result and report describe funds as pending. Repeat for failed or unavailable facts. | Rules, API, report | 03–04 |
| AT-06 | Scenario E. Evidence requests a PIN, OTP, or unexpected collect approval. Show a prominent warning and High concern for a successful transaction. Independently supported warnings remain visible with a pending transaction. | Rules, API, browser | 03 |
| AT-07 | Unreadable screenshot or OCR failure. Show correction or manual-entry options. Analysis uses the user-confirmed text after review. | OCR adapter, API, browser | 02 |
| AT-08 | The exact identifier has no seeded intel match. Show “No match found in the available demo data.” For a seeded match, show the identifier, source, match type, and limitations. | Rules, API | 03 |
| AT-09 | Evidence includes instructions to ignore rules or reveal secrets. Verify evidence is passed as data and unsupported output or fabricated citations are discarded. Confirm credential values stay out of storage, provider requests, logs, and reports. | Extraction, API, report/browser | 03–04 |
| AT-10 | A second session supplies a foreign transaction, investigation, evidence, incident, or report ID. Expect `404` without object details or side effects. | API with separate cookie jars | 01–04 |
| AT-11 | Missing Gemini key, timeout, or malformed output. Preserve the case, show extraction status, and use supported fallback findings or Unable to assess. Confirm one retry for timeout or invalid output. | Extraction, API | 03 |
| AT-12 | Generate and download a report for the current result. Verify the timestamp, transaction facts, user statements, submitted evidence, extracted findings, category, unknowns, and recommendations. | API, browser | 04 |

## Seeded demo scenarios

| Scenario | Fixture outcome |
| --- | --- |
| A | Different-ID repayment with urgency and no other strong signal or relevant match → Needs verification |
| B | Same-ID repayment with a threat and a request to avoid the bank → High concern |
| C | Same-ID polite repayment request without pressure or a match → Needs verification |
| D | Expected transfer from a known contact with no suspicious evidence → No strong indicators found |
| E | Suspicious collect approval or credential request on a successful credit → High concern |

## Cross-cutting checks

- **Phase 01** Run migrations twice, confirm the second run has no changes, and verify seed idempotency. Reload a transaction, inspect actual status labels, and confirm cross-session ownership.
- **Phase 02** Save and resume intake. Exercise paste, call summary, legible and unreadable screenshots, unsupported files, oversized uploads, OCR correction, evidence removal, and confirmation gating. Verify the server has no durable image copy.
- **Phase 03** Start simultaneous analysis requests and verify one active run ID. Simulate an expired lease and retry. Change evidence while a run is active and verify the old revision cannot publish results. Show progress in the UI and confirm every finding has a source and reference.
- **Phase 04** Update every case status and reopen the case. Verify audit events and post-loss guidance. Edit or delete evidence after exporting and confirm the server can no longer retrieve the stale assessment or report.
- **Phase 05** Confirm reset restores only the current session's seeded state. Run the browser journey at desktop and mobile sizes. Check visible focus, keyboard navigation, status announcements, readable labels, and action reachability. Measure seeded analysis from Analyze to visible result after evidence is submitted, with a target under 20 seconds.
- **Provider verification** Use deterministic fixtures for routine runs. Check EasyOCR against synthetic legible and unreadable images using installed CPU models. Check live Gemini separately with synthetic evidence and record the model, outcome, and timing. Record live Gemini as pending when credentials are absent.

## Evidence of completion

Record the command, cases exercised, result, and any unresolved item in [progress](progress.md). Record measured timings with the test environment and provider mode.

## Phase 05 verification — 2026-11-13

All deterministic checks pass: 94 backend tests, production frontend build, five browser suites, and real CPU OCR. Individual commands and timing are recorded in progress. The optional live Gemini check is separately pending key/model configuration.

| Acceptance cases | Passing coverage |
| --- | --- |
| AT-01, AT-02, AT-03, AT-04, AT-06 | Analysis rule/API tests and Phase 03/05 browser journeys for A–E; same-ID neutrality and independent warnings verified. |
| AT-05 | Analysis/report tests and Phase 03/04 browser checks for pending and failed transactions. |
| AT-07 | Investigation tests, real OCR smoke, Phase 02 browser correction/failure flows, and Phase 05 Scenario B screenshot rehearsal. |
| AT-08 | Analysis tests for exact/no simulated matches; browser findings display no-match limitations. |
| AT-09 | Extraction/report privacy and citation tests; Phase 04 inert malicious-evidence browser flow; Phase 05 rejects edited fixture destinations. |
| AT-10 | Ownership tests across foundation, intake, analysis, reports/incidents, and reset; separate-browser reset isolation and stale URL checks. |
| AT-11 | Analysis tests for missing configuration, timeout, invalid output, retry counts, and safe fallback. Live network verification remains separate. |
| AT-12 | Report tests and Phase 04/05 snapshot review, UTF-8 download, reopen, and invalidation journeys. |

Phase 05 adds reset repeatability, rollback, concurrent creation/loading/reset/status/report checks, every stale worker write, and delayed provider/OCR completion. Desktop 1280×900, mobile 390×844, keyboard focus/navigation, status announcements, API error/retry, and the fresh-reset report/status walkthrough pass.
