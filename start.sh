#!/usr/bin/env bash
set -e

# Install Chromium binary at runtime (Render wipes build cache before starting)
playwright install --with-deps chromium

# Start the app
exec uvicorn backend.app:app --host 0.0.0.0 --port "$PORT"
