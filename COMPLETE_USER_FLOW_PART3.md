# Byte Bot Complete User Flow - Part 3: Analysis & Decision

## 6️⃣ BACKEND PROCESS: Supervisor Analysis (Automatic)
**File**: `backend/bytebot/analysis_worker.py`, `analysis_graph.py`

### What Happens Behind the Scenes:
```
Timeline:
  T+0s   User confirms evidence (input_revision incremented)
  T+0.5s AnalysisWorker polls database (2 concurrent slots)
  T+0.6s Worker claims the analysis run with lease (60 sec timeout)
  T+1s   Supervisor graph starts executing nodes sequentially
  T+2s   Results stored in database
  T+2.5s Frontend polls and detects new results
  T+2.6s UI updates automatically
```

### Worker Loop (analysis_worker.py:loop)
```
while True:
  ├─ Sleep 2 seconds
  ├─ Poll analysis_runs table:
  │   └─ SELECT * FROM analysis_runs 
  │       WHERE state = 'pending' 
  │       AND (lease_expires IS NULL OR lease_expires < now())
  │       LIMIT 2  [max 2 concurrent]
  │
  ├─ For each pending run:
  │   ├─ Acquire lease (60 second heartbeat):
  │   │   ├─ UPDATE analysis_runs SET
  │   │   │   ├─ state = 'claimed',
  │   │   │   ├─ lease_expires = now() + 60 seconds,
  │   │   │   ├─ attempt_number = attempt_number + 1
  │   │   │   └─ WHERE id = ? AND state = 'pending'
  │   │   │
  │   │   └─ If UPDATE returns 0 rows:
  │   │       └─ Skip (another worker claimed it)
  │   │
  │   ├─ Execute analysis (with heartbeat pulses every 10 sec):
  │   │   ├─ Start background thread for heartbeat
  │   │   │   ├─ Every 10 seconds:
  │   │   │   └─ UPDATE analysis_runs SET lease_expires = now() + 60s
  │   │   │
  │   │   ├─ Check ownership/revision/lease (triple-check):
  │   │   │   ├─ SELECT FROM investigations WHERE id = ? AND owner_id = ?
  │   │   │   ├─ SELECT FROM analysis_runs WHERE id = ?
  │   │   │   ├─ Verify run.input_revision == case.input_revision
  │   │   │   ├─ Verify lease not expired
  │   │   │   └─ If any check fails: abandon run, mark state = 'failed'
  │   │   │
  │   │   ├─ Execute LangGraph Supervisor:
  │   │   │   (See supervisor graph below)
  │   │   │
  │   │   └─ Persist results:
  │   │       ├─ UPDATE analysis_runs SET
  │   │       │   ├─ state = 'complete'
  │   │       │   ├─ completed_at = now()
  │   │       │   └─ output_data = {...}
  │   │       │
  │   │       └─ Also store:
  │   │           ├─ risk_assessments table (category, score, factors)
  │   │           ├─ agent_traces table (supervisor decisions)
  │   │           └─ reports table (if prepare_report=true)
  │   │
  │   └─ Stop heartbeat thread
  │
  └─ Repeat
```

---

### Supervisor Graph (analysis_graph.py)

The supervisor routes deterministically through 4 nodes based on Python logic (not LLM decisions).

#### **Node 1: TRANSACTION CONTEXT**
```
Input:
  ├─ Investigation ID
  ├─ Transaction details (sender, amount, date)
  └─ User context (expected payment?, knows sender?)

Processing (transaction_context_node):
  ├─ Fetch transaction from database
  ├─ Fetch investigation context
  ├─ Build initial state for supervisor:
  │   {
  │     transaction: {...},
  │     context: {
  │       expected_payment: 'no',
  │       knows_sender: 'yes',
  │       contact_channels: ['call', 'whatsapp'],
  │       ...
  │     },
  │     evidence: [...],
  │     messages: []
  │   }
  │
  └─ Pass to router

Output:
  └─ Complete case context ready for analysis
```

