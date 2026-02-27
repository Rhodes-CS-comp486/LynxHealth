# Start script for Windows PowerShell
# Activates the Python virtual environment and launches the backend server.

# Path to the virtual environment activation script
$venvPath = ".\.venv\Scripts\Activate.ps1"

if (Test-Path $venvPath) {
    Write-Host "Activating virtual environment..."
    & $venvPath
} else {
    Write-Warning "Virtual environment not found at $venvPath"
}

# start frontend in separate process
if (Test-Path "frontend\package.json") {
    Write-Host "Starting frontend (npm)..."
    Start-Process -NoNewWindow -WorkingDirectory "frontend" cmd.exe -ArgumentList "/c","npm run start"
} else {
    Write-Warning "Frontend directory not found, skipping npm start."
}

# Launch the FastAPI application with uvicorn
Write-Host "Starting FastAPI server..."
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
