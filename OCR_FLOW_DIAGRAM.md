# OCR Request Flow Diagram

## User Uploads Screenshot

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FRONTEND (React UI)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [User clicks "Upload Screenshot" Button]                          │
│             ↓                                                       │
│  [File input dialog opens]                                         │
│  User selects PNG/JPEG image (max 5 MiB)                           │
│             ↓                                                       │
│  [Form prepared with:                                              │
│   - file: image bytes                                              │
│   - expected_revision: current case revision]                      │
│             ↓                                                       │
│  POST /api/v1/investigations/{case_id}/evidence                    │
│  Content-Type: multipart/form-data                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Backend Processing Pipeline

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     FASTAPI BACKEND                                      │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. PARSE UPLOAD (uploads.py:screenshot_body)                           │
│  ────────────────────────────────────────                               │
│     [Request arrives]                                                   │
│         ↓                                                               │
│     [Validate multipart format]                                         │
│         ↓                                                               │
│     [Extract 'file' field → image bytes]                                │
│     [Extract 'expected_revision' field → revision #]                    │
│         ↓                                                               │
│     [Enforce size limits: 5 MiB file, 16 MP pixels]                     │
│                                                                          │
│                                                                          │
│  2. DECODE IMAGE (ocr.py:decode_image)                                  │
│  ──────────────────────────────────────                                 │
│     [Image bytes in memory]                                             │
│         ↓                                                               │
│     [PIL opens image → validate format (PNG/JPEG)]                      │
│         ↓                                                               │
│     [Check dimensions, pixel count, not animated]                       │
│         ↓                                                               │
│     [Convert to RGB]                                                    │
│         ↓                                                               │
│     [Return PIL Image object + metadata]                                │
│     {content_type, width, height, size_bytes}                           │
│                                                                          │
│                                                                          │
│  3. EXTRACT TEXT + QR CODES (investigations.py:process_image)           │
│  ──────────────────────────────────────────────────────────             │
│     [PIL Image in memory]                                               │
│         ↓                                                               │
│     ┌─ QR Detection (qr.py)                                             │
│     │  └─→ Scan for UPI QR codes                                        │
│     │      └─→ Parse payment intents                                    │
│     │          └─→ Add to metadata['qr_payments']                       │
│     │                                                                   │
│     ├─ OCR Extraction (OCRAdapter)                                      │
│     │  └─→ Check if OCR thread available                               │
│     │      ├─ YES → Run EasyOCR                                         │
│     │      │        └─→ Extract text (conf ≥ 0.3)                      │
│     │      │            └─→ Join with newlines                         │
│     │      │                └─→ Return text + 'success'                 │
│     │      │                                                            │
│     │      └─ NO (OCR busy) → Return '' + 'ocr_unavailable'            │
│     │                                                                   │
│     └─ Safety Analysis (safety.py)                                      │
│        └─→ Detect request markers                                       │
│            └─→ Add to metadata['request_markers']                       │
│                └─→ Flag: urgent, verify, credential, etc.              │
│         ↓                                                               │
│     [Redact credentials (redaction.py)]                                 │
│     Remove: phones, emails, accounts, UPI IDs, OTPs                    │
│         ↓                                                               │
│     [Truncate to 10,000 chars max]                                      │
│         ↓                                                               │
│     [Return: text, metadata, notice]                                    │
│                                                                          │
│                                                                          │
│  4. STORE EVIDENCE (investigation_store.py:add_evidence)                │
│  ─────────────────────────────────────────────────────                 │
│     [With database transaction]                                         │
│         ↓                                                               │
│     [Validate case ownership (HttpOnly cookie)]                         │
│     [Validate expected_revision (optimistic lock)]                      │
│         ↓                                                               │
│     INSERT INTO evidence (                                              │
│       id: UUID,                                                         │
│       investigation_id,                                                 │
│       type: 'screenshot',                                               │
│       review_state: 'needs_review',                                     │
│       ocr_text: extracted_text,                                         │
│       confirmed_text: NULL,                                             │
│       metadata: { qr_payments, request_markers, dimensions },           │
│       notice: success/failure_code                                      │
│     )                                                                   │
│         ↓                                                               │
│     [Return: EvidenceResult]                                            │
│                                                                          │
│         ↓ HTTP 201 Created                                              │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Frontend: Review & Confirm

```
┌─────────────────────────────────────────────────────────────────────┐
│                   FRONTEND (Evidence Panel)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  [Evidence appears in panel with status 'needs_review']           │
│             ↓                                                       │
│  OCR-extracted text displayed in editable field:                   │
│  ┌──────────────────────────────────────────────┐                 │
│  │ "Hi, your account needs verification..."    │ ← User can edit  │
│  │ "Please reply with your UPI PIN and OTP."   │                 │
│  │ [REDACTED PII markers shown]                │                 │
│  └──────────────────────────────────────────────┘                 │
│                                                                     │
│  [Safety alerts if request markers detected]                       │
│  ⚠️ "Urgent language detected"                                     │
│  ⚠️ "Credential request detected"                                  │
│                                                                     │
│  [QR payment details if QR found]                                  │
│  💳 "UPI QR found: upi://pay?pa=scammer@bank&am=1000"             │
│                                                                     │
│  [Buttons]                                                          │
│  [Confirm] [Edit] [Delete]                                         │
│      ↓                                                               │
│  User clicks [Confirm]                                              │
│      ↓                                                               │
│  POST /api/v1/investigations/{case_id}/evidence/{evidence_id}      │
│  {                                                                 │
│    "text": "Hi, your account needs verification...",              │
│    "confirmed": true,                                              │
│    "expected_revision": 42                                         │
│  }                                                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Backend: Confirmation & Re-Analysis

```
┌──────────────────────────────────────────────────────────────────────┐
│                    FASTAPI BACKEND (Confirmation)                    │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. VALIDATE & UPDATE (investigations.py:confirm)                   │
│  ───────────────────────────────────────                            │
│     [PATCH arrives with confirmed text]                             │
│         ↓                                                            │
│     [Check case ownership]                                           │
│     [Check expected_revision matches case]                           │
│         ↓                                                            │
│     [If user edited text: re-detect request_markers]                │
│         ↓                                                            │
│     UPDATE evidence SET                                             │
│       confirmed_text = user_text,                                   │
│       review_state = 'confirmed',                                   │
│       notice = NULL,                                                │
│       metadata = { ...markers, qr_payments, dimensions }            │
│         ↓                                                            │
│     [Increment case input_revision]                                 │
│         ↓                                                            │
│     [Record audit event]                                            │
│         ↓                                                            │
│     [Return HTTP 200]                                               │
│                                                                      │
│                                                                      │
│  2. TRIGGER RE-ANALYSIS (implicit)                                  │
│  ──────────────────────────────                                     │
│     [Frontend polls /api/v1/investigations/{case_id}]               │
│         ↓                                                            │
│     [Detects new input_revision]                                    │
│         ↓                                                            │
│     [Auto-submits to analysis: POST /analyze]                       │
│         ↓                                                            │
│     [AnalysisWorker picks up run]                                   │
│         ↓                                                            │
│     ┌─ LangGraph Supervisor ──────────────────────┐                │
│     │                                             │                │
│     │  1. Transaction Context Node                │                │
│     │     └─ Read transaction details              │                │
│     │                                             │                │
│     │  2. Message Analysis Node                   │                │
│     │     └─ Input: confirmed OCR text             │                │
│     │        └─ Gemini/Sarvam extracts signals    │                │
│     │        └─ Outputs: fraud_patterns           │                │
│     │                                             │                │
│     │  3. Risk Investigation Node                 │                │
│     │     └─ Input: signals, context              │                │
│     │        └─ Decision table assessment          │                │
│     │        └─ Outputs: category, score          │                │
│     │                                             │                │
│     │  4. Incident Resolution Node                │                │
│     │     └─ Input: category, signals             │                │
│     │        └─ Generate action plan               │                │
│     │        └─ Outputs: follow-up questions      │                │
│     │                                             │                │
│     └─────────────────────────────────────────────┘                │
│         ↓                                                            │
│     [Store risk_assessment + agent_trace]                           │
│         ↓                                                            │
│     [Frontend auto-refresh shows new category]                      │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

## Data Flow: OCR → Evidence → Analysis → Decision

```
Screenshot Image
    ↓
    ├─ Decode (validate format, size)
    │   ↓
    ├─ QR Detection
    │   └─→ Extract UPI payment intents
    │
    ├─ OCR Extraction
    │   └─→ EasyOCR English model
    │       └─→ Confidence ≥ 0.3 threshold
    │
    ├─ Redaction
    │   └─→ Remove PII patterns
    │
    ├─ Safety Analysis
    │   └─→ Detect request markers
    │
    ↓
evidence table
  ├─ ocr_text: "raw extracted text"
  ├─ metadata: { qr_payments, request_markers, dimensions }
  ├─ notice: success/failure code
  └─ review_state: 'needs_review'
    ↓
[User confirms in UI]
    ↓
evidence table
  ├─ confirmed_text: "user-approved text"
  └─ review_state: 'confirmed'
    ↓
[input_revision increments]
    ↓
analysis_runs table (new run created)
    ↓
LangGraph Supervisor executes:
  1. Transaction Context
  2. Message Analysis (processes confirmed_text)
  3. Risk Investigation
  4. Incident Resolution
    ↓
risk_assessments table
  ├─ category: 'high_risk' | 'medium_risk' | 'low_risk'
  ├─ risk_score: 0-100
  ├─ risk_factors: [list of detected patterns]
  └─ decision_basis: Python rules table
    ↓
[Frontend displays decision]
    ├─ Risk gauge
    ├─ Fraud graph
    ├─ Follow-up questions
    └─ Recommended actions
```

## Error Scenarios

```
┌─────────────────────────────────────────────────────────────┐
│               ERROR HANDLING                                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Image too large (> 5 MiB)                                 │
│  ↓ HTTP 413 'evidence_too_large'                            │
│  ↓ UI: "Use an image up to 5 MiB"                          │
│                                                             │
│  Wrong format (BMP, TIFF, animated GIF)                    │
│  ↓ HTTP 415 'unsupported_image'                             │
│  ↓ UI: "Use a PNG or JPEG screenshot"                      │
│                                                             │
│  Corrupted image data                                       │
│  ↓ HTTP 422 'invalid_image'                                 │
│  ↓ UI: "This image could not be decoded"                   │
│                                                             │
│  OCR thread busy                                            │
│  ↓ evidence.notice = 'ocr_unavailable'                      │
│  ↓ evidence.review_state = 'needs_review'                   │
│  ↓ UI: "OCR unavailable; enter text manually"              │
│                                                             │
│  OCR returned empty text                                    │
│  ↓ evidence.notice = 'unreadable'                           │
│  ↓ evidence.review_state = 'needs_review'                   │
│  ↓ UI: "Couldn't read screenshot; enter text manually"     │
│                                                             │
│  Stale revision check                                       │
│  ↓ HTTP 409 'stale_input'                                   │
│  ↓ UI: "Another action changed this case; reload"          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Key Components & Technologies

| Component | Technology | Role |
|-----------|-----------|------|
| Image Decoding | Python PIL/Pillow | Validate format, dimensions, memory safety |
| OCR Engine | EasyOCR 1.7.2 | Extract English text from images |
| Neural Network | PyTorch 2.6.0 | EasyOCR backbone |
| QR Detection | OpenCV (via qr.py) | Extract UPI payment intents |
| Redaction | Regex patterns (redaction.py) | Remove PII before storage |
| Safety Markers | Regex patterns (safety.py) | Detect social engineering language |
| Storage | PostgreSQL evidence table | Persist extracted text + metadata |
| Analysis | LangGraph Supervisor | Process confirmed text through agents |

## Performance Characteristics

```
┌────────────────────────────────────────────────┐
│ OCR TIMING BREAKDOWN                           │
├────────────────────────────────────────────────┤
│                                                │
│ Image Decode        ~10 ms                     │
│ QR Detection        ~50 ms                     │
│ OCR Extraction      500-2000 ms (CPU-bound)    │
│ Redaction           ~2 ms                      │
│ Safety Markers      ~5 ms                      │
│ Database Store      ~20 ms                     │
│ ─────────────────────────────────              │
│ TOTAL (avg)         ~600-2000 ms               │
│                                                │
│ Depends on:                                    │
│ • Image size (height × width)                  │
│ • Text density (amount of text)                │
│ • CPU cores available                          │
│ • Other system load                            │
│                                                │
│ Non-blocking:                                  │
│ • If OCR locked: fallback immediately         │
│ • User can manually enter text                 │
│ • No timeout waiting                           │
│                                                │
└────────────────────────────────────────────────┘
```

---

## Summary

**Complete OCR workflow in Byte Bot:**

1. **Upload** → Screenshot multipart upload with revision check
2. **Decode** → Validate format, size, pixel count
3. **Extract** → OCR + QR codes + safety markers (in parallel)
4. **Redact** → Remove PII before storage
5. **Review** → User sees extracted text, can edit
6. **Confirm** → User approves text, triggers re-analysis
7. **Analyze** → LangGraph supervisor processes confirmed evidence
8. **Decide** → Risk category determined from analysis
9. **Act** → Show decision, follow-up questions, recommendations

All processing is **local (no external APIs for OCR)**, **in-memory (no disk writes)**, and **gracefully degraded (fallback on errors)**.
