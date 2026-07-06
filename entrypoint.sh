#!/bin/sh
set -eu

REPO_URL="${REPO_URL:-https://github.com/TherealJoeyw/Eden.git}"
BRANCH="${BRANCH:-main}"

cd /
rm -rf /app
git clone --branch "$BRANCH" --single-branch "$REPO_URL" /app

cd /app
python -m pip install --no-cache-dir -r requirements.txt

exec python bot/main.py