#### **Node 2: MESSAGE ANALYSIS**
```
Input:
  └─ Case context + confirmed evidence text

Processing (message_analysis_node):
  ├─ Extract signals from evidence via Gemini/Sarvam:
  │   ├─ If BYTEBOT_EXTRACTION_MODE = 'gemini':
  │   │   ├─ Call Gemini API with evidence text
  │   │   ├─ Request schema:
  │   │   │   {
  │   │   │     "is_likely_fraud": boolean,
  │   │   │     "fraud_patterns": ["urgency_tactics", "credential_request", ...],
  │   │   │     "confidence": 0.0-1.0,
  │   │   │     "reasoning": "..."
  │   │   │   }
  │   │   │
  │   │   └─ Gemini returns validated response
  │   │
  │   ├─ If BYTEBOT_EXTRACTION_MODE = 'sarvam':
  │   │   ├─ Call Sarvam API (voice-to-text conversion)
  │   │   ├─ Then extract signals same way
  │   │   │
  │   │   └─ Return same schema
  │   │
  │   └─ If BYTEBOT_EXTRACTION_MODE = 'fixture':
  │       ├─ Use deterministic test fixtures (no API call)
  │       └─ Return exact same schema (for testing)
  │
  ├─ Redact credentials from extraction results
  │   └─ Keep labels, remove values
  │
  ├─ Build messages for supervisor:
  │   └─ {
  │       "role": "extraction_result",
  │       "content": "Detected fraud patterns: urgency, credential request"
  │     }
  │
  └─ Pass to router

Output:
  └─ Extracted signals (fraud patterns, confidence)
```

#### **Node 3: RISK INVESTIGATION**
```
Input:
  ├─ Case context
  ├─ Extracted signals
  └─ Evidence (messages, transactions)

Processing (risk_investigation_node):
  ├─ Apply Python decision table (risk_rules.py:assess):
  │   ├─ Check transaction status first (highest priority):
  │   │   ├─ If status = 'FAILED' → category = 'low_risk'
  │   │   ├─ If status = 'PENDING' → category = 'medium_risk'
  │   │   └─ Continue to next check if 'COMPLETED'
  │   │
  │   ├─ Check dangerous mechanisms (medium priority):
  │   │   ├─ IF "credential_request" in signals:
  │   │   │   └─ category = 'high_risk'
  │   │   ├─ IF "qr_code_payment" in signals:
  │   │   │   └─ category = 'high_risk'
  │   │   ├─ IF "pin_request" in signals:
  │   │   │   └─ category = 'high_risk'
  │   │   └─ Continue if none found
  │   │
  │   ├─ Apply rules table (low priority):
  │   │   ├─ known_sender = true → reduce risk
  │   │   ├─ expected_payment = yes → reduce risk
  │   │   ├─ already_sent_money = yes → increase risk
  │   │   ├─ pressure_tactics found → increase risk
  │   │   ├─ contact via WhatsApp/SMS → increase risk
  │   │   └─ Calculate weighted score (0-100)
  │   │
  │   └─ Category precedence:
  │       ├─ Category NEVER changes once set (high > medium > low)
  │       ├─ Score (0-100) is for display only
  │       └─ Score cannot override category
  │
  ├─ Walk fraud graph (optional, for related cases):
  │   ├─ Query similar transactions (sender VPA, amount range)
  │   ├─ Build fraud graph showing connections
  │   └─ Add to display_data
  │
  ├─ Build assessment:
  │   {
  │     "category": "high_risk",
  │     "risk_score": 87,
  │     "risk_factors": ["credential_request", "urgency", "unknown_sender"],
  │     "decision_basis": "credential_request detected + urgency language"
  │   }
  │
  └─ Pass to router

Output:
  └─ Risk category + score + factors
```

