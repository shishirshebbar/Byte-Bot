# Phase 03 Analysis and results

## Prerequisites

Phase 02 passes. Read PRD FR-07 through FR-12, [analysis architecture](../architecture.md#analysis-and-reporting), and the [acceptance matrix](../acceptance.md). Use synthetic, deterministic provider fixtures for routine tests. Supply a local key and model only when running the separate live Gemini smoke check.

## Implementation order

1. Persist runs, simulated intel records, extracted signals, and risk assessments. Add an analysis lease and input revision guard. Persist each completed stage and safe errors. Reuse an existing active run for the same revision, and allow interrupted attempts to be reclaimed after lease expiry.
2. Implement one LangGraph workflow using a typed state and the four nodes in the architecture. Use a bounded worker with recovery from the database. Test ownership and idempotency through the analyze and investigation endpoints.
3. Keep Gemini prompts and Pydantic response schemas separate from the routes. Extract request intent, amount, destination identifiers, and social-engineering signals. Match each quoted source to the supplied evidence. Resolve matching locally from redacted placeholders or independently parsed identifiers. Retry once after a timeout or invalid response. Record a clear extraction limitation and use valid structured inputs when available.
4. Normalize relevant identifiers and query exact matches in the seeded intel store. Compute destination match from the original transaction and requested destination. Cite the underlying evidence or rule in each finding. Apply the decision table below.
5. Render stage progress, result category, findings and sources, limitations, and safe guidance. Offer a retry when a run fails. Keep the analysis interface usable when Gemini is unavailable.

## Risk decisions

Apply the rows in order. An independently supported credential or authorization warning remains visible at any category.

| Category | Condition |
| --- | --- |
| Unable to assess | The transaction is pending, failed, or unavailable. Preserve its actual status. |
| High concern | A supported credential or dangerous authorization request, two distinct pressure signals, or a relevant simulated match together with an unexpected credit and a repayment request. |
| Needs verification | An unexpected credit and repayment request with limited evidence, or supported suspicious findings that warrant verification, including a destination mismatch. |
| No strong indicators found | An expected transfer with sufficient context and no suspicious findings. |
| Unable to assess | The available verified facts and user context are insufficient for the preceding categories. |

Count distinct pressure types such as urgency, threats, or isolation once each. A same-UPI-ID match never subtracts concern. A simulated match needs its source, identifier, match type, and limits. A missing match never contributes a positive trust claim. Preserve reported and extracted findings with their respective provenance.

## Expected files and contracts

- Graph, typed state, four specialist nodes, and analysis run service.
- Extraction prompt and adapter, extraction schema, intel lookup, versioned risk rules, and synthetic provider fixtures.
- Analysis API tests, risk and extraction tests, and React progress and results screens.

## Verification and exit checklist

Run `python -m pytest backend/tests` using the project virtual environment and `npm --prefix frontend run build`. Exercise the result page using all five scenario fixtures.

- [x] All categories and scenarios match the [acceptance matrix](../acceptance.md#seeded-demo-scenarios).
- [x] Findings identify their source and reference, with actual payment status and limitations visible.
- [x] Duplicate requests reuse one active run, interrupted work is retryable, and an old input revision cannot publish.
- [x] Missing credentials, timeout, invalid output, and instruction-like evidence preserve the case and return supported fallback results.
- [x] AT-01 through AT-06 and AT-08 through AT-11 are verified at their applicable layers. Record live Gemini verification separately in [progress](../progress.md).

Implemented and verified on 2026-11-13. See [progress](../progress.md#2026-11-13--phase-03-analysis-and-results-complete) for commands, results, synthetic timings, port preservation, and the separately pending optional live Gemini check.
