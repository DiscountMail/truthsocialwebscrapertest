#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browsers. We remove --with-deps because
# render.yaml is now handling the system dependencies for us.
playwright install
