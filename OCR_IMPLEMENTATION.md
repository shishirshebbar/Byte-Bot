# OCR Implementation in Byte Bot

## Overview
Byte Bot **DOES have OCR (Optical Character Recognition)** functionality. It uses **EasyOCR** to extract text from screenshot evidence uploaded by users.

---

## Architecture

### 1. **Local CPU-Based OCR** (`backend/bytebot/ocr.py`)
- **No external API calls** – OCR runs locally on CPU
- **In-memory processing** – Images decoded but never written to disk
- **EasyOCR** – English text extraction with confidence filtering (0.3+ threshold)
- **Non-blocking** – If OCR is busy, returns fallback notice instead of blocking

**Key Class: `OCRAdapter`**
```python
class OCRAdapter:
    def extract(self, image) -> tuple[str, notice]:
        # Thread-locked to prevent concurrent OCR crashes
        # Returns (extracted_text, notice_code)
        # Notice codes: None (success), 'ocr_unavailable', 'unreadable'
```

### 2. **Image Validation** (`ocr.py:decode_image`)
- **File limit**: 5 MiB max
- **Pixel limit**: 16 megapixels max (to prevent decompression bombs)
- **Format**: PNG or JPEG only; static images (no animated GIFs)
- **Error handling**: Returns structured errors with status codes (413, 415, 422)

### 3. **QR Code Detection** (`backend/bytebot/qr.py`)
- Integrated into screenshot processing
- Extracts UPI payment intents from QR codes
- Adds `qr_payments` to metadata if found
- Enhances OCR text with parsed QR payment details

---

## Request Flow: Screenshot Upload

### Step 1: User Uploads Screenshot
**Endpoint**: `POST /api/v1/investigations/{case_id}/evidence`
- Content-Type: `multipart/form-data`
- Two fields required:
  - `file`: PNG/JPEG image (max 5 MiB)
  - `expected_revision`: Optimistic lock value (integer)

### Step 2: Upload Parsing (`uploads.py:screenshot_body`)
- Multipart parsing with **no temp files** (all in-memory bytearrays)
- Validates boundary, extracts image + revision
- Enforces `BODY_LIMIT = 6 MiB` total request size

### Step 3: Image Decoding (`ocr.py:decode_image`)
- Decodes PNG/JPEG to RGB in memory via PIL
- Validates format, dimensions, pixel count
- Catches decompression bombs and format mismatches
- Returns PIL Image object + metadata dict

### Step 4: OCR + QR Processing (`investigations.py:process_image`)
```
Image → QR Code Detection → OCR Extraction → Request Marker Detection
  ↓
  Combines results: OCR text + QR payments + safety markers
  ↓
  Redacts credentials (PII cleanup)
  ↓
  Stores as 'screenshot' evidence
```

**Outputs**:
- `text`: Extracted OCR text (redacted, max 10,000 chars)
- `metadata`: 
  - `content_type`: 'image/png' or 'image/jpeg'
  - `width`, `height`: Image dimensions
  - `size_bytes`: File size
  - `qr_payments`: Parsed UPI intents (if QR detected)
  - `request_markers`: Suspected social engineering indicators
- `notice`: Status code
  - `None`: Success
  - `'ocr_unavailable'`: OCR locked/unavailable
  - `'unreadable'`: OCR returned empty text

### Step 5: Store Evidence (`investigation_store.py:add_evidence`)
Inserted into `evidence` table:
```sql
INSERT INTO evidence (
  id, investigation_id, type, review_state, 
  ocr_text, confirmed_text, metadata, notice, 
  created_at, updated_at
) VALUES (...)
```

**Fields**:
- `type = 'screenshot'` (also: 'message', 'call_summary', 'voice_note')
- `review_state = 'needs_review'` (user must confirm OCR)
- `ocr_text`: Raw OCR output
- `confirmed_text`: NULL initially (user confirms/edits)
- `metadata`: JSON blob with extraction results
- `notice`: Fallback status if OCR failed

---

## User Confirmation Workflow

### Step 1: Review Extracted Text
**UI**: User sees OCR-extracted text in evidence panel
- Can edit if OCR made mistakes
- Can review QR payment details
- Safety markers highlighted (e.g., "urgent language detected")

### Step 2: Confirm Evidence
**Endpoint**: `PATCH /api/v1/investigations/{case_id}/evidence/{evidence_id}`
```json
{
  "text": "Confirmed text (possibly edited)",
  "confirmed": true,
  "expected_revision": 42
}
```

**Logic** (`investigations.py:confirm`):
- Updates `confirmed_text`
- Changes `review_state` from 'needs_review' → 'confirmed'
- If user edited, updates `request_markers` (redetected)
- Increments case `input_revision` (triggers re-analysis)
- Records audit event

### Step 3: Re-analysis
Once evidence confirmed:
1. Supervisor node **Message Analysis** reprocesses the case
2. Risk assessment runs with confirmed text
3. New `risk_factors`, `risk_score`, and `category` generated

---

## Evidence Schema

```python
class Evidence(BaseModel):
    id: UUID
    type: Literal['message', 'call_summary', 'screenshot', 'voice_note']
    review_state: Literal['needs_review', 'ocr_failed', 'confirmed']
    ocr_text: str | None           # Raw OCR output
    confirmed_text: str | None     # User-confirmed text
    metadata: dict                 # QR codes, safety markers, image dimensions
    notice: Literal['ocr_unavailable', 'unreadable'] | None
    created_at: datetime
    updated_at: datetime
```

