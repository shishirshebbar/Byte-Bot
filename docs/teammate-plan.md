# Byte Bot → hackathon-winning "AI teammate": adapted phase plan

## Context

**Inputs that shape this plan:**
1. **Problem statement** (Paytm × Sarvam AI × Devsemble). The AI teammate must:
   - understand context and make decisions
   - **take actions across systems**
   - **escalate to humans only when needed**
   - show **measurable outcomes**
2. **Declared tech stack and agent architecture.** React, FastAPI, LangGraph, a GPT/Gemini LLM, LLM-based extraction, Tesseract/EasyOCR, a rule-based scoring risk engine, PostgreSQL, and a Neo4j or simulated fraud graph. Four specialist agents (**Transaction Context, Message Analysis, Risk Investigation, Incident Resolution**) are coordinated by **one main agent**.
3. **UI references** (`C:\Users\chait\Downloads\Newfolderdfd`):
   - (a) a clean banking transaction history with date groups, status-badged icons, filter chips, search and period sheets, and a bottom tab bar
   - (b) a chatbot with quick-reply chips, a privacy notice, navy user bubbles, and a "Was this chat helpful?" prompt
   - (c) a "Risk & Fraud Analysis" panel with a score gauge, a HIGH RISK banner, and a risk-factor list using ✕/⚠/✓ icons
   - (d) a SOC-style case management console with action buttons, status, analyst, Yes/No insight pills, activity and notes tabs, a notifications feed, an integrations grid, and an agent timeline ("Composing next steps…")

**What already exists:**
- The four specialists as a **linear** LangGraph (`backend/bytebot/analysis_graph.py`), with durable checkpoints and a leased worker.
- Gemini extraction plus a fixture mode (`extraction.py`), EasyOCR (`ocr.py`), and PostgreSQL with revisioned and ownership-checked cases.
- A categorical Python decision table (`risk_rules.py`) and exact-match simulated intel in two flat tables (`intelligence.py`).
- Static guidance (`guidance.py`), immutable reports, and the phone plus presenter-panel view (`presentation.tsx`).

**What's missing:** the main agent, real decisions, actions, a human teammate, a numeric explainable score, a graph-shaped intel model, Sarvam, metrics, and the reference-quality UI.

**Outcome:** "Byte Bot: Paytm's AI fraud-resolution teammate." A supervisor agent runs the four specialists. It asks only the follow-ups it needs, scores and explains risk, takes consented, policy-gated actions on **clearly labeled simulated systems**, and hands off to a human console with a full brief when needed. A metrics dashboard proves the outcome.

## Stack decisions (mapping the declared stack to the repo)

| Layer | Decision |
| --- | --- |
| Frontend | Keep React 19, Vite, TypeScript. Restyle to the references; no new UI framework, plain CSS tokens. |
| Backend | Keep FastAPI and the leased in-process worker. |
| Agent | LangGraph **supervisor** node plus four specialist subgraphs, with conditional edges and the existing durable checkpoints. |
| LLM | Gemini stays primary. GPT and **Sarvam** are optional providers behind the same interface as `extraction.py`. Fixture mode keeps the demo deterministic. |
| NLP | Schema-validated LLM extraction (existing), plus local regex markers in `safety.py`, extended to Hindi/Hinglish. |
| OCR | EasyOCR (existing). Tesseract isn't needed. |
| Risk engine | Keep the categorical Python decision table as the authority. **Add** an explainable 0–100 score made of weighted factors; the score never overrides the category. |
| Database | PostgreSQL only; SQLite is dropped. |
| Fraud intel | A **simulated graph in PostgreSQL** (node and edge tables with a recursive CTE for two-hop links). It's a drop-in for Neo4j later, and avoids Docker and Neo4j setup risk, since the Docker engine was unavailable on this machine in earlier runs. |

**Boundary update:** this was approved with the previous plan and is applied in Phase 0. Actions run only against local mock systems labeled "Simulated system." There are still no real payments, external submissions, call recording, or background message access.

---

## Phase 0: Reframe, guardrails, design tokens

