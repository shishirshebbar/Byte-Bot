# Local setup

Use Python 3.12, Node 22 with npm, and Docker with the Compose plugin. Version hints are in `.python-version` and `.node-version`. Commands start at the repository root unless stated otherwise. On Windows/macOS, start Docker Desktop first.

## Install dependencies

For a fresh checkout:

```bash
git clone https://github.com/krishnacsn/byte.git
cd byte
cp .env.example .env
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
docker compose config --quiet
```

Windows PowerShell:

```powershell
git clone https://github.com/krishnacsn/byte.git
Set-Location byte
Copy-Item .env.example .env
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
docker compose config --quiet
```

Copy the environment example only for a new installation; preserve an existing `.env` and merge missing settings manually. Never commit it.

| Manifest | Installs |
| --- | --- |
| `backend/requirements.txt` | Runtime dependencies |
| `backend/requirements-dev.txt` | Runtime plus pytest, HTTP client, and Playwright tooling |
| `backend/requirements-ocr.txt` | Optional EasyOCR and pinned PyTorch/torchvision; install alongside runtime or development dependencies |
| `frontend/package-lock.json` | Locked npm dependency tree, installed with `npm ci` |

Use runtime requirements instead of development requirements when test tools are unnecessary. Python direct dependencies are pinned, but transitive dependencies are not fully locked. Do not replace the manifests with a freeze of an unrelated environment.

If Python 3.12 is unavailable and `uv` is installed, use `uv python install 3.12`, `uv venv --python 3.12 --seed .venv`, and `uv pip install --python .venv/bin/python -r backend/requirements-dev.txt`.

## Environment variables

The API and CLI load the root `.env`; existing shell variables take precedence. Compose also reads the root `.env`. Vite and browser scripts require their optional overrides in the launching shell.

| Variable | Default / example | Purpose |
| --- | --- | --- |
| `BYTEBOT_DB_PORT` | `55433` | Compose host port; PostgreSQL stays on 5432 inside the container |
| `DATABASE_URL` | No code default; example points to `127.0.0.1:55433/bytebot` | Required demo database connection |
| `TEST_DATABASE_URL` | No code default; example points to `127.0.0.1:55433/bytebot_test` | Separate database required for integration tests |
| `COOKIE_SECURE` | `false` | Use `true` when serving through HTTPS; keep false for loopback HTTP |
| `BYTEBOT_EXTRACTION_MODE` | `gemini` | `fixture` explicitly enables deterministic synthetic extraction |
| `GEMINI_API_KEY` | Empty | Optional server-side Gemini credential |
| `GEMINI_MODEL` | Empty | Optional Gemini model identifier; required with the key for live extraction |
| `OCR_MODEL_DIR` | `.cache/easyocr` | OCR cache, resolved relative to the repository root unless absolute |
| `BYTEBOT_API_TARGET` | `http://127.0.0.1:8000` | Vite development/preview API proxy target; shell variable |
| `BYTEBOT_WEB_URL` | `http://127.0.0.1:5174` | Browser acceptance target; shell variable |

Example database credentials are `bytebot` / `bytebot` for loopback development only. Keep Gemini settings blank unless explicitly configuring the optional live integration.

## Database and migrations

```text
docker compose up -d --wait db
docker compose ps
docker compose exec -T db createdb -U bytebot bytebot_test
```

Create `bytebot_test` once; if it already exists, reuse it. Compose creates the demo database `bytebot` automatically on a fresh volume. Changing Compose credentials later does not modify an already-initialized volume.

Linux/macOS, backend terminal:

```bash
cd backend
../.venv/bin/python -m bytebot.cli migrate
../.venv/bin/python -m bytebot.cli seed
```

PowerShell, backend terminal:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m bytebot.cli migrate
..\.venv\Scripts\python.exe -m bytebot.cli seed
```

Migrations are explicit, versioned, checksum-checked, serialized, and transactional. Seeds insert missing synthetic templates without overwriting existing session data. For repeatability verification, see [testing](testing.md#migrations-and-seeds).

## Start the applications

In the backend terminal above, start the deterministic demo:

```bash
BYTEBOT_EXTRACTION_MODE=fixture ../.venv/bin/python -m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

