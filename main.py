#!/usr/bin/env python3
"""Echo Recon Linux Edition entry point."""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    if platform.system() != "Linux":
        print("Echo Recon Linux Edition supports Linux only (Kali, Debian, Ubuntu, etc.).", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description="Echo Recon Linux Edition — authorized reconnaissance dashboard")
    parser.add_argument("--check-tools", action="store_true", help="Print local dependency status as JSON")
    parser.add_argument("--test", action="store_true", help="Run offline unit/regression tests")
    parser.add_argument("--version", action="version", version="Echo Recon echo 2026.10")
    args = parser.parse_args()
    if args.check_tools:
        from echo_recon.tools import tool_status
        print(json.dumps(tool_status(), indent=2, ensure_ascii=False))
        return 0
    if args.test:
        return subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT)
    from echo_recon.ui import launch
    launch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
