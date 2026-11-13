# Synthetic demo walkthrough

Complete [setup](setup.md), start the API with explicit `BYTEBOT_EXTRACTION_MODE=fixture`, and open **http://127.0.0.1:5174**. A text-only demo does not need OCR or Gemini credentials. All intelligence and payments are synthetic.

## Scenarios

| Scenario | Evidence | Expected category |
| --- | --- | --- |
| A | Different-ID repayment request with urgency | Needs verification |
| B | Same-ID repayment pressure, threat, and bank avoidance | High concern |
| C | Same-ID polite repayment request | Needs verification |
| D | Expected payment from a known contact, no evidence | No strong indicators found |
| E | Unexpected collect approval request | High concern |

Select A–E on history and choose **Load / reopen scenario**. First loading saves the synthetic answers and message; D has no evidence. Choose **Ask Byte Bot**, review the saved inputs, and analyze. The five cases use distinct transactions and can coexist. Reopening preserves edits, evidence, results, reports, and case status. It does not refill an existing case; reset before replaying original inputs.

Choose **Enter evidence manually** before a scenario's first load to save answers without evidence. Paste the catalog message or use the screenshot walkthrough. Fixture extraction requires exact canonical confirmed text; arbitrary/edited evidence receives an extraction-unavailable limitation and supported local fallback. Gemini mode never silently substitutes fixtures. Pending and failed transactions produce Unable to assess, with independent supported warnings preserved.

## Screenshot walkthrough

Install [optional OCR](setup.md#optional-local-ocr) and prepare its models. From the repository root:

```bash
.venv/bin/python backend/tests/synthetic_images.py --scenario B --output .cache/phase05/scenario-b.png
```

PowerShell:

```powershell
.\.venv\Scripts\python.exe backend/tests/synthetic_images.py --scenario B --output .cache/phase05/scenario-b.png
```

1. Reset from history. Select **B. Same-ID repayment pressure**, check **Enter evidence manually**, and load.
2. Choose **Ask Byte Bot** and review the attached transaction facts and saved answers.
3. Upload the synthetic PNG, review/correct its OCR text, and confirm it. For exact fixture matching, correct line breaks and recognition errors to: `Please return INR 5000 to aarav.demo@upi. I will call the police. Do not contact your bank.`
4. Analyze and show **High concern**, with threat/bank-avoidance findings and the same-ID limitation. Findings are signals requiring verification, not proof of fraud.
5. Generate/download the report, reopen it through **My Incidents**, and save **Bank Contacted** as a user-entered status.

This is the four-minute presentation sequence. Automated historical rehearsal times exclude human narration and measure fixtures, not live Gemini. See [progress](progress.md) for the recorded environment and timings.

## Reset

**Reset demo** on history asks for confirmation, then clears only the current session's cases, evidence, analysis, reports, and audits and restores eight synthetic transactions. It keeps the cookie and creates new resource IDs. Other sessions remain intact; old case/report URLs become unavailable. Pending OCR/provider work cannot repopulate deleted data. Previously downloaded reports remain on the user's device.

For API use, create a separate cookie jar. This resets that API session, not an existing browser session:

```bash
mkdir -p .cache
curl --fail --silent --cookie-jar .cache/demo.cookies http://127.0.0.1:8000/api/v1/transactions
curl --fail --silent --cookie .cache/demo.cookies --request POST http://127.0.0.1:8000/api/v1/demo/reset
```

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/transactions -SessionVariable demoSession
Invoke-RestMethod http://127.0.0.1:8000/api/v1/demo/reset -Method Post -WebSession $demoSession
```

Do not publish cookie jars or generated evidence/reports. `.cache/` is ignored. For complete regression commands and keyboard/mobile coverage, see [testing](testing.md#browser-acceptance).
