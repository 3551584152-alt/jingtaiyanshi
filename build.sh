#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py seed_words

cd frontend
npm ci
npm run build
cd ..

echo "Build complete. Run: python manage.py runserver 127.0.0.1:8002"