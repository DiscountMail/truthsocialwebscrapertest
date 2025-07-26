#!/usr/bin/env bash
set -o errexit

# Install Python dependencies
pip install -r requirements.txt

# Install only the browsers (no OS‑package install)
playwright install
