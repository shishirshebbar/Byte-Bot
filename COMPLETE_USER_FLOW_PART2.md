# Byte Bot Complete User Flow - Part 2: Evidence Upload & Processing

## 4️⃣ SCREEN: Investigation Workspace - Evidence Tab
**File**: `frontend/src/investigation.tsx`

### What User Sees:
```
┌──────────────────────────────────────────────────────────────────┐
│  📱 Byte Bot Investigation Workspace                             │
│  ════════════════════════════════════════════════════════════    │
│                                                                  │
│  Transaction: Rajesh Kumar                                       │
│  ₹5,000 • Nov 10, 2:45 PM                                       │
│  Status: Open                                                    │
│                                                                  │
│  [Context] [Evidence] [Analysis] [Results]                       │
│                      ↑ ACTIVE TAB                                │
│                                                                  │
│  ──────────────────────────────────────────────────────────     │
│  STEP 2: EVIDENCE                                                │
│  ──────────────────────────────────────────────────────────     │
│                                                                  │
│  Add evidence to this case:                                      │
│  Choose type of evidence:                                        │
│                                                                  │
│  [ + Paste Message/Email    ]                                   │
│  [ + Type Call Summary      ]                                   │
│  [ + Upload Screenshot      ]                                   │
│  [ + Voice Note (Sarvam AI) ]                                   │
│                                                                  │
│  ──────────────────────────────────────────────────────────     │
│  EXISTING EVIDENCE (for this case):                              │
│                                                                  │
│  [None yet]                                                      │
│                                                                  │
│  ──────────────────────────────────────────────────────────     │
│  [← Back]  [Continue Analysis →]                               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### Buttons & User Actions:

#### 🔘 Button: "+ Upload Screenshot"
**User Clicks**: Screenshot upload button
```
Frontend (investigation.tsx):
  └─ onClick → open file dialog
     ├─ <input type="file" accept=".png,.jpg,.jpeg">
     └─ showFileDialog()

Result: Native file picker opens, user selects PNG/JPEG image
```

---

#### 📄 User Selects Image File
**User Selects**: "fraud_message_screenshot.png" (file size: 2.5 MiB)
```
Frontend (investigation.tsx:submit_evidence):
  └─ onChange event:
     ├─ Validate file:
     │   ├─ contentType = "image/png" ✓
     │   ├─ fileSize = 2,621,440 bytes (< 5 MiB) ✓
     │   └─ Dimensions: 1080x1920 pixels (< 16 MP) ✓
     │
     ├─ Prepare FormData:
     │   ├─ Create multipart body with:
     │   │   ├─ field: "file" → image blob
     │   │   ├─ field: "expected_revision" → 1
     │   │   └─ Content-Type for file: "image/png"
     │   │
     │   └─ POST /api/v1/investigations/{case_id}/evidence
     │       Headers: Content-Type: multipart/form-data
     │
     └─ Show upload progress indicator

