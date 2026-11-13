# Phase 02 Guided investigation

## Prerequisites

Phase 01 passes. Read PRD FR-02 through FR-06, [evidence lifecycle](../architecture.md#storage-and-evidence), and [AT-07 and AT-10](../acceptance.md#prd-acceptance-cases). Install optional OCR dependencies in the project virtual environment before the real OCR smoke test.

```text
python -m pip install -r backend/requirements-ocr.txt
```

Use CPU-compatible PyTorch and torchvision builds for the host. Initialize EasyOCR in CPU mode with English recognition and the configured `OCR_MODEL_DIR`. Cache models before the demo. Keep OCR initialization lazy so paste and call summaries remain available if setup fails.

## Implementation order

1. Add migrations and typed schemas for investigations, context, and evidence. **Ask Byte Bot** creates or reopens the session's case for the selected transaction. Read transaction facts server-side and keep the original transaction visible during intake.
2. Build a guided form for expected payment, sender familiarity, repayment request, contact channels, destination, pressure tactics, and whether the user already sent money. Keep unknown answers distinct from negative ones. Save progress and restore it on reload.
3. Accept pasted text and typed call summaries as user evidence. Redact credential values before any write. For images, validate content, cap uploads at 5 MiB and decoded images at 16 megapixels, and process image bytes transiently.
4. Return redacted OCR text for review. Show a browser-local image preview and allow editing, confirmation, replacement through a new upload, and removal. If the image cannot be read, keep the case usable and offer manual text entry. An unreviewed image is never analysis input.
5. Implement revision updates for changes to context and evidence. Add ownership checks and tests for each new endpoint.

## Expected files and contracts

- Investigation, context, and evidence migration, schemas, and routes.
- Redaction and EasyOCR adapters with injectable test doubles.
- Guided investigation and evidence review components with accessible labels, status messages, and keyboard-operable controls.
- Use the [Phase 02 API contract](../architecture.md#rest-interface) for JSON text submission, multipart screenshot upload, confirmation, and removal.

## Verification and exit checklist

Run `python -m pytest backend/tests` in the project virtual environment and `npm --prefix frontend run build`. In the browser, open the same investigation after reload and exercise each evidence method.

- [x] The transaction stays attached and saved answers restore on reload.
- [x] Pasted text, a typed call summary, and a valid screenshot can be submitted and removed.
- [x] OCR text can be edited and confirmed. An unreadable image offers manual entry.
- [x] Oversized, mislabeled, or unsupported uploads are rejected. Raw images and credential values are absent from durable storage and logs.
- [x] A second session cannot read, edit, confirm, or remove another session's evidence.
- [x] Record AT-07, relevant AT-10 checks, and real OCR verification status in [progress](../progress.md).

Completed 2026-11-13. See the dated [progress entry](../progress.md#2026-11-13--phase-02-guided-investigation-complete) for commands, AT-07/AT-10 coverage, real OCR timing, and browser artifacts.
