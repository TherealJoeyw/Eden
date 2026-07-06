#!/bin/sh
set -eu

REPO_URL="https://github.com/yourusername/Eden.git"
APP_DIR="/app"

rm -rf "$APP_DIR"
git clone "$REPO_URL" "$APP_DIR"

cd "$APP_DIR"

python -m pip install --no-cache-dir -r requirements.txt

exec python bot/main.py
