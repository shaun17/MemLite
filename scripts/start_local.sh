#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${VENV_PYTHON}" ]]; then
  echo "Missing Python virtualenv at ${VENV_PYTHON}" >&2
  echo "Create it with: /opt/homebrew/bin/python3.12 -m venv ${ROOT_DIR}/.venv" >&2
  exit 1
fi

exec "${VENV_PYTHON}" -m memlite.app.main