- **Plan doc:** Write `docs/teammate-plan.md` and link it from the README phase guides. Update the boundaries in `AGENTS.md`, `README.md`, and `docs/architecture.md`.
- **Design tokens** in `frontend/src/styles.css` and `presentation.css`:
  - Colors: Paytm blue `#0A5CFF`-ish primary, navy, success green, warning amber, danger red, light grey surfaces.
  - 12–16 px radii, Manrope (already installed), and an icon set from `lucide-react` (already installed).
- **Scenario catalog:** grow A–E to about 15–20 scenarios in `demo.py` and `fixtures.py`. Include Hindi/Hinglish, already-sent-money (escalates), conflicting evidence (escalates), a prompt-injection message, a legitimate refund (no action), a mule-ring graph hit, and a pending or failed credit.
- **North-star metrics:** autonomous resolution rate, escalation precision and recall, time to resolution, customer actions saved, simulated amount protected, and **0 policy violations**.

## Phase 1: Main agent and specialists (backend core, the biggest judging lever)

- **Supervisor in `analysis_graph.py`:** the single main agent. It holds the case state and routes with deterministic conditional edges:
  - `supervisor → transaction_context → supervisor → message_analysis → supervisor → risk_investigation → supervisor → (gather_context | plan_actions) → policy_gate → (execute | await_consent | escalate) → incident_resolution → END`
  - Each specialist stays a focused function (existing code is reused) and writes a typed output.
  - The supervisor records a **decision trace entry** (`why`, `next`) per hop, stored with `save_stage`. The trace feeds the "Composing next steps…" timeline.
- **gather_context:** when key `Context` fields are `unknown` or unanswered, the supervisor emits typed follow-up questions (new table `follow_up_questions`). The run pauses in `awaiting_customer`, and answering creates a new revision and resumes.
- **Planner (`planner.py`):** a deterministic playbook keyed by category and decision. An LLM may phrase or explain steps but can never add tools.
- **Policy and escalation (`policy.py`):** gives each action a verdict of `auto`, `needs_customer_consent`, `needs_human_approval`, or `deny`.
  - It escalates on: already sent money, evidence that conflicts with answers, failed or low-confidence extraction, suspected injection, an amount above the threshold, a customer request for a human, and repeated "Unable to assess."
  - Policies are versioned like `RULE_VERSION`.
- **Migration `006_agent_core.sql`:**
  - `agent_trace`
  - `follow_up_questions`
  - `agent_actions` (idempotency key, state, actor, and system reference)
  - `escalations` (priority, SLA, assignee, and status)
- **Invalidation:** revision invalidation, already in the investigation store, also revokes pending actions and questions. Executed simulated actions remain in the ledger.
- **Reuse:** `fenced`, `save_stage`, `publish` (`analysis_store.py`), the worker leases (`analysis_worker.py`), and `risk_rules.assess` unchanged as the category authority.

## Phase 2: Risk engine score and fraud-intelligence graph

- **Score (`risk_rules.py` and `analysis_schemas.py`):**
  - Add `risk_score` (0–100) and `risk_factors`. Each factor has an id, label, weight, status (`fail`/`warn`/`pass`), source, and evidence reference. These drive the ✕/⚠/✓ list in reference (c).
  - Weights live in one versioned table.
  - A same-UPI-ID match is an explicit **0-weight** "does not reduce concern" factor.
  - The category still comes from the decision table. Add a test asserting the score can't move the category.
- **Graph intel (`intelligence.py` plus migration `007_intel_graph.sql`):**
  - Tables: `intel_nodes` (vpa, phone, device, incident, account) and `intel_edges` (typed, sourced, timestamped).
  - A recursive CTE finds two-hop links ("this VPA shares a phone with 3 reported incidents").
  - Seed a small synthetic mule ring. Matches keep the "not proof of guilt" limitation.
- **Endpoint:** `GET /investigations/{id}/intel-graph` returns an owner-scoped, masked subgraph for the UI.

## Phase 3: Actions across simulated systems

- **`backend/bytebot/systems/`:** one mock per system. Each is injectable through `create_app(...)`, like `ocr_adapter` and `extraction_provider`.
  - **Paytm UPI sandbox:** dispute hold on the credit, block VPA, decline collect request.
  - **Bank dispute desk:** ticket reference and SLA.
  - **Cybercrime 1930:** a pre-filled draft for the customer; never sent.
  - **Notifications:** simulated SMS/WhatsApp/in-app messages.
