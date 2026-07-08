# Quick local launcher for Windows PowerShell.
# Run once:  .\run_local.ps1

# Create and activate a virtual environment
# (uses the "py" launcher because bare "python" hits the Windows Store stub)
if (-not (Test-Path ".venv")) {
    py -m venv .venv
}
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Make sure you've copied .env.example to .env and filled it in!
if (-not (Test-Path ".env")) {
    Write-Host "WARNING: no .env file found. Copy .env.example to .env and fill it in." -ForegroundColor Yellow
}

# Start the server with auto-reload
uvicorn app.main:app --reload --port 8000
