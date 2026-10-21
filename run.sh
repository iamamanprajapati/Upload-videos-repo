#!/bin/zsh
# Social Uploader start karo: ./run.sh
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "Pehli baar setup ho raha hai…"
  python3 -m venv .venv || exit 1
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt || exit 1
fi
exec .venv/bin/python app.py
