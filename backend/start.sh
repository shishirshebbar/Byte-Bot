#!/bin/bash
set -e

echo "Installing Python dependencies..."
python -m pip install -r backend/requirements.txt

echo "Running database migrations..."
cd backend
python -m bytebot.cli migrate
python -m bytebot.cli seed
cd ..

echo "Starting Byte Bot API server..."
python -m uvicorn bytebot.main:app --host 0.0.0.0 --port $PORT --no-access-log