---

## Error Handling

| Status | Code | Meaning | Action |
|--------|------|---------|--------|
| 413 | `evidence_too_large` | File > 5 MiB or > 16 MP | Show upload size error |
| 415 | `unsupported_image` | Not PNG/JPEG, animated, or format mismatch | Reject file type |
| 422 | `invalid_image` | Corrupted image data | Ask user to re-upload |
| 422 | `invalid_upload` | Missing `file` or `expected_revision` field | Check form submission |

---

## OCR Models & Dependencies

**File**: `backend/requirements-ocr.txt`
```
easyocr==1.7.2
torch==2.6.0
torchvision==0.21.0
```

**Model Directory**:
- Cached at `.cache/easyocr/` (configurable via `OCR_MODEL_DIR` env var)
- Downloaded on first run via `bytebot cli ocr-prepare`
- English (en) model only; non-English text ignored

**CPU/GPU**:
- Runs on CPU only (`gpu=False`)
- No GPU wheels required
- ~500ms–2s per image (depends on image size & complexity)

---

## Testing

**Test Files**:
- `backend/tests/ocr_smoke.py` – Runs OCR against synthetic images
  - Tests legible and unreadable screenshots
  - Validates confidence scoring
  - Measures performance
  
- `backend/tests/browser_phase02.py` – End-to-end screenshot upload test
  - User uploads screenshot via UI
  - Verifies OCR text appears
  - User confirms text
  - Checks re-analysis triggered

**Run OCR Tests**:
```powershell
# Smoke test (local CPU OCR only)
.\.venv\Scripts\python.exe backend/tests/ocr_smoke.py

# Browser test (full workflow)
$env:BYTEBOT_WEB_URL='http://127.0.0.1:5174'
.\.venv\Scripts\python.exe backend/tests/browser_phase02.py
```

---

## Safety & Redaction

**Credential Redaction** (`redaction.py`):
- Removes PII patterns before any persistence
- Cleans: phone numbers, emails, account numbers, UPI IDs, OTPs
- Keeps labels (e.g., "Phone number [REDACTED]")
- Applied **before** OCR text stored in database
- Safe to share OCR results with Gemini/Sarvam

**Request Marker Detection** (`safety.py:request_markers`):
- Scans text for social engineering language
- Markers: "urgent", "verify account", "confirm credentials", "click link", etc.
- Stored in evidence metadata
- Flagged in UI as safety concerns

**Image Security**:
- Images never written to disk
- Decoded in memory only
- Immediately closed after OCR
- No image URLs stored anywhere

---

## Integration Points

### 1. **Frontend** (`frontend/src/`)
- **Evidence Panel**: Shows OCR-extracted text
- **Upload Zone**: Accepts PNG/JPEG screenshots
- **Confirmation UI**: Edit + confirm workflow
- **Safety Alerts**: Highlights request markers

### 2. **Supervisor Agent** (`analysis_graph.py`)
- **Message Analysis Node**: Processes confirmed evidence
- **Input Revision Trigger**: Re-runs on evidence confirmation
- **Risk Investigation**: Uses confirmed OCR text in decision table

### 3. **Database Schema**
```sql
CREATE TABLE evidence (
  id UUID PRIMARY KEY,
  investigation_id UUID NOT NULL,
  type TEXT NOT NULL,
  review_state TEXT NOT NULL,
  ocr_text TEXT,          -- Raw OCR output
  confirmed_text TEXT,    -- User-confirmed text
  metadata JSONB,         -- QR codes, markers, image metadata
  notice TEXT,            -- Fallback status
  created_at TIMESTAMP,
  updated_at TIMESTAMP
);
```

---

## Configuration

**Environment Variables**:
- `OCR_MODEL_DIR`: Path to EasyOCR models (default: `.cache/easyocr`)
  - Set before first run to use a custom location
- `BYTEBOT_EXTRACTION_MODE=fixture`: Skips OCR, uses exact fixture text (testing)

**Lifespan Setup** (`main.py:create_app`):
```python
@contextmanager
def lifespan(app):
    app.state.ocr = OCRAdapter()  # Initialized once
    yield
    # OCR thread lock cleaned up on shutdown
```

---

## Performance Characteristics

| Component | Time | Behavior |
|-----------|------|----------|
| Image decode | ~10ms | Validates format, dimensions |
| QR detection | ~50ms | Finds UPI payment codes |
| OCR extraction | 500ms–2s | CPU-bound; depends on text density |
| Request markers | ~5ms | Simple regex scan |
| Total per screenshot | 600ms–2.1s | Parallel processing where possible |

**Lock Behavior**:
- If OCR is busy (locked by another request), fallback:
  - `notice = 'ocr_unavailable'`
  - User sees "OCR unavailable; manual entry" in UI
  - Can type text manually
  - No blocking or timeouts

---

## Summary

✅ **OCR is fully implemented** using EasyOCR (local CPU, no external APIs)  
✅ **Integrated into evidence workflow** (upload → extract → review → confirm → re-analyze)  
✅ **QR code detection** for UPI payment intents  
✅ **Safety markers** for social engineering language  
✅ **Credential redaction** before storage  
✅ **Comprehensive error handling** with user-friendly messages  
✅ **Tested** via smoke tests and browser suites  
✅ **Configurable** via environment variables  
✅ **Performant** with non-blocking fallback  

The system gracefully handles OCR failures while maintaining security and usability.
