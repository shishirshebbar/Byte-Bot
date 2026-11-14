# Byte Bot Complete User Journey - Visual Summary

## 🎯 Complete End-to-End Flow

```
START: Home Screen
   ↓
   User sees: "Something feels wrong? Check a payment with Byte Bot"
   ├─ Clicks: "Check a payment"
   ├─ Backend: GET /api/v1/transactions (list all payments)
   └─ Shows: Transaction List
   
   ↓
SCREEN 2: Transaction List
   ├─ User sees: List of payments
   ├─ Clicks: Select a transaction (e.g., "Rajesh Kumar - ₹5,000")
   ├─ Backend: POST /api/v1/investigations
   │   └─ Creates new investigation case (or returns existing)
   └─ Navigates to: Investigation Workspace
   
   ↓
SCREEN 3: Investigation Workspace - Context Tab
   ├─ User sees: Form with 8 context questions
   │   ├─ "Did you expect this payment?"
   │   ├─ "Do you know the sender?"
   │   ├─ "Contact method?" (WhatsApp, SMS, Call, etc)
   │   └─ "Target VPA?" (where they asked you to send money)
   │
   ├─ User enters: Answers (radio buttons, checkboxes, text)
   ├─ Clicks: "Save & Continue"
   ├─ Backend: PATCH /api/v1/investigations/{id}/context
   │   ├─ Validates all fields
   │   ├─ Redacts PII (phone, email, UPI ID)
   │   └─ Stores in database
   │
   └─ Shows: "Context saved ✓"
   
   ↓
SCREEN 4: Investigation Workspace - Evidence Tab
   ├─ User sees: Evidence upload options
   │   ├─ "Paste Message/Email"
   │   ├─ "Type Call Summary"
   │   ├─ "Upload Screenshot" ← Most common
   │   └─ "Voice Note"
   │
   ├─ Clicks: "+ Upload Screenshot"
   ├─ File picker opens
   ├─ User selects: "message_screenshot.png"
   │
   ├─ Backend: POST /api/v1/investigations/{id}/evidence
   │   ├─ 1. Parse multipart form (no temp files)
   │   ├─ 2. Decode image (PIL validation)
   │   │   ├─ Check: file size < 5 MiB ✓
   │   │   ├─ Check: format is PNG/JPEG ✓
   │   │   ├─ Check: pixel count < 16 MP ✓
   │   │   └─ Check: not animated ✓
   │   │
   │   ├─ 3. Process image (all in-memory):
   │   │   ├─ Detect QR codes (if any)
   │   │   ├─ Run EasyOCR extraction (CPU local)
   │   │   │   └─ Returns text: "Hi, your account needs verification..."
   │   │   ├─ Detect request markers
   │   │   │   └─ Flags: "urgent_language", "credential_request"
   │   │   └─ Redact credentials (PII cleanup)
   │   │
   │   ├─ 4. Store evidence:
   │   │   └─ INSERT evidence table
   │   │       (ocr_text, metadata, review_state='needs_review')
   │   │
   │   └─ Returns: Evidence with OCR text
   │
   ├─ Shows: "Screenshot uploaded ✓"
   └─ User sees: OCR-extracted text in panel
       "Hi, your account needs verification..."
       ⚠️ "Urgent language detected"
       ⚠️ "Credential request detected"
   
   ↓
   ├─ User clicks: "Confirm" (or edits text, then confirms)
   ├─ Backend: PATCH /api/v1/investigations/{id}/evidence/{evidence_id}
   │   ├─ Update review_state: 'needs_review' → 'confirmed'
   │   ├─ Increment input_revision: 1 → 2
   │   │   (This triggers automatic re-analysis)
   │   └─ Record audit event
   │
   └─ Shows: "Evidence confirmed ✓"
   
   ↓
SCREEN 5: Investigation Workspace - Auto-Refresh (Analysis Running)
   ├─ Shows: Spinner "Byte Bot is analyzing your evidence..."
   │
   ├─ Backend (AnalysisWorker):
   │   ├─ 1. Poll database for pending analysis_runs
   │   ├─ 2. Claim run (acquire lease, 60 sec timeout)
   │   │
   │   ├─ 3. Execute LangGraph Supervisor:
   │   │   ├─ Node 1: Transaction Context
   │   │   │   └─ Load transaction + investigation context
   │   │   │
   │   │   ├─ Node 2: Message Analysis
   │   │   │   ├─ Call Gemini API with evidence text
   │   │   │   ├─ Extract signals: fraud_patterns, confidence
   │   │   │   └─ Redact credentials from results
   │   │   │
   │   │   ├─ Node 3: Risk Investigation
   │   │   │   ├─ Apply Python decision table (risk_rules.py)
   │   │   │   ├─ Check transaction status (PENDING/FAILED/COMPLETED)
   │   │   │   ├─ Check dangerous mechanisms (credential request, QR, PIN)
   │   │   │   ├─ Apply rules table (known_sender, expected_payment, etc)
   │   │   │   ├─ Calculate risk category: high/medium/low
   │   │   │   ├─ Calculate risk_score: 0-100 (display only)
   │   │   │   └─ Walk fraud graph (find similar cases)
   │   │   │
   │   │   └─ Node 4: Incident Resolution
   │   │       ├─ Generate follow-up questions
   │   │       ├─ Generate action plan
   │   │       └─ Determine policy gate:
   │   │           ├─ auto (no approval needed)
   │   │           ├─ needs_customer_consent
   │   │           └─ needs_human_approval
   │   │
   │   ├─ 4. Store results:
   │   │   ├─ analysis_runs: state='complete', output_data={...}
   │   │   ├─ risk_assessments: category, score, factors
   │   │   ├─ agent_traces: debug info
   │   │   └─ (optionally) reports: downloadable summary
   │   │
   │   └─ Release lease (mark complete)
   │
   ├─ Frontend polls: GET /api/v1/investigations/{id} (every 1 sec)
   │   ├─ Detects: state changed to 'complete'
   │   ├─ Auto-navigates to: Results tab
   │   └─ Stops polling
   │
   └─ Spinner disappears
   
   ↓
SCREEN 6: Investigation Workspace - Results Tab
   ├─ User sees: RISK ASSESSMENT
   │   ├─ 🔴 HIGH RISK / 🟡 MEDIUM RISK / 🟢 LOW RISK
   │   ├─ Risk Score: 87/100 (with progress bar)
   │   ├─ Risk Factors:
   │   │   ✓ Credential request detected
   │   │   ✓ Urgent language detected
   │   │   ✓ Unknown sender
   │   │   ✓ Different VPA requested
   │   │
   │   ├─ FRAUD GRAPH:
   │   │   └─ Shows related/similar cases (if any)
   │   │
   │   ├─ FOLLOW-UP QUESTIONS:
   │   │   ├─ "Have you already shared your credentials?"
   │   │   ├─ "Has money left your account?"
   │   │   └─ "Can you contact your bank?"
   │   │
   │   └─ RECOMMENDED ACTIONS:
   │       ├─ [1] Contact your bank (needs consent)
   │       ├─ [2] Monitor account (needs approval)
   │       └─ [3] Report to Paytm (needs consent)
   │
   ├─ Buttons available:
   │   ├─ [Action buttons: Get Help, Authorize, Skip]
   │   ├─ [Download Report ↓]
   │   ├─ [Escalate to Agent →]
   │   └─ [← Close/Back to Home]
   │
   ├─ User clicks: "[1] Contact your bank - Get Help"
   ├─ Backend: POST /api/v1/actions/{id}/consent
   │   ├─ Update action state: approved
   │   ├─ Execute on simulated bank system:
   │   │   └─ Call SimulatedBankDesk.notify(...)
   │   ├─ Record audit event
   │   └─ Return status
   │
   └─ Shows: "Bank contacted! They'll investigate within 48 hours"
   
   ↓
   ├─ User clicks: "[3] Report to Paytm - Authorize"
   ├─ Backend: POST /api/v1/actions/{id}/consent
   │   ├─ Execute: SimulatedPaytm.submit_fraud_report(...)
   │   ├─ Return: report_id
   │   └─ Update action state: executed
   │
   └─ Shows: "Report #FP-2024-0987 submitted"
   
   ↓
   ├─ User clicks: "Download Report ↓"
   ├─ Backend: GET /api/v1/incidents/{id}/report?format=txt
   │   └─ Generate UTF-8 text file with:
   │       ├─ Case details
   │       ├─ Risk assessment
   │       ├─ Evidence summary (redacted)
   │       ├─ Actions taken
   │       └─ Recommendations
   │
   └─ Browser downloads: "bytebot-report-{id}.txt"
   
   ↓
   ├─ User clicks: "Escalate to Agent →"
   ├─ Backend: POST /api/v1/investigations/{id}/escalate
   │   ├─ Update status: escalated_to_human
   │   ├─ Create escalation record
   │   ├─ Notify on-call fraud agent
   │   └─ Return: wait time (5-10 min)
   │
   └─ Shows: "Escalated to Fraud Team - Waiting for agent call"
   
   ↓
   └─ User clicks: "← Close" or navigates to Home
       └─ Returns to: Home Screen
           [Your Byte Bot cases]
           ├─ Shows: "Rajesh Kumar - HIGH RISK" (with current status)
           └─ User can click to re-open case or view report
```

