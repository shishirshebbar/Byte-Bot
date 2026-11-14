# Byte Bot Complete User Flow - Part 1: Home to Investigation Screen

## 1️⃣ SCREEN: Home / Paytm-style Dashboard
**File**: `frontend/src/phone-home.tsx`

### What User Sees:
```
┌─────────────────────────────────────────────────┐
│  📱 Phone Screen (Paytm-style app)              │
│  ═════════════════════════════════════════════  │
│                                                 │
│  👤 Welcome back                                │
│  Let's make it simple.                          │
│                                                 │
│  ─────── UPI PAYMENTS ────────                  │
│  [📱 Scan & Pay] [👥 To mobile] [🏦 To bank]   │
│  [💳 Balance & History]                         │
│                                                 │
│  ─────────────────────────────────             │
│  🤖 Something feels wrong?                      │
│     Check a payment with Byte Bot ➜            │
│  ─────────────────────────────────             │
│                                                 │
│  ──── RECENT PAYMENTS ─────                     │
│  Rajesh Kumar  ✓ ₹5,000                         │
│  Amit Singh    ✓ ₹2,500                        │
│  Priya Gupta   ✓ ₹10,000                       │
│                                                 │
│  [🕐 Your Byte Bot cases ➜]                    │
│                                                 │
│  Paytm-style prototype · Synthetic payments    │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Buttons & User Actions:

#### 🔘 Button: "Scan & Pay" / "To mobile" / "To bank"
**User Clicks**: Scan & Pay button
```
Frontend:
  └─ onClick → setNotice("Scan & Pay is a preview...")
     └─ Shows message: "This is a preview in this prototype"
     └─ No backend call

Result: User sees info banner, stays on home screen
```

---

#### 🔘 Button: "Balance & History"
**User Clicks**: Link to transaction history
```
Frontend:
  └─ <Link to="/history">
     └─ React Router navigates to /history page
     └─ Loads TransactionList component

Backend API Call: GET /api/v1/transactions
  └─ transactions_routes.py:list_transactions()
     ├─ Extract owner from HttpOnly cookie (demo_session)
     ├─ Query: SELECT * FROM transactions WHERE owner_id = ?
     ├─ Serialize as JSON
     └─ Return: { transactions: [...] }

Result: Shows list of all transactions
```

---

#### 🔘 Button: "Something feels wrong? Check a payment with Byte Bot" 
**User Clicks**: Byte Bot assistant link
```
Frontend:
  └─ <Link to="/check-payment">
     └─ React Router navigates to /check-payment
     └─ Loads TransactionList component (same as History)

Backend API Call: GET /api/v1/transactions
  └─ Same as above

Result: Shows transaction list to select which one to investigate
```

---

#### 🔘 Button: "Your Byte Bot cases"
**User Clicks**: Link to past investigations
```
Frontend:
  └─ <Link to="/incidents">
     └─ React Router navigates to /incidents
     └─ Loads IncidentList component

Backend API Call: GET /api/v1/incidents
  └─ incident_routes.py:list_incidents()
     ├─ Extract owner from HttpOnly cookie
     ├─ Query: SELECT i.id, i.created_at, i.case_status, t.*
              FROM investigations i
              JOIN transactions t ON t.id = i.transaction_id
              WHERE i.owner_id = ?
     ├─ LEFT JOIN with analysis_runs to get risk category
     ├─ Serialize with transaction details & category
     └─ Return: { incidents: [...] }

