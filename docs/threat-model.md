# Byte Bot threat model

Scope: the local hackathon demo. FastAPI on loopback, PostgreSQL, the React phone, the human console, simulated systems, and Sarvam AI as the live provider. All data is synthetic. This document maps threats to the controls that exist in code and the tests that check them. It also lists what a production deployment would still need.

## Assets and trust boundaries

| Asset | Why it matters |
| --- | --- |
| Customer evidence (messages, voice transcripts, screenshot text) | It may contain credentials, personal data, or attacker-written instructions. |
| Case decisions (category, actions, escalations) | Wrong decisions harm customers: a missed scam, or an unwanted hold. |
| Account actions on simulated systems | In production these would move or freeze money. |
| Audit ledger | It is the evidence of who did what. |
| Provider key (Sarvam) | It costs money and could leak data if misused. |

The boundaries are: browser to API (customer cookie), browser to console API (separate console cookie), API to Sarvam (masked text, in-memory audio), API to PostgreSQL, and evidence to the model (untrusted data).

## STRIDE

| Threat | Example | Control | Verified by |
| --- | --- | --- | --- |
| **Spoofing** | Reading another customer's case | An opaque HttpOnly SameSite cookie. Ownership is derived on every query, and foreign and missing IDs return the same 404. | `test_foundation`, `test_agent::test_customer_can_ask_for_a_person`, `test_actions::…ownership…` |
| Spoofing | A customer acting as a support agent | A separate `bytebot_console` cookie scoped to `/api/v1/console`. The customer cookie never opens the console, and the console cookie never opens customer data. | `test_console::test_console_requires_its_own_session` |
| **Tampering** | Editing audit history to hide who approved a hold | A per-case SHA-256 hash chain on `audit_events` (content, timestamp, previous hash). Edits and deletions break verification, and the console shows "Ledger verified". | `test_security::test_ledger_is_tamper_evident` |
| Tampering | Replaying a stale consent after the case changed | Consent and human decisions require the current input revision and the exact waiting state. Input changes revoke pending steps. | `test_actions::test_consent_requires_revision_ownership_and_waiting_state`, `test_agent::test_input_change_revokes_pending_decisions` |
| **Repudiation** | "Byte Bot did it, not me" | Every executed, declined, failed, or undone step records an actor (`agent`, `customer`, `human`) in `agent_actions` and in the chained audit. | `test_console::test_human_approval_executes_and_customer_sees_receipt` |
| **Information disclosure** | Credentials reaching storage or the provider | Credential-label redaction before storage, translation, and extraction. Identifiers are masked as `[VPA_n]` before the model sees text. Audio and images stay in memory. Text-to-speech receives only Byte Bot's guidance. | `test_voice`, `test_analysis::test_redacted_credentials_and_provider_privacy` |
| Information disclosure | The console revealing the customer | The console reads only escalated cases, through allowlisted fields, with the customer UPI ID masked. Metrics are counts only. | `test_console::test_queue_shows_only_escalated_cases…`, `test_metrics` |
| **Denial of service** | Flooding analysis or burning provider credit | Per-session rate limits: 120 mutations a minute, and 12 speech calls a minute. Bounded uploads (images 5 MiB, audio 2 MiB, body 6 MiB). Two worker slots with leases. An 8-second extraction deadline. | `test_security::test_rate_limits…`, upload-limit tests |
| **Elevation of privilege** | A model or message triggering account actions | The model never selects tools. Steps come only from the fixed playbook (`planner.ACTIONS`). Each step passes the Python policy, which requires customer consent or human approval for account actions. Systems re-derive targets from the database, never from model output. | `test_agent::test_policy_and_planner_units`, `eval_teammate.py` (policy violations = 0) |

## OWASP Top 10 for LLM applications (2025)

| Risk | How Byte Bot handles it |
| --- | --- |
| **LLM01 Prompt injection** | Evidence is labelled as data in the system prompt. Instruction-like text (English and Hinglish) is detected by `policy.INJECTION` and escalates to a person. The category comes from Python rules, and a dangerous request inside an injection can only raise risk. The model cannot cause actions. Verified by the 8-string corpus in `test_security`, Scenario H, and the evaluation ("injection contained"). |
| **LLM02 Sensitive information disclosure** | Redaction and identifier masking happen before every provider call. No raw images, audio, filenames, or provider responses are stored. Provider error bodies are never logged or returned. |
| **LLM03 Supply chain** | Pinned Python requirements, the npm lockfile, and a single first-party provider SDK path (`httpx` for Sarvam). No model weights are downloaded except EasyOCR's documented models. |
| **LLM04 Data and model poisoning** | No training or fine-tuning on user data. Human overrides are recorded but never auto-applied. Simulated intelligence is seeded, not learned. |
| **LLM05 Improper output handling** | Model output must match a strict Pydantic schema (extra fields forbidden). Each claim's quote must be an exact substring of the evidence it cites. Kinds are revalidated with local patterns and negation checks. Identifiers must map back to masked placeholders. Hostile outputs are discarded (`test_security::test_hostile_provider_output_is_contained`). React escapes all rendered text. |
| **LLM06 Excessive agency** | The playbook allowlist, the policy verdicts (`auto` only for a customer-only notification), consent and human approval gates, revision fencing, idempotent execution, read-back verification, and undo. Simulated systems only. |
| **LLM07 System prompt leakage** | The prompt contains no secrets. The key is server-side in `.env`, which is gitignored, and is never sent to the browser. |
| **LLM08 Vector and embedding weaknesses** | Not applicable: no retrieval store. |
| **LLM09 Misinformation** | Every finding carries provenance and limitations. "Not proof of guilt" and "not a safety guarantee" are stated on matches, links, and calm results. Scores are labelled as summaries that never change the category. |
| **LLM10 Unbounded consumption** | Rate limits, an 8-second deadline with one retry, `max_tokens` 1500, a 25-second voice cap, a 1,000-character translation input, and a 1,500-character speech input. |

## Web hardening

- **API responses:** `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, and `Cross-Origin-Resource-Policy: same-origin`.
- **Production preview (4174):** a strict CSP (`script-src 'self'`, no inline scripts, `connect-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`) and `Permissions-Policy` allowing only the microphone, for voice notes. The dev server omits CSP because Vite's hot reload injects inline scripts. A browser check of the presentation, console, and metrics under the preview CSP showed no violations.
- **Cookies:** HttpOnly and SameSite=Lax. `Secure` is enabled when `COOKIE_SECURE=true` behind HTTPS.

## Residual risks and production gaps

- **Console authentication:** the console role is a demo session with no real authentication. Production needs SSO, role-based access, and a per-agent audit identity.
- **Ledger anchoring:** the chain detects edits and deletions inside the history, but not truncation of the newest entries. Production should anchor the chain head externally, for example in a write-once store.
- **Rate limits:** limits live in process memory and reset on restart. Production needs a shared store and per-IP limits for anonymous traffic.
- **Detection coverage:** injection and scam patterns are conservative English and Hinglish prototypes, not complete detection. Sarvam translation can paraphrase; the original-language text is kept for review.
- **Simulated systems:** these stand in for real Paytm, bank, and 1930 integrations, which would each need their own authorisation, idempotency keys, and reconciliation.
