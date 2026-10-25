#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This package is Linux-only. Run it on Kali Linux, Debian or Ubuntu." >&2
  exit 2
fi
command -v python3 >/dev/null 2>&1 || { echo "python3 is required. Run ./install_linux.sh" >&2; exit 1; }
python3 "$ROOT/main.py" "$@"
