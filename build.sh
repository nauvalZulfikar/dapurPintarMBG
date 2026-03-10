#!/usr/bin/env bash
set -e

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright + system dependencies (needed for price scraper on Linux)
playwright install --with-deps chromium

# Build frontend
cd frontend
npm install
npm run build
cd ..
