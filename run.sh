#!/usr/bin/env bash
cd "$(dirname "$0")"
python3 -c "import PySide6" >/dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "PySide6 is not installed."
  echo "Run: python3 -m pip install -r requirements.txt"
  exit 1
fi
python3 main.py