- **Executor (`actions.py`):** idempotent, retries with backoff, verifies by reading back, and supports compensation (undo) from the console.
- **Incident Resolution Agent:** `guidance.py` and `reports.py` gain an "Actions taken / pending / owner" section with system references. Audit events stay allowlisted (`audit.py`).
- **Endpoints:**
  - `POST /investigations/{id}/actions/{action_id}/consent` (customer)
  - `POST /investigations/{id}/escalate` (talk to a human)

## Phase 4: Phone UI redesign (references a, b, c)

- **History (reference a)** in `main.tsx` and `transaction-ui.tsx`:
  - Date-grouped list (Today, Yesterday, dates) with round direction icons and **status badges** (✓ successful, clock pending, ✕ failed).
  - An **"Unexpected credit"** chip on the flagged item.
  - Filter chips (balance, All, All time) and **search and period bottom sheets**.
  - A bottom tab bar (Home, History, Pay, **Byte Bot** chat with a badge, More).
- **Proactive entry:** a simulated push card: "Unexpected ₹5,000 received. Did someone ask you to return it?" Tapping it opens the chat.
- **Chat (reference b)**, chat-first intake in `investigation.tsx`, shared with the presentation:
  - A header with close and the privacy notice ("This conversation is saved to your private case…").
  - Bot bubbles, navy user bubbles, timestamps, and **quick-reply chips** for each `Context` question.
  - Paste-message, screenshot, and **mic** buttons in the input bar.
  - Inline **consent cards** and **action receipts** with simulated-system references, an always-visible "Talk to a human," and "Was this helpful? 🙂 / 🙁" at the end. That feedback is stored as a metric.
- **Result (reference c)** in `results.tsx`:
  - A **risk score gauge**, a category banner, and transaction summary rows (amount, sender, **actual analysis time** from run timestamps).
  - A **risk factors** list with ✕/⚠/✓ icons and source links, plus a "Checks" grid (Transaction status, Destination check, Intel graph, Pressure tactics, Credential request).
  - Banner wording follows actual actions: "Dispute hold placed (simulated)" only if executed. Otherwise "High concern — act now."
- **Workspace:** `/workspace` keeps the form-based flow so the existing browser suites remain valid.

## Phase 5: Human teammate console (reference d)

- **`/console` route** (`frontend/src/console.tsx`) with a left icon rail:
  - **Queue:** escalated cases with priority, SLA timer, and reason chips.
  - **Case header chips:** severity, scammer identifier → customer (masked), channel, and amount.
  - **Actions row:** approve, reject, send note, and more. **Status** dropdown and **Analyst** assignment.
  - **Insights** Yes/No pills (Threat, Bank avoidance, Credential request, Destination mismatch, Intel graph hit) with "click to see details" linking to the sourced finding.
  - **Activity / Notes** tabs: the agent trace timeline, including "Composing next steps…", plus human notes.
  - A **notifications** feed ("Case #… escalated · 3 actions executed · triggered by Byte Bot").
  - An **Integrations** page: a card grid of the simulated systems plus Gemini, Sarvam, EasyOCR, and the Intel graph, each with mode, health check, and Details.
- **Demo agent role:** a separate demo agent cookie that reads only escalated cases through allowlisted fields. Customer ownership checks are unchanged. Human approvals and overrides are written to `agent_actions` with `actor=human` and counted in metrics.

## Phase 6: Sarvam AI multilingual voice (sponsor fit)

- **`sarvam.py` adapter:** speech-to-text for Hindi, Hinglish, Tamil, etc., translation to English for rules (keeping the **original-language quote** as provenance), text-to-speech for replies, and optionally Sarvam's LLM as an extraction provider. Verify endpoints and models against current Sarvam docs at implementation time.
- **Safety:** audio stays in memory only (`uploads.py` pattern). The transcript is redacted (`redaction.py`) and masked before provider calls. The customer reviews the transcript, like OCR review.
- **Localization:** add Hindi/Hinglish markers to `safety.py` ("OTP batao," "bank ko mat batana," AnyDesk). Localize guidance in code, with Sarvam translation as a fallback only.
- **Configuration:** `SARVAM_API_KEY` is optional, and fixture mode works offline.

## Phase 7: Presenter panel, evaluation, metrics

