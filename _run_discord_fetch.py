"""
Wrapper that chains: 03_fetch_messages.py -> 02_parse_signals.py
Loads DB_PW from Windows registry (HKCU:\Environment\DB_PW) before spawning subprocesses.
"""
import subprocess, sys, os, pathlib, winreg

SCRIPT_DIR = pathlib.Path(__file__).parent / "Discord" / "myTrading"

def get_db_pw():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        try:
            val, _ = winreg.QueryValueEx(key, "DB_PW")
            return val
        finally:
            winreg.CloseKey(key)
        return ""
    except Exception:
        return ""

def main():
    db_pw = get_db_pw()
    if not db_pw:
        print("ERROR: DB_PW not found in registry HKCU\\Environment")
        sys.exit(1)

    env = os.environ.copy()
    env["DB_PASSWORD"] = db_pw

    # Step 1: Fetch messages
    fetch_script = SCRIPT_DIR / "03_fetch_messages.py"
    print(f"[1/2] Fetching messages: {fetch_script}")
    r1 = subprocess.run([sys.executable, str(fetch_script)], env=env)
    if r1.returncode != 0:
        print(f"[ERROR] Fetch failed with exit code {r1.returncode}")
        sys.exit(r1.returncode)

    # Step 2: Parse signals
    parse_script = SCRIPT_DIR / "02_parse_signals.py"
    print(f"[2/2] Parsing signals: {parse_script}")
    r2 = subprocess.run([sys.executable, str(parse_script)], env=env)
    if r2.returncode != 0:
        print(f"[ERROR] Parse failed with exit code {r2.returncode}")
        sys.exit(r2.returncode)

    print("[DONE] Discord fetch + parse complete.")

if __name__ == "__main__":
    main()