#### **Node 4: INCIDENT RESOLUTION**
```
Input:
  ├─ Case context
  ├─ Risk category
  ├─ Signals
  └─ Evidence

Processing (incident_resolution_node):
  ├─ Determine next steps based on category:
  │   ├─ IF category = 'high_risk':
  │   │   ├─ Generate follow-up questions:
  │   │   │   ├─ "Have you already shared your credentials?"
  │   │   │   ├─ "Has money left your account?"
  │   │   │   └─ "Can you contact your bank immediately?"
  │   │   │
  │   │   ├─ Generate action plan:
  │   │   │   ├─ action_1: "Contact your bank (priority: immediate)"
  │   │   │   ├─ action_2: "Monitor account for fraudulent transfers"
  │   │   │   └─ action_3: "Report to Paytm support"
  │   │   │
  │   │   └─ Determine escalation:
  │   │       ├─ policy_gate assigns:
  │   │       │   ├─ "needs_human_approval" (for high risk)
  │   │       │   ├─ reason: "potential credential theft"
  │   │       │   └─ escalate_to: "fraud_team"
  │   │       │
  │   │       └─ User cannot take actions alone
  │   │           (requires human agent approval)
  │   │
  │   └─ IF category = 'medium_risk' or 'low_risk':
  │       ├─ Generate follow-up questions
  │       ├─ Determine policy gate outcome
  │       │   ├─ If needs_customer_consent:
  │       │   │   └─ User can approve actions
  │       │   ├─ If auto:
  │       │   │   └─ Actions execute immediately
  │       │   └─ If deny:
  │       │       └─ No actions allowed
  │       │
  │       └─ Continue
  │
  └─ Pass to router

Output:
  └─ Follow-up questions + action plan + policy decision
```

#### **Supervisor Routing (analysis_graph.py:route)**
```
Current state → route() → Next node

route() logic:
  ├─ IF current_node = 'transaction_context':
  │   └─ next = 'message_analysis'
  │
  ├─ IF current_node = 'message_analysis':
  │   └─ next = 'risk_investigation'
  │
  ├─ IF current_node = 'risk_investigation':
  │   └─ next = 'incident_resolution'
  │
  ├─ IF current_node = 'incident_resolution':
  │   └─ next = END
  │
  └─ All routing decisions are deterministic (no LLM randomness)
```

---

### Store Analysis Results (investigation_store.py)

After supervisor completes:
```
INSERT INTO analysis_runs:
  ├─ id: run_id
  ├─ investigation_id: case_id
  ├─ input_revision: 2 (from case.input_revision)
  ├─ state: 'complete'
  ├─ output_data: {...full supervisor output...}
  └─ completed_at: now()

INSERT INTO risk_assessments:
  ├─ id: assessment_id
  ├─ run_id: run_id
  ├─ data: {
  │   "category": "high_risk",
  │   "risk_score": 87,
  │   "risk_factors": ["credential_request", "urgency"],
  │   "decision_basis": "..."
  │ }
  └─ created_at: now()

INSERT INTO agent_traces (for debugging):
  ├─ investigation_id: case_id
  ├─ node_name: 'risk_investigation'
  ├─ input: {...}
  ├─ output: {...}
  └─ timestamp: now()

IF prepare_report = true:
  └─ INSERT INTO reports:
      ├─ id: report_id
      ├─ investigation_id: case_id
      ├─ data: {
      │   "case_id": "...",
      │   "transaction": {...},
      │   "category": "high_risk",
      │   "risk_factors": [...],
      │   "actions": [...],
      │   "created_at": now()
      │ }
      └─ created_at: now()
```

---

## 7️⃣ SCREEN: Investigation Workspace - Analysis Results
**File**: `frontend/src/results.tsx`, `agent-ui.tsx`

