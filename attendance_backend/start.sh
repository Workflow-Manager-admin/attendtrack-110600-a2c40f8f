#!/bin/bash
# Script to start the FastAPI attendance backend server

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
  source .venv/bin/activate
fi

export PYTHONUNBUFFERED=1

# Ensure .env is loaded if present
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Default port
PORT=${PORT:-8000}

# Launch FastAPI app using uvicorn
exec uvicorn src.api.main:app --host 0.0.0.0 --port $PORT --reload