---

## 📊 Architecture Layers

```
┌──────────────────────────────────────────────────────────────┐
│ LAYER 1: USER INTERFACE (React/Vite)                         │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  phone-home.tsx          → Home screen (Paytm-style)        │
│  transaction-ui.tsx      → Transaction list / selection     │
│  investigation.tsx       → Workspace (context, evidence)    │
│  results.tsx             → Analysis results display         │
│  agent-ui.tsx            → Follow-up questions + actions    │
│  voice-ui.tsx            → Voice note interface (Sarvam)    │
│                                                              │
│  HTTP calls via api.ts (relative /api path through Vite)    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                            ↓ HTTP/REST
┌──────────────────────────────────────────────────────────────┐
│ LAYER 2: API GATEWAY (FastAPI on :8000)                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  transactions_routes.py     → GET /transactions             │
│  investigations.py          → POST /investigations           │
│                             → PATCH /investigations/{id}/... │
│                             → POST /evidence                │
│  incident_routes.py         → GET /incidents                │
│                             → GET /report                   │
│  actions_routes.py          → POST /actions/{id}/consent    │
│  agent_routes.py            → POST /escalate                │
│  voice_routes.py            → POST /voice-notes             │
│                                                              │
│  Validates ownership via HttpOnly demo_session cookie       │
│  Enforces optimistic locking (expected_revision)            │
│  All input is redacted before persistence                   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                            ↓ Psycopg
┌──────────────────────────────────────────────────────────────┐
│ LAYER 3: BACKEND WORKER (AnalysisWorker)                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Bounded worker (2 concurrent slots, 60 sec leases)         │
│  Polls analysis_runs table every 2 seconds                  │
│  Executes LangGraph Supervisor graph:                       │
│                                                              │
│  ┌─ Node 1: Transaction Context                           │
│  ├─ Node 2: Message Analysis (calls Gemini/Sarvam)        │
│  ├─ Node 3: Risk Investigation (applies Python rules)     │
│  └─ Node 4: Incident Resolution (generates actions)       │
│                                                              │
│  Stores results atomically in analysis_runs,               │
│  risk_assessments, agent_traces tables                     │
│                                                              │
│  All decisions deterministic (no LLM randomness in routing) │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                            ↓ Psycopg
┌──────────────────────────────────────────────────────────────┐
│ LAYER 4: DATABASE (PostgreSQL on :55433)                     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  tables:                                                     │
│  ├─ transactions          (seeded with demo data)           │
│  ├─ investigations        (cases user opens)                │
│  ├─ evidence              (messages, calls, screenshots)    │
│  ├─ analysis_runs         (supervisor execution records)    │
│  ├─ risk_assessments      (category, score, factors)        │
│  ├─ agent_traces          (for debugging)                   │
│  ├─ reports               (downloadable summaries)          │
│  ├─ actions               (follow-up actions, states)       │
│  ├─ audit_log             (hash-chained audit trail)        │
│  └─ escalations           (human escalations)               │
│                                                              │
│  Supports:                                                   │
│  ├─ Session ownership (always derive from cookie)          │
│  ├─ Optimistic locking (input_revision checks)             │
│  ├─ Credential redaction (PII removed before storage)      │
│  └─ Audit ledger (immutable event history)                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                            ↑
         ┌────────────────────────────────────┐
         │ EXTERNAL SERVICES (Simulated)      │
         ├────────────────────────────────────┤
         │                                    │
         │ SimulatedBankDesk    (mock API)   │
         │ SimulatedPaytm       (mock API)   │
         │                                    │
         │ + Optional Live:                   │
         │ Gemini              (extraction)   │
         │ Sarvam              (voice-to-text)│
         │                                    │
         └────────────────────────────────────┘
```

