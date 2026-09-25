#!/usr/bin/env sh
set -eu
if [ ! -d .venv ]; then python -m venv .venv; fi
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python scripts/seed_demo.py
exec uvicorn app.main:app --reload
