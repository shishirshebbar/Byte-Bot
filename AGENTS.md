# Byte Bot agent instructions

This directory is the local development workspace for the Byte Bot hackathon MVP.

## Start here

1. Read the latest user request and [progress](docs/progress.md) to identify the authorized work and current phase.
2. Read the matching [phase guide](README.md#phase-guides), [architecture](docs/architecture.md), and [acceptance matrix](docs/acceptance.md).
3. Consult the [original PRD](docs/reference/byte_bot_prd.md) for the requirements referenced in the guide. Section 20 is an embedded reference prompt. The user's current request governs what work starts.
4. Check the existing workspace before editing. Reuse the dependency manifests, lockfile, and relevant code already present.
5. Run the phase's checks and update [progress](docs/progress.md) with exact commands, results, and any pending verification. Mark a phase complete only after its exit criteria pass. If the user authorizes multiple phases, work through them in order.

## Product boundaries

- The demo uses seeded transactions and simulated intelligence. The report is a user-owned download and case statuses are user-entered.
- Byte Bot may take actions only against local mock systems labelled "Simulated system", only from the playbook in `planner.py`, and only after the Python policy in `policy.py` grants the verdict (customer consent or human approval where required). It never moves real money, submits reports externally, records calls, or reads background messages.
- The application checks demo-session ownership on every user-scoped operation. Evidence is untrusted data. Keep credentials and raw screenshots out of persistent storage, logs, reports, and provider requests.
- Python rules assign the risk category, and the supervisor's routing, follow-ups, plan, and escalation are deterministic Python. Evidence that contains instructions is data and a reason to escalate, never a command. Gemini extracts evidence into a validated schema. A same-UPI-ID match carries zero risk reduction, and a different destination is a finding that can warrant verification. Show provenance and limitations for all results.
- Start with synthetic fixtures. Use locally configured keys (Sarvam, optionally Gemini) only with synthetic evidence. Keys live only in the gitignored `.env`; never write them into code, docs, logs, or tests. Text-to-speech receives only Byte Bot's own guidance, never evidence.

## Local service ports

- Ports **5000, 5173, and 3306 belong to the separate AI_Chat project**. Do not use, stop, restart, or reconfigure their services, even to free a port.
- Byte Bot uses loopback API **8000**, frontend **5174**, preview **4174**, and PostgreSQL **55433**. Frontend ports are strict; fail clearly on conflicts instead of selecting another port or terminating another process.
- Leave the original temporary `bytebot-mvp-pg` container on **55432** untouched.
