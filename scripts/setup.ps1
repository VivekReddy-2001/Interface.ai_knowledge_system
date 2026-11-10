$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $ProjectRoot
try {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Python launcher not found. Install Python 3.11, reopen PowerShell, and retry."
    }
    & py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create a Python 3.11 virtual environment." }
    & .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
    & .\.venv\Scripts\python.exe -m pytest
    if ($LASTEXITCODE -ne 0) { throw "Smoke check failed." }
    Write-Host "Ready. Open knowledge-now.code-workspace in VS Code."
} finally {
    Pop-Location
}
