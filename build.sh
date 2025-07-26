#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Tell Playwright to install browsers into the persistent disk.
# The PLAYWRIGHT_BROWSERS_PATH env var from render.yaml makes this work.
playwright install