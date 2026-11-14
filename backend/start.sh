#!/bin/bash
set -e

echo "Installing Python dependencies..."
python -m pip install -r requirements.txt

echo "Running database migrations..."
python -m bytebot.cli migrate
python -m bytebot.cli seed

echo "Starting Byte Bot API server..."
python -m uvicorn bytebot.main:app --host 0.0.0.0 --port $PORT --no-access-log