Backend API Call: POST /api/v1/investigations/{case_id}/evidence
  └─ investigations.py:submit_evidence()
     ├─ Extract owner from cookie
     ├─ check_case() → Validates ownership
     │   └─ Query: SELECT id FROM investigations WHERE id = ? AND owner_id = ?
     │
     ├─ Parse multipart form (uploads.py:screenshot_body):
     │   ├─ Validate boundary format
     │   ├─ Extract "file" field bytes → data
     │   ├─ Extract "expected_revision" field → revision = 1
     │   └─ Enforce BODY_LIMIT = 6 MiB total
     │       └─ If exceeded: raise EvidenceError(413, 'evidence_too_large')
     │
     ├─ Decode image (ocr.py:decode_image):
     │   ├─ Validate file size: 2.5 MiB < 5 MiB ✓
     │   ├─ Validate content-type matches PNG
     │   ├─ Open image with PIL
     │   ├─ Validate format: PNG == PNG ✓
     │   ├─ Validate pixel count: 1080x1920 = 2,073,600 px < 16 MP ✓
     │   ├─ Validate not animated (n_frames == 1) ✓
     │   ├─ Convert to RGB
     │   ├─ Return: PIL Image object + metadata
     │   │   {
     │   │     content_type: "image/png",
     │   │     width: 1080,
     │   │     height: 1920,
     │   │     size_bytes: 2621440
     │   │   }
     │   └─ If validation fails:
     │       └─ raise EvidenceError(413 or 415 or 422, code, message)
     │
     ├─ Process image (investigations.py:process_image):
     │   ├─ [All in-memory, image never touches disk]
     │   │
     │   ├─ QR Detection (qr.py:payment_intents):
     │   │   ├─ Scan image for UPI QR codes
     │   │   └─ If found:
     │   │       ├─ Extract payment intent: "upi://pay?pa=scammer@bank&am=1000&tn=rent"
     │   │       ├─ Add to metadata['qr_payments']
     │   │       └─ Enhance OCR text with parsed QR info
     │   │   └─ If not found: continue
     │   │
     │   ├─ OCR Extraction (ocr.py:OCRAdapter.extract):
     │   │   ├─ Check if OCR thread is available (lock.acquire(blocking=False))
     │   │   │
     │   │   ├─ If available:
     │   │   │   ├─ Load EasyOCR English model (if not loaded)
     │   │   │   │   └─ From: .cache/easyocr/ (or OCR_MODEL_DIR)
     │   │   │   │
     │   │   │   ├─ Run OCR on numpy array:
     │   │   │   │   ├─ Extract text with confidence scores
     │   │   │   │   ├─ Filter text with confidence ≥ 0.3
     │   │   │   │   ├─ Join lines with newlines
     │   │   │   │   └─ Return extracted text
     │   │   │   │
     │   │   │   └─ Result: text = "Hi, your account needs verification...", notice = None
     │   │   │
     │   │   └─ If NOT available (OCR locked):
     │   │       └─ Return: text = "", notice = "ocr_unavailable"
     │   │           └─ User will see: "OCR unavailable; enter text manually"
     │   │
     │   ├─ Safety Analysis (safety.py:request_markers):
     │   │   ├─ Scan OCR text for social engineering patterns:
     │   │   │   ├─ "urgent language": matches urgency keywords
     │   │   │   ├─ "credential request": matches PIN, OTP, password
     │   │   │   ├─ "payment redirect": matches "new bank" patterns
     │   │   │   ├─ "verification demand": matches "verify" keywords
     │   │   │   ├─ "qr_payment": detected from QR code
     │   │   │   └─ "link request": matches "click link" patterns
     │   │   │
     │   │   └─ Return: markers = ["urgent_language", "credential_request"]
     │   │
     │   ├─ Add markers to metadata:
     │   │   └─ metadata['request_markers'] = ["urgent_language", "credential_request"]
     │   │
     │   ├─ Redact credentials (redaction.py:redact):
     │   │   ├─ Scan text for PII patterns:
     │   │   │   ├─ Phone numbers: "8765432109" → "[PHONE REDACTED]"
     │   │   │   ├─ Email addresses: "user@example.com" → "[EMAIL REDACTED]"
     │   │   │   ├─ UPI IDs: "user@bank" → "[UPI REDACTED]"
     │   │   │   ├─ Account numbers: "123456789" → "[ACCOUNT REDACTED]"
     │   │   │   └─ OTP/PIN patterns: "123456" → "[OTP REDACTED]"
     │   │   │
     │   │   └─ Return: redacted_text
     │   │
     │   ├─ Truncate text to 10,000 chars max
     │   │
     │   └─ Return:
     │       {
     │         text: "[redacted OCR text]",
     │         metadata: {
     │           content_type: "image/png",
     │           width: 1080,
     │           height: 1920,
     │           size_bytes: 2621440,
     │           qr_payments: [],
     │           request_markers: ["urgent_language", "credential_request"]
     │         },
     │         notice: None  (or 'ocr_unavailable' / 'unreadable')
     │       }
     │
     ├─ Store evidence in database (investigation_store.py:add_evidence):
     │   ├─ Generate UUID for evidence
     │   ├─ INSERT INTO evidence:
     │   │   {
     │   │     id: "abc-123-evidence",
     │   │     investigation_id: case_id,
     │   │     type: "screenshot",
     │   │     review_state: "needs_review",
     │   │     ocr_text: "[redacted OCR text]",
     │   │     confirmed_text: NULL,
     │   │     metadata: { content_type, width, height, qr_payments, request_markers },
     │   │     notice: NULL,
     │   │     created_at: now(),
     │   │     updated_at: now()
     │   │   }
     │   │
     │   └─ Return: { evidence: {...}, input_revision: 1 }
     │
     └─ Return HTTP 201 + EvidenceResult
        {
          evidence: {
            id: "abc-123-evidence",
            type: "screenshot",
            review_state: "needs_review",
            ocr_text: "[redacted text from image]",
            confirmed_text: NULL,
            metadata: { ... },
            notice: NULL,
            created_at: "2024-11-14T15:00:00Z",
            updated_at: "2024-11-14T15:00:00Z"
          },
          input_revision: 1
        }

