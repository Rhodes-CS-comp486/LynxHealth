#!/usr/bin/env bash
# Start script for Unix-like systems.
# Activates the Python virtual environment and launches the backend server.

VENV_PATH=".venv/bin/activate"
if [ -f "$VENV_PATH" ]; then
    echo "Activating virtual environment..."
    # shellcheck source=/dev/null
    source "$VENV_PATH"
else
    echo "Warning: virtual environment not found at $VENV_PATH" >&2
fi

# start frontend if available
if [ -f "frontend/package.json" ]; then
    echo "Starting frontend (npm)..."
    (cd frontend && npm run start) &
else
    echo "Warning: frontend directory not found, skipping npm start" >&2
fi

echo "Starting FastAPI server..."
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
