#!/usr/bin/env bash
set -e

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright system dependencies (Chromium binary installed at start time)
playwright install-deps chromium

# Build frontend
cd frontend
npm install
npm run build
cd ..