---

## 🔄 Data Flow Summary

```
User uploads screenshot
         ↓
    Frontend validates file
         ↓
  POST /api/v1/investigations/{id}/evidence
         ↓
  Backend parses multipart form
         ↓
  Decode image → Validate format/size
         ↓
  Process in memory:
  ├─ QR code detection (if any)
  ├─ EasyOCR extraction (local CPU)
  ├─ Request marker detection (regex)
  └─ Credential redaction
         ↓
  Store in evidence table (review_state='needs_review')
         ↓
  User reviews OCR text
         ↓
  User clicks "Confirm"
         ↓
  PATCH /api/v1/investigations/{id}/evidence/{evidence_id}
         ↓
  Update: confirmed_text, review_state='confirmed'
         ↓
  Increment input_revision (triggers re-analysis)
         ↓
  AnalysisWorker polls and detects new revision
         ↓
  Execute LangGraph Supervisor:
  Node 1 → Node 2 (Gemini extraction) → Node 3 (rules) → Node 4 (actions)
         ↓
  Store results in analysis_runs, risk_assessments
         ↓
  Frontend polls and detects completion
         ↓
  Auto-navigate to Results tab
         ↓
  Display risk category, score, factors, actions
         ↓
  User clicks action buttons (Get Help, Authorize, etc)
         ↓
  Backend executes actions on simulated systems
         ↓
  Results updated, audit events recorded
```

---

## 🔐 Security & Privacy

```
Every step:
  1. Verify HttpOnly demo_session cookie (derive owner)
  2. Fetch case from DB, check owner_id matches
  3. Check expected_revision (optimistic lock)
  4. If foreign ID: return same 404 (no information leak)
  
Before storing or sending to provider:
  1. Redact all PII (phone, email, UPI, OTP, account #)
  2. Keep labels, remove values
  3. Safe to share with Gemini/Sarvam
  
For images:
  1. Never written to disk
  2. Decoded in memory only
  3. Closed after OCR
  4. No image URLs stored anywhere
  
Audit trail:
  1. Every action recorded with timestamp
  2. Hash-chained per case (immutable)
  3. Can verify ledger integrity
  4. Available for compliance review
```

