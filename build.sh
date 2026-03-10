#!/usr/bin/env bash
set -e

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browser (needed for price scraper)
playwright install chromium

# Build frontend
cd frontend
npm install
npm run build
cd ..