### What User Sees (Frontend Auto-Refreshes):
```
┌──────────────────────────────────────────────────────────────────┐
│  📱 Byte Bot Investigation Workspace                             │
│  ════════════════════════════════════════════════════════════    │
│                                                                  │
│  [Context] [Evidence] [Analysis] [Results] ← AUTO-REFRESHES     │
│                                                                  │
│  ──────────────────────────────────────────────────────────     │
│  RISK ASSESSMENT                                                 │
│  ──────────────────────────────────────────────────────────     │
│                                                                  │
│  🔴 HIGH RISK                                                    │
│                                                                  │
│  Risk Score: 87/100                                              │
│  ┌────────────────────────────────────────┐ [87% filled]        │
│  │████████████████████████░░░░░░░░░░░░░│  │                    │
│  └────────────────────────────────────────┘                     │
│                                                                  │
│  Risk Factors:                                                   │
│  ✓ Credential request detected                                  │
│  ✓ Urgent language detected                                     │
│  ✓ Unknown sender                                               │
│  ✓ Requested money transfer (not same VPA)                      │
│                                                                  │
│  ──────────────────────────────────────────────────────────     │
│  FRAUD GRAPH (Related Transactions)                              │
│  ──────────────────────────────────────────────────────────     │
│                                                                  │
│  This transaction is part of a fraud pattern:                   │
│                                                                  │
│     [Rajesh Kumar] ←── UPI payment ───→ [Unknown 1]             │
│        ₹5,000                              ₹5,000               │
│                                                                  │
│  [Similar case from 3 days ago]  [4 other similar cases]        │
│                                                                  │
│  ──────────────────────────────────────────────────────────     │
│  FOLLOW-UP QUESTIONS                                             │
│  ──────────────────────────────────────────────────────────     │
│                                                                  │
│  ❓ Have you already shared any credentials?                     │
│  ❓ Has any money left your account?                             │
│  ❓ Do you recognize the requesting account?                     │
│                                                                  │
│  ──────────────────────────────────────────────────────────     │
│  RECOMMENDED ACTIONS                                             │
│  ──────────────────────────────────────────────────────────     │
│                                                                  │
│  [1] IMMEDIATE: Contact your bank                               │
│      "Notify your bank about the suspicious payment"            │
│      Status: Needs your permission                              │
│      [Get Help] [Skip]                                          │
│                                                                  │
│  [2] SOON: Monitor account for fraudulent transfers             │
│      "Watch for unexpected money movements"                     │
│      Status: Needs human approval                               │
│      [View] [Skip]                                              │
│                                                                  │
│  [3] REPORT: Submit to Paytm support                            │
│      "We can file a report on your behalf"                      │
│      Status: Needs your consent                                 │
│      [Authorize] [Skip]                                         │
│                                                                  │
│  ──────────────────────────────────────────────────────────     │
│                                                                  │
│  [← Close] [Download Report ↓]  [Escalate to Agent →]          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Buttons & User Actions:

#### 🔘 Button: "[1] Contact your Bank - Get Help"
**User Clicks**: "Get Help" for action 1
```
Frontend (agent-ui.tsx:ActionCard):
  └─ onClick → handleActionClick('contact_bank', 'get_help')
     ├─ If action requires consent:
     │   └─ Show consent card/modal
     │       ├─ Display: "We need your permission to..."
     │       └─ [Authorize] [Cancel]
     │
     ├─ POST /api/v1/investigations/{case_id}/actions/{action_id}/consent
     │   Body: { consented: true }

Backend API Call: POST /api/v1/actions/{action_id}/consent
  └─ actions_routes.py:consent_action()
     ├─ Verify case ownership
     ├─ Verify action exists & pending
     ├─ Check action requires consent
     ├─ UPDATE actions SET
     │   ├─ state = 'approved'
     │   ├─ customer_consented_at = now()
     │   └─ executed_at = NULL (will execute when triggered)
     │
     ├─ Execute action immediately (planner.py:ACTIONS):
     │   ├─ action_type = 'contact_bank'
     │   ├─ Execute on simulated system:
     │   │   └─ systems.py:SimulatedBankDesk.notify(...)
     │   │       ├─ POST to mock bank API
     │   │       ├─ Record call log
     │   │       └─ Store response
     │   │
     │   ├─ Verify step succeeded
     │   ├─ Record audit log:
     │   │   └─ action_executed: "Notified bank desk"
     │   │
     │   └─ UPDATE actions SET executed_at = now()
     │
     └─ Return: Action with updated state