- **Presenter panel** (`presentation.tsx` and `presentation-state.ts`): a live supervisor trace (hop → specialist → decision → policy verdict → action result), color-coded by agent, customer, and human, plus a mini intel-graph view.
- **`backend/tests/eval_teammate.py`:** runs every scenario through the API in fixture mode and writes `.cache/eval/results.json`. It measures:
  - category accuracy
  - escalation precision and recall
  - autonomous resolution rate
  - median time to resolution
  - injection attempts blocked
  - policy violations, which must be 0
- **`/metrics` page:** KPI tiles plus a before/after comparison of customer actions and time. Pilot projections are labeled as estimates.

## Phase 8: Security hardening

- **Threat model:** `docs/threat-model.md`, covering STRIDE and the OWASP Top 10 for LLM applications, mapped to the controls.
- **Agent controls:**
  - The LLM never selects tools.
  - Tools have an allowlist with typed arguments.
  - Consent tokens are bound to the session, case, revision, and action.
  - Amounts and VPAs are re-derived from the database.
- **Tests:** an English and Indic prompt-injection corpus asserting no action, no policy bypass, and no leakage.
- **Ledger and app hardening:** hash-chained `agent_actions` and audit rows (a "Ledger verified ✓" badge in the console), rate limits on mutations, CSP and security headers, and a test that the console role can't read non-escalated cases.

## Phase 9: Pitch, rehearsal, verification

- **Four-minute story:**
  1. Push alert.
  2. A Hindi voice note: "galti se ₹5,000 bheje, wapas karo, bank ko mat batana."
  3. One follow-up chip.
  4. Score gauge at High.
  5. Consent leads to hold, VPA block, and bank ticket (receipts).
  6. A second case (already sent money) escalates to the console, where a human approves the 1930 draft.
  7. Close on the metrics page.
- **Assets:** an architecture slide (supervisor plus four specialists, policy gate, simulated systems, graph, Sarvam), a fallback recording, and judge Q&A.

---

## Priority if time is short

1. **Phase 1:** supervisor, policy, and escalation.
2. **Phase 3:** at least three actions.
3. **Phase 4:** chat and result screens.
4. **Phase 5:** the console's queue, case, and approve.
5. **Phase 2:** score and graph.
6. **Phase 6:** Sarvam speech-to-text for Hindi.
7. **Phase 7:** metrics.

The threat-model doc and injection tests are cheap wins.

## Critical files

- **Change:** `backend/bytebot/analysis_graph.py`, `risk_rules.py`, `analysis_schemas.py`, `intelligence.py`, `guidance.py`, `safety.py`, `extraction.py`, `reports.py`, `report_schemas.py`, `audit.py`, `demo.py`, `fixtures.py`, `main.py`, and `investigation_store.py` (invalidation). Frontend: `frontend/src/main.tsx`, `transaction-ui.tsx`, `investigation.tsx`, `results.tsx`, `presentation.tsx`, `presentation-state.ts`, `styles.css`, `presentation.css`, `api.ts`. Also `AGENTS.md`.
- **New:** `planner.py`, `policy.py`, `actions.py`, `systems/*`, `sarvam.py`, `migrations/006_agent_core.sql`, `migrations/007_intel_graph.sql`, `frontend/src/console.tsx`, `metrics.tsx`, `chat.tsx`, `backend/tests/test_agent.py`, `eval_teammate.py`, `browser_teammate.py`, `docs/teammate-plan.md`, `docs/threat-model.md`.

## Verification (each phase)

- `.\.venv\Scripts\python.exe -m pytest backend/tests -q`. New tests cover supervisor routing, follow-ups, policy verdicts, escalation triggers, the score-vs-category invariant, the graph two-hop query, action idempotency and compensation, consent binding, console ownership, injection, and Sarvam with fakes.
- `npm --prefix frontend run build`.
- The six existing browser suites (the `/workspace` flow is preserved) plus a new `browser_teammate.py` covering push → chat → consent → receipts, escalation → console approve, and the metrics page at 1280×720 and 390×844.
- `eval_teammate.py` reports 0 policy violations and meets the escalation precision target.
- Optional live Gemini and Sarvam smoke tests with synthetic input only.
- Record results in `docs/progress.md`. Ports stay at 8000, 5174, 4174, and 55433.
