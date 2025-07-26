#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies from requirements.txt
pip install -r requirements.txt

# Install Playwright's browsers. The '--with-deps' is no longer
# needed because render.yaml is handling the system libraries.
playwright install