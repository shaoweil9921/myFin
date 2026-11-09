# -*- coding: utf-8 -*-
"""Apply cron job patches via the OpenClaw gateway CLI without PowerShell quoting issues.

Usage:
    python _cron_patch.py <patch.json>

The patch file contains a single JSON object:
    {"jobId": "...", "patch": {...}}
"""
import json
import os
import subprocess
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python _cron_patch.py <patch.json>")
        return 2

    with open(sys.argv[1], "r", encoding="utf-8-sig") as fh:
        params = json.load(fh)

    openclaw = os.path.join(os.environ.get("APPDATA", ""), "npm", "openclaw.cmd")
    cmd = [openclaw, "gateway", "call", "cron.update", "--params", json.dumps(params, separators=(",", ":"))]

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    print("exit:", proc.returncode)
    print(proc.stdout)
    if proc.stderr:
        print("STDERR:", proc.stderr)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