Result: Shows list of past cases with their status & risk category
```

---

## 2️⃣ SCREEN: Transaction List / Check Payment Screen
**File**: `frontend/src/transaction-ui.tsx`

### What User Sees:
```
┌─────────────────────────────────────────────────┐
│  📱 All Transactions / Check Payment            │
│  ═════════════════════════════════════════════  │
│                                                 │
│  [← Home]                                       │
│                                                 │
│  Which payment would you like to check?         │
│                                                 │
│  [ Search box                           ]       │
│                                                 │
│  ──────────────────────────────────────────     │
│  Rajesh Kumar          ✓ COMPLETED              │
│  Unexpected UPI credit                          │
│  Date: Nov 10, 2:45 PM                          │
│  Amount: ₹5,000                                 │
│  [Click to select →]                            │
│  ──────────────────────────────────────────     │
│                                                 │
│  Amit Singh            ✓ COMPLETED              │
│  Regular payment                                │
│  Date: Nov 09, 11:20 AM                         │
│  Amount: ₹2,500                                 │
│  [Click to select →]                            │
│  ──────────────────────────────────────────     │
│                                                 │
│  Priya Gupta           ⚠ PENDING                │
│  Suspicious request                             │
│  Date: Nov 08, 9:15 PM                          │
│  Amount: ₹10,000                                │
│  [Click to select →]                            │
│  ──────────────────────────────────────────     │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Buttons & User Actions:

#### 🔘 Button: Select a Transaction
**User Clicks**: Transaction card (e.g., "Rajesh Kumar - ₹5,000")
```
Frontend (investigation.tsx:AskByteBot):
  └─ onClick → open()
     ├─ setBusy(true)
     ├─ POST /api/v1/investigations
     │   Body: { transaction_id: "abc-123-def-456" }
     
Backend API Call: POST /api/v1/investigations
  └─ investigations.py:create()
     ├─ Extract owner from HttpOnly cookie
     ├─ Check if investigation exists for this transaction
     │  └─ Query: SELECT * FROM investigations 
     │            WHERE transaction_id = ? AND owner_id = ?
     │
     ├─ If EXISTS:
     │   └─ Return existing investigation (status: 200)
     │
     ├─ If NEW:
     │   ├─ INSERT into investigations table:
     │   │   ├─ id: UUID
     │   │   ├─ transaction_id: passed value
     │   │   ├─ owner_id: from cookie
     │   │   ├─ input_revision: 1
     │   │   ├─ status: 'open'
     │   │   ├─ created_at: now()
     │   │   └─ updated_at: now()
     │   │
     │   ├─ Copy 8 seeded template transactions to owner
     │   │   └─ On first-time investigation
     │   │
     │   └─ Return new investigation (status: 201)
     │
     └─ Return: Investigation object
     
Frontend:
  └─ onSuccess:
     ├─ presentation?.showCase(data)  [save to context]
     ├─ navigate(`/investigations/${data.id}`)
     ├─ setBusy(false)
     └─ Transitions to Investigation Workspace screen

Result: Opens investigation workspace for selected transaction
```

---

## 3️⃣ SCREEN: Investigation Workspace - Context Entry
**File**: `frontend/src/investigation.tsx`

### What User Sees:
```
┌─────────────────────────────────────────────────────────────────┐
│  📱 Byte Bot Investigation Workspace                            │
│  ════════════════════════════════════════════════════════════   │
│                                                                 │
│  Transaction: Rajesh Kumar                                      │
│  ₹5,000 • Nov 10, 2:45 PM                                      │
│  Unexpected UPI credit                                          │
│  Status: Open                                                   │
│                                                                 │
│  ─────────────────────────────────────────────────────────     │
│  STEP 1: CONTEXT                                               │
│  ─────────────────────────────────────────────────────────     │
│                                                                 │
│  Did you expect this payment?                                   │
│  ⭕ Not sure  ⭕ Yes  ⭕ No                                      │
│                                                                 │
│  Do you know the sender?                                        │
│  ⭕ Not sure  ⭕ Yes  ⭕ No                                      │
│                                                                 │
│  Has sender asked you to repay them?                            │
│  ⭕ Not sure  ⭕ Yes  ⭕ No                                      │
│                                                                 │
│  How did they contact you?                                      │
│  ☐ Phone call  ☐ WhatsApp  ☐ SMS  ☐ Paytm request  ☐ Other   │
│                                                                 │
│  What type of payment are they requesting?                      │
│  ⭕ Unknown  ⭕ Same sender VPA  ⭕ Different VPA                │
│  ⭕ Bank account  ⭕ Payment request  ⭕ Not specified          │
│                                                                 │
│  Target VPA / Account:                                          │
│  [ ___________________________________ ]                       │
│                                                                 │
│  Pressure tactics used?                                         │
│  ☐ Urgency  ☐ Threats  ☐ Bank avoidance  ☐ Secrecy            │
│                                                                 │
│  Have you already sent money?                                   │
│  ⭕ Not sure  ⭕ Yes  ⭕ No                                      │
│                                                                 │
│  [← Back]  [Save & Continue →]                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Buttons & User Actions:

#### 🔘 Radio Buttons: Multiple Choice Answers
**User Clicks**: "Did you expect this payment? → No"
```
Frontend (investigation.tsx:Workspace):
  └─ Local state update:
     ├─ data.context.expected_payment = 'no'
     ├─ UI re-renders
     └─ Mark form as dirty (unsaved changes)