Frontend:
  └─ onSuccess:
     ├─ Hide upload progress
     ├─ Add new evidence to local data.evidence array
     ├─ Show toast: "Screenshot uploaded & OCR processed"
     └─ Display evidence in "EXISTING EVIDENCE" section

Result: Evidence appears in UI with OCR text, awaiting user confirmation
```

---

#### 🔘 Button: "Confirm" (on OCR Text)
**User Clicks**: After reviewing OCR text from screenshot
```
Frontend (investigation.tsx:confirm function):
  └─ onClick → confirm()
     ├─ Optional: User may edit OCR text in textarea
     │   └─ If edited: confirmed_text = edited_text
     │   └─ If not edited: confirmed_text = ocr_text
     │
     ├─ PATCH /api/v1/investigations/{case_id}/evidence/{evidence_id}
     │   Body: {
     │     text: "[user-approved OCR text or edited text]",
     │     confirmed: true,
     │     expected_revision: 1
     │   }

Backend API Call: PATCH /api/v1/investigations/{case_id}/evidence/{evidence_id}
  └─ investigations.py:confirm()
     ├─ Extract owner from cookie
     ├─ Validate case ownership
     ├─ Check expected_revision (optimistic lock)
     │   └─ If stale: return HTTP 409
     │
     ├─ Validate evidence exists:
     │   └─ SELECT * FROM evidence WHERE id = ? AND investigation_id = ?
     │
     ├─ Update evidence:
     │   ├─ If text changed OR review_state != 'confirmed':
     │   │   ├─ Re-detect request_markers from new text
     │   │   ├─ UPDATE evidence SET
     │   │   │   ├─ confirmed_text = user_text,
     │   │   │   ├─ review_state = 'confirmed',
     │   │   │   ├─ notice = NULL,
     │   │   │   ├─ metadata.request_markers = newly_detected_markers,
     │   │   │   └─ updated_at = now()
     │   │   │
     │   │   └─ Increment input_revision:
     │   │       ├─ UPDATE investigations SET
     │   │       │   ├─ input_revision = input_revision + 1
     │   │       │   ├─ (This triggers re-analysis in supervisor)
     │   │       │   └─ updated_at = now()
     │   │       │
     │   │       └─ Record audit event:
     │   │           └─ INSERT INTO audit_log
     │   │               (action: 'evidence_updated', evidence_id, ...)
     │   │
     │   └─ If no change: Return current revision (no-op)
     │
     └─ Return: { evidence: {...}, input_revision: 2 }

Frontend:
  └─ onSuccess:
     ├─ Update evidence with confirmed_text
     ├─ Mark review_state as 'confirmed'
     ├─ Update input_revision locally
     ├─ Show toast: "Evidence confirmed"
     └─ Auto-submit for analysis:
        └─ POST /api/v1/investigations/{case_id}/analyze
           (See Analysis section below)

Result: Evidence locked, re-analysis triggered automatically
```

---

## 5️⃣ SCREEN: Investigation Workspace - Evidence Tab (After Confirmation)

### What User Sees:
```
┌──────────────────────────────────────────────────────────────────┐
│  📱 Byte Bot Investigation Workspace                             │
│  ════════════════════════════════════════════════════════════    │
│                                                                  │
│  [Context] [Evidence] [Analysis] [Results]                       │
│                      ↑ ACTIVE TAB                                │
│                                                                  │
│  ──────────────────────────────────────────────────────────     │
│  EXISTING EVIDENCE:                                              │
│                                                                  │
│  📸 Screenshot [CONFIRMED]                                       │
│     "Hi, your account needs verification..."                    │
│     ⚠️ Urgent language detected                                  │
│     ⚠️ Credential request detected                               │
│     [💬 Show full text] [✏️ Edit] [🗑️ Delete]                   │
│                                                                  │
│  ──────────────────────────────────────────────────────────     │
│  Analyzing... [spinner]                                         │
│  "Supervisor is processing your evidence..."                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

