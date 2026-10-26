"""
_run_daily_signals.py
=====================
Wrapper for the "Ashley Discord - Daily Signals File Generator" cron job.

Runs the full end-of-day Discord pipeline:
  1. _run_discord_fetch.py   -> fetch Discord messages + parse trade signals into Postgres
  2. generate_daily_signals.py --date <today ET>  -> write Obsidian daily signals file

Why this wrapper exists:
The cron job previously only ran step 1, so signals landed in Postgres but no
Obsidian file was ever written. File generation lived only in the heartbeat
instructions, which were removed on 2026-10-15. This wrapper makes the cron job
self-contained and idempotent.

Usage:
  python _run_daily_signals.py                # today ET
  python _run_daily_signals.py --date 2026-10-22   # backfill a specific date
  python _run_daily_signals.py --fetch-only        # skip file generation
  python _run_daily_signals.py --files-only        # skip fetch, only write file
"""
import os
import sys
import subprocess
import argparse
import pathlib
import winreg
from datetime import datetime, timezone, timedelta

WORKSPACE = pathlib.Path(__file__).parent
FETCH_SCRIPT = WORKSPACE / "_run_discord_fetch.py"
GENERATE_SCRIPT = WORKSPACE / "Discord" / "myTrading" / "generate_daily_signals.py"


def get_db_pw():
    """Read DB_PW from Windows registry (HKCU\\Environment)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        try:
            val, _ = winreg.QueryValueEx(key, "DB_PW")
            return val
        finally:
            winreg.CloseKey(key)
    except Exception:
        return ""


def get_today_et():
    """Today in US Eastern time (ET), DST-aware."""
    et_tz = timezone(timedelta(hours=-4))  # EDT; Oct 22-25 is within DST window
    return datetime.now(timezone.utc).astimezone(et_tz).date()


def main():
    parser = argparse.ArgumentParser(description="Discord daily signals: fetch + Obsidian file")
    parser.add_argument("--date", type=str, default=None,
                        help="Date to generate file for (YYYY-MM-DD). Defaults to today ET.")
    parser.add_argument("--fetch-only", action="store_true", help="Run fetch, skip file generation")
    parser.add_argument("--files-only", action="store_true", help="Only write Obsidian file, skip fetch")
    args = parser.parse_args()

    target_date = args.date or get_today_et().strftime("%Y-%m-%d")

    env = os.environ.copy()
    db_pw = get_db_pw()
    if db_pw:
        env["DB_PASSWORD"] = db_pw
        env["DB_PW"] = db_pw
    else:
        print("[WARN] DB_PW not found in registry HKCU\\Environment")

    exit_code = 0

    # ── Step 1: fetch + parse signals ────────────────────────────────────────
    if not args.files_only:
        print(f"[1/2] Fetching Discord messages + parsing signals...")
        r = subprocess.run([sys.executable, str(FETCH_SCRIPT)], env=env)
        if r.returncode != 0:
            print(f"[ERROR] Fetch failed with exit code {r.returncode}")
            exit_code = r.returncode

    # ── Step 2: write Obsidian daily file ───────────────────────────────────
    if not args.fetch_only:
        print(f"\n[2/2] Generating Obsidian daily signals file for {target_date}...")
        r = subprocess.run(
            [sys.executable, str(GENERATE_SCRIPT), "--date", target_date],
            env=env
        )
        if r.returncode != 0:
            print(f"[ERROR] File generation failed with exit code {r.returncode}")
            exit_code = r.returncode

    print("\n[DONE] Daily signals pipeline complete.")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
