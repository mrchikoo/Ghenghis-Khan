#!/usr/bin/env bash
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  echo "First run — please run ./install.sh"
  exit 1
fi
exec ./.venv/bin/python ghenghis_khan.py
