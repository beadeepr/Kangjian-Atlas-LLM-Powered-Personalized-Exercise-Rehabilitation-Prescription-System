$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$env:APP_ENV = if ($env:APP_ENV) { $env:APP_ENV } else { "production" }
$env:PORT = if ($env:PORT) { $env:PORT } else { "8000" }

.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port $env:PORT