Result: Selection highlighted, form marked dirty
```

#### 🔘 Text Input: Target VPA
**User Types**: "upi://pay?pa=unknown@bank"
```
Frontend (investigation.tsx:Workspace):
  └─ onChange event:
     ├─ Update data.context.requested_vpa = user_input
     ├─ Redact credentials (via field validator)
     ├─ Mark form as dirty
     └─ Show as typed (but will be redacted on save)

Result: Text appears in field, marked for redaction on save
```

#### 🔘 Button: "Save & Continue"
**User Clicks**: Save button
```
Frontend (investigation.tsx:Workspace):
  └─ onClick → saveContext()
     ├─ Check dirty flag
     ├─ If no changes: skip backend call
     ├─ If dirty:
     │   ├─ setSaving(true)
     │   └─ PATCH /api/v1/investigations/{case_id}/context
     │       Body: {
     │         expected_payment: 'no',
     │         knows_sender: 'yes',
     │         repayment_requested: 'unknown',
     │         contact_channels: ['call', 'whatsapp'],
     │         requested_destination_type: 'different_vpa',
     │         requested_vpa: '[REDACTED]',
     │         pressure_tactics: ['urgency'],
     │         already_sent_money: 'no',
     │         expected_revision: 1
     │       }

Backend API Call: PATCH /api/v1/investigations/{case_id}/context
  └─ investigations.py:save_context()
     ├─ Extract owner from cookie
     ├─ owned_case() → validates ownership + revision
     │   └─ SELECT * FROM investigations WHERE id = ? AND owner_id = ?
     │   └─ If expected_revision ≠ case.input_revision → HTTP 409 (stale)
     │
     ├─ Model validation (via ContextPatch):
     │   ├─ Validate field ranges
     │   ├─ Redact VPA/credentials
     │   ├─ Validate presence of required fields
     │   └─ Reject if validation fails
     │
     ├─ UPDATE investigations SET
     │   ├─ context = jsonb_set(context, '{expected_payment}', '"no"')
     │   ├─ (repeat for all fields)
     │   ├─ updated_at = now()
     │   └─ input_revision still = 1 (no change triggers re-analysis)
     │
     └─ Return: Investigation object with updated context

Frontend:
  └─ onSuccess:
     ├─ Update local data with response
     ├─ Clear dirty flag
     ├─ setSaving(false)
     ├─ Show success toast: "Context saved"
     └─ Optionally auto-navigate to next section

Result: Data persisted, ready for next step (evidence upload)
```

---

## Navigation Between Sections

**Frontend Hash-based Navigation** (`screen-path.ts`):
```
/investigations/{id}            → Workspace Home (all tabs)
/investigations/{id}#context    → Context tab active
/investigations/{id}#evidence   → Evidence tab active
/investigations/{id}#analysis   → Analysis/Results tab active
```

User can click between tabs without re-loading data from server (except polling for analysis results).

