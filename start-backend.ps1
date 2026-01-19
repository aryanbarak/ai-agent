# Start AI Agent Backend
$ErrorActionPreference = "Stop"

# Change to project directory
Set-Location "c:\Projects\AI Agent"

# Activate virtual environment
& ".\venv\Scripts\Activate.ps1"

# Load environment variables from .env
if (Test-Path .env) {
    Get-Content .env | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1]
            $value = $matches[2]
            [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
            Write-Host "Loaded: $key"
        }
    }
}

# Start uvicorn
Write-Host "`n✅ Starting AI Agent Backend on http://127.0.0.1:8000`n" -ForegroundColor Green
python -m uvicorn agent.api:app --reload --port 8000 --host 127.0.0.1