PowerShell:

```powershell
$env:BYTEBOT_EXTRACTION_MODE = 'fixture'
..\.venv\Scripts\python.exe -m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal at the repository root:

```text
npm --prefix frontend run dev
```

Open **http://127.0.0.1:5174**. `http://127.0.0.1:8000/api/v1/health` probes database readiness without creating a demo session. Use the frontend address consistently so its cookie owns the same session on subsequent requests.

The API uses port 8000, Vite uses strict port 5174, preview uses strict port 4174, and PostgreSQL uses 55433, all on loopback. Ports **5000, 5173, and 3306** belong to another project. Do not interrupt them or the temporary `bytebot-mvp-pg` container on **55432**. On a conflict, select a free port explicitly. Database port changes require matching `BYTEBOT_DB_PORT`, `DATABASE_URL`, and `TEST_DATABASE_URL`; API port changes require matching `--port` and the frontend shell's `BYTEBOT_API_TARGET`. A frontend port change requires the explicit Vite `--port` option and matching `BYTEBOT_WEB_URL` for tests.

For a local production-bundle check, run `npm --prefix frontend run build` then `npm --prefix frontend run preview`. Preview is a local verification server, not a production deployment configuration.

## Optional local OCR

Paste and call-summary intake work without OCR installed. Missing models or an unavailable reader offer manual entry. Screenshot review/confirmation is always required.

On the verified Linux/Python 3.12 setup, install CPU wheels before optional OCR dependencies:

```bash
.venv/bin/python -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r backend/requirements-ocr.txt
cd backend
../.venv/bin/python -m bytebot.cli ocr-prepare
```

PowerShell equivalent:

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-ocr.txt
Set-Location backend
..\.venv\Scripts\python.exe -m bytebot.cli ocr-prepare
```

On macOS, install the OCR requirements with the normal package index instead of the Linux/Windows CPU wheel command; the adapter still uses CPU mode. Host-specific OCR installation must be verified locally; recorded OCR acceptance was on Linux.

Preparation downloads English recognition and CRAFT detection weights to the ignored cache. Requests initialize lazily with downloads disabled. No raw screenshot is stored by the server. Restart only your Byte Bot API after dependency/settings changes. See [OCR verification](testing.md#real-ocr) and the [screenshot demo](demo.md#screenshot-walkthrough).

## Optional Gemini extraction

Configure both `GEMINI_API_KEY` and `GEMINI_MODEL` locally. Stop your fixture API before starting a replacement on the same port. From `backend/`, launch without a fixture override:

```bash
BYTEBOT_EXTRACTION_MODE=gemini ../.venv/bin/python -m uvicorn bytebot.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

PowerShell uses `$env:BYTEBOT_EXTRACTION_MODE = 'gemini'` before the equivalent Python command. Missing configuration, timeouts, or invalid extraction preserve the case and show a limitation with supported local fallback. Gemini extracts evidence; Python determines the category. It never silently substitutes fixture extraction. Live verification is separate from deterministic acceptance; see [the provider check](testing.md#optional-live-gemini).

## Troubleshooting and stopping

- Database readiness failure: check Docker, `docker compose ps`, and that all three database settings use the same port. Do not delete a volume to resolve a connection error.
- Empty history or scenario-unavailable notice: confirm migrations and seeds ran against `DATABASE_URL`.
- Missing browser executable: run the Playwright Chromium installation in [testing](testing.md#browser-acceptance).
- Fixture extraction unavailable: confirm saved evidence exactly matches the synthetic catalog text; correct OCR line breaks and recognition errors before confirming it.
- A Secure cookie on plain HTTP may prevent session continuity; use `COOKIE_SECURE=false` for local HTTP.

Stop your own API/Vite terminal with Ctrl+C. `docker compose stop db` preserves the database volume. **Reset demo** clears only the current browser session's cases and restores its eight transactions; see [demo reset](demo.md#reset). Avoid `docker compose down -v` unless you deliberately intend to delete all local Byte Bot database data.
