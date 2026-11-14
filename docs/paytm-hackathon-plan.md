# Byte Bot Paytm-style hackathon demo

At `/`, judges see an interactive iPhone-style Paytm prototype on the left and a live explanation with presenter controls on the right. The existing backend powers the customer journey from a suspicious repayment request through evidence review, a sourced assessment, a downloadable incident report, and user-recorded follow-up.

## Phase 0 — Save the plan and retire the old guides

- Make this the single active phase-wise plan and link it from the README's **Phase guides** section. Retire the five superseded implementation guides.
- Link completed MVP phases to their dated progress entries. Preserve the original PRD, historical checks, and development, demo, setup, and acceptance guides. Check references for broken links.

## Phase 1 — Build the presentation shell

- Make `/` the presentation entry and retain the existing transaction, investigation, results, report, and incidents deep links inside the phone. Mount the standard workspace at `/workspace` with corresponding child routes. Share screen components and API operations across both layouts.
- Use a roughly 390 px phone screen, blue accents, a bright transaction surface, and a navy explanation panel. Keep **Paytm hackathon prototype · Synthetic data** visible and use compact transaction cards, guided chat prompts, and a clear primary action on each screen.
- Below 1024 px, stack the phone above the explanation and provide a jump link to presenter controls. Verify keyboard reachability, visible focus, narrow widths, and reduced motion.

## Phase 2 — Run the real customer journey inside the phone

- Reuse the React and TypeScript API client, same-origin session cookie, FastAPI endpoints, PostgreSQL schema, LangGraph workflow, CPU EasyOCR, optional Gemini extraction, simulated intelligence, and Python risk rules.
- Default to Scenario B with a seeded text message. Load or reopen the ₹5,000 transaction, open **Ask Byte Bot**, review the saved answers and message, and explicitly start analysis. Support pasted messages, typed call summaries, and screenshots that require confirmation before analysis.
- Show **High concern**, the sourced threat and bank-avoidance findings, the matching UPI ID's zero risk reduction, and official-bank verification guidance. Generate and download a UTF-8 report, reopen it through **My Incidents**, and save the user-entered **Bank Contacted** status.
- Keep case actions in the phone and preserve retry, stale-revision recovery, and unsaved-edit protection. The prototype uses synthetic payments and simulated intelligence. Money movement, bank contact, external submissions, call recording, and background message access are outside its scope.

## Phase 3 — Synchronize the explanation and presenter controls

- Provide expandable **Workflow** steps for the four LangGraph stages, **Findings** with source evidence links and limitations, and **Outcome** with confirmed evidence count, report readiness, and saved case status.
- Derive both panes from shared API responses and existing analysis polling. Reflect actual queue, stage, failure, and completion states. Fast runs may finish between polls. Mark report and status updates after successful responses, and clear stale state on input changes, case changes, and reset.
- Put A–E selection, evidence mode, load or reopen, and confirmed reset in the presenter controls. Guard mutations until the session is ready and while edits or writes are in flight. Reset restores history and clears the panel. Failed reset preserves the current view for retry.

## Phase 4 — Verify and rehearse

- Run the frontend build, backend pytest suite, the five standard workspace Playwright scripts, a root presentation regression, and the CPU OCR smoke check. Keep browser API calls at the origin.
- Verify the production preview at 1280×720, 1440×900, 390×844, and 320 px wide. Exercise keyboard operation, reload and back navigation, A–E outcomes, screenshot confirmation, analysis retry, report invalidation, reset recovery, and session ownership.
- Rehearse a four-minute Scenario B walkthrough from a fresh reset. Target under 20 seconds from Analyze to the visible fixture result and record timing and completed actions in [progress](progress.md). Fraud prevention, support time saved, and detection precision are proposed pilot measures.
- Keep Byte Bot on loopback API 8000, frontend 5174, preview 4174, and PostgreSQL 55433. Use explicit fixture mode for the presentation. Verify live Gemini separately when a local key and model are configured, using synthetic evidence.

## Upgrade Phase 1 — Measure the baseline and prepare a private report

- Measure three fresh Scenario B runs from the saved case review through download and a saved **Bank Contacted** status. Count customer actions from analysis approval, including status selection and save.
- In the phone, **Analyze & prepare report** approves both actions for the reviewed revision. The existing worker prepares a private report from the completed assessment. Reuse a completed assessment when approval arrives later. Keep screenshot confirmation, ownership, revision checks, retry, and idempotency. The workspace retains separate analysis and report actions.

## Upgrade Phase 2 — Put the next action beside the assessment

- Show priority guidance, a direct UTF-8 download, and report review on the result. Let the customer record their own follow-up there and reopen it through **My Incidents**.
- Show the sourced same-UPI-ID comparison, threat, and bank avoidance when returned. Use the saved assessment, report ID, and follow-up status in the phone and the presenter panel. Preserve urgent warnings and limitations.

## Upgrade Phase 3 — Verify and rehearse for judging

- Run the build, backend suite, six browser suites, and CPU OCR. Verify report approval, retry, concurrency, stale inputs, ownership, reset, narrow layouts, and a keyboard walkthrough.
- Log three matched fixture runs with at least two fewer customer actions and a visible assessment and ready report within 20 seconds each. Verify download, status save, and reopen.
- Rehearse Scenario B with a four-minute script, a local fallback recording, and a judge Q&A. Use Scenario C only as a comparison if time permits. Treat fraud prevented, detection precision, and support effort as pilot metrics.
