# Synthetic demo walkthrough

Complete [setup](setup.md), start the API with explicit `BYTEBOT_EXTRACTION_MODE=fixture`, and open **http://127.0.0.1:5174**. A text-only demo does not need OCR or Gemini credentials. All intelligence and payments are synthetic.

## Four-minute presentation

Reset the demo before the timer starts. Use the default **Scenario B** and leave the manual evidence checkbox clear.

1. **0:00–0:45** “An unexpected ₹5,000 credit arrives. A stranger asks you to return it to the same UPI ID and tells you to stay away from your bank.” Load the scenario and tap **Ask Byte Bot**. Point to the attached payment and the submitted message.
2. **0:45–1:30** Show the saved inputs and choose **Analyze & prepare report**. “This is the customer’s approval to analyze the reviewed inputs and prepare a private report.” The **Workflow** view shows the actual stages, or their completed state when the fixture finishes between polls.
3. **1:30–2:45** Open **Findings** and show **High concern**. Point to the matching destination, the threat, and the request to avoid the bank. “The destination matches the original sender. That leaves the risk unchanged. The pressure and isolation are why I’d verify the original credit through official bank channels.”
4. **2:45–4:00** Choose **Download report** from the result, then save **Bank Contacted** as the customer’s own update. Show **Outcome**, open **My Incidents**, and reopen the report. “One approval gave the customer an assessment and a report they can take to support. They decide whether to share it and report any follow-up they’ve taken.”

If live services are unavailable, play the local `.cache/paytm-upgrade/scenario-b-fallback.webm` recording. It is a silent, synthetic walkthrough. Use the same narration landmarks and cite the recorded fixture measurements in [progress](progress.md).

### Judge Q&A

- **Why does the same UPI ID still warrant concern?** A matching destination leaves the risk unchanged. Scenario B includes a threat and a request to bypass the bank. The polite same-ID request in Scenario C comes back **Needs verification**. Use C as an optional comparison after the main walkthrough.
- **What does Gemini do?** When configured, it extracts structured claims from confirmed, redacted evidence. Byte Bot checks that each claim is supported by the cited evidence. Python rules assign the category and LangGraph coordinates the investigation. The judges’ run uses deterministic extraction fixtures.
- **What does the customer control?** The customer approves the inputs and private report, decides whether to download or share it, and records their own follow-up. The report carries transaction facts, redacted evidence, provenance, and limitations that a human reviewer can inspect.
- **What has been measured?** The fixture runs measure customer actions, time until the decision and report are ready, successful download, and follow-up save. A pilot could measure assisted completion before repayment, support handling time, and precision against human-reviewed outcomes.

The screenshot walkthrough below is an alternate. Use the right-hand presenter controls in the presentation or the history controls in the standard workspace at **http://127.0.0.1:5174/workspace**.

## Scenarios

| Scenario | Evidence | Expected category |
| --- | --- | --- |
| A | Different-ID repayment request with urgency | Needs verification |
| B | Same-ID repayment pressure, threat, and bank avoidance | High concern |
| C | Same-ID polite repayment request | Needs verification |
| D | Expected payment from a known contact, no evidence | No strong indicators found |
| E | Unexpected collect approval request | High concern |

Select A–E in the demo controls and choose **Load / reopen scenario**. First loading saves the synthetic answers and message. D has no evidence. Choose **Ask Byte Bot**, review the saved inputs, and analyze. The five cases use distinct transactions and can coexist. Reopening preserves edits, evidence, results, reports, and case status. Reset before replaying the original inputs.

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
5. Download the report prepared by the phone. In the standard workspace, use the separate **Generate / view report** action. Save **Bank Contacted** as a user-entered status and reopen the report through **My Incidents**.

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