Frontend:
  └─ onSuccess:
     ├─ Show toast: "Bank contacted! They'll investigate within 48 hours"
     ├─ Update action card status: "Completed ✓"
     └─ Refresh results view

Result: Action executed, user notified of next steps
```

---

#### 🔘 Button: "[2] Monitor Account - View"
**User Clicks**: "View" for action 2 (needs human approval)
```
Frontend:
  └─ onClick → showActionDetails('monitor_account')
     ├─ Display additional context:
     │   ├─ "Action pending human agent review"
     │   ├─ "A Paytm fraud specialist will review and approve"
     │   ├─ Estimated time: "2-4 hours"
     │   └─ What to do: "In the meantime, change your password"
     │
     └─ [Understood] [Call Agent]

Result: Shows waiting status, user can call for immediate help
```

---

#### 🔘 Button: "[3] Report to Paytm - Authorize"
**User Clicks**: "Authorize" for action 3
```
Frontend:
  └─ Similar to consent action above
     ├─ Shows consent card
     ├─ Display: "We'll submit a fraud report to Paytm support"
     │
     └─ POST /api/v1/investigations/{case_id}/actions/{action_id}/consent

Backend:
  └─ actions_routes.py:consent_action()
     ├─ Verify + approve
     ├─ Execute: systems.py:SimulatedPaytm.submit_fraud_report(...)
     │   ├─ POST to mock Paytm API
     │   ├─ Return report_id
     │   └─ Store in database
     │
     └─ Return status

Frontend:
  └─ Show: "Report #FP-2024-0987 submitted to Paytm"
     └─ "You'll receive an update in 24-48 hours"

Result: Report submitted, tracking ID provided
```

---

#### 🔘 Button: "Download Report"
**User Clicks**: Download Report button
```
Frontend:
  └─ onClick → downloadReport()
     ├─ GET /api/v1/investigations/{case_id}/report?format=txt
     │   └─ Accept: text/plain

Backend API Call: GET /api/v1/investigations/{case_id}/report?format=txt
  └─ incident_routes.py:get_report()
     ├─ Retrieve or generate report
     ├─ Format as UTF-8 text file:
     │   ├─ Header: Case ID, Date, Transaction Details
     │   ├─ Risk Assessment: Category, Score, Factors
     │   ├─ Evidence: All messages/calls/screenshots (redacted)
     │   ├─ Actions: List of taken steps
     │   └─ Recommendations: Next steps
     │
     ├─ Set response headers:
     │   ├─ Content-Type: text/plain; charset=utf-8
     │   ├─ Content-Disposition: attachment; filename="bytebot-report-{id}.txt"
     │   └─ X-Content-Type-Options: nosniff (prevent MIME sniffing)
     │
     └─ Return: File content (raw text)

Frontend:
  └─ Browser downloads file
     └─ Opens file browser in Download folder

Result: User has PDF/text report for records/bank
```

---

#### 🔘 Button: "Escalate to Agent"
**User Clicks**: Escalate to agent (for immediate help)
```
Frontend:
  └─ onClick → escalateToAgent()
     ├─ POST /api/v1/investigations/{case_id}/escalate
     │   Body: { reason: "user_requested_help" }

Backend API Call: POST /api/v1/investigations/{case_id}/escalate
  └─ agent_routes.py:escalate()
     ├─ Verify ownership
     ├─ Update investigation:
     │   └─ status = 'escalated_to_human'
     │
     ├─ Create escalation record:
     │   └─ INSERT INTO escalations
     │       (investigation_id, reason, requested_at, assigned_to)
     │
     ├─ Notify fraud team (via background job):
     │   └─ Email/SMS to on-call agent
     │
     └─ Return: { escalation_id, wait_time: "5-10 min" }

Frontend:
  └─ Show: "Escalated to Paytm Fraud Team"
     └─ "An agent will contact you shortly"
     └─ "Your case ID: ESC-2024-0987"

Result: Case routed to human agent, user waits for call
```

---

## 8️⃣ SCREEN: Case History (Follow-up)

User can return to home and check "Your Byte Bot cases" to see all past investigations with their current status and outcomes.

