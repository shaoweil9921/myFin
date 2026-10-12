"""
Stock data update check script.
Checks market holidays/early closes and skips fetch if market is closed.
Runs the full Finviz pipeline (scrape + load) only on trading days.
Uses DB_PW from registry to handle subprocess DB access.
"""
import psycopg2
import subprocess
import sys
import os
from datetime import datetime, date
import winreg

# Paths
WORKSPACE = r'C:\Users\shaowei_l\.openclaw\workspace'
SCRAPE_SCRIPT = os.path.join(WORKSPACE, 'scrape_finviz.py')
LOAD_SCRIPT = os.path.join(WORKSPACE, 'load_finviz_data.py')


def get_db_pw():
    """Read DB_PW from Windows registry (HKCU\\Environment)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        db_pw, _ = winreg.QueryValueEx(key, "DB_PW")
        winreg.CloseKey(key)
        return db_pw
    except Exception:
        return None


def get_db_kwargs():
    """Build DB connection kwargs using registry password."""
    db_pw = get_db_pw()
    if db_pw:
        return dict(host='127.0.0.1', dbname='fintech', user='postgres', password=db_pw)
    # Fallback: try DB_PASSWORD from env
    db_pw = os.environ.get('DB_PASSWORD', 'asdfghjk1234%')
    return dict(host='127.0.0.1', dbname='fintech', user='postgres', password=db_pw)


DB_KWARGS = get_db_kwargs()


def is_market_closed_today():
    """Returns (closed, reason)"""
    today = date.today()
    
    # Check day of week (0=Monday, 6=Sunday in Python)
    dow = today.weekday()
    if dow >= 5:
        return True, f"Weekend (dow={dow})"
    
    try:
        conn = psycopg2.connect(**DB_KWARGS)
        conn.autocommit = True
        cur = conn.cursor()
        
        # Check market holidays
        cur.execute("SELECT holiday_name FROM market_holidays WHERE date = %s", (today,))
        r = cur.fetchone()
        if r:
            reason = f"Holiday: {r[0]}"
            cur.close()
            conn.close()
            return True, reason
        
        # Check early close
        cur.execute("SELECT close_time FROM market_holidays WHERE date = %s AND is_early_close = true", (today,))
        r = cur.fetchone()
        if r:
            reason = f"Early close at {r[0]}"
            cur.close()
            conn.close()
            return True, reason
        
        cur.close()
        conn.close()
        return False, "Open"
        
    except Exception as e:
        print(f"DB check failed: {e}, proceeding with caution")
        return False, f"DB error: {e}"


def check_already_loaded():
    """Check if GapperMid data already loaded today"""
    try:
        conn = psycopg2.connect(**DB_KWARGS)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM finviz_screener_scan_result r 
            JOIN scan s ON r.scan_id = s.scan_id 
            WHERE s.scan_name = 'GapperMid' AND DATE(s.scan_time) = CURRENT_DATE
        """)
        cnt = cur.fetchone()[0]
        cur.close()
        conn.close()
        return cnt > 0
    except Exception as e:
        print(f"DB check already-loaded failed: {e}")
        return False


def run_step(script_path, step_name):
    """Run a Python script with DB_PW set in its environment."""
    print(f"\n=== {step_name} ===")
    try:
        # Build env with DB_PW for child process
        env = os.environ.copy()
        db_pw = get_db_pw()
        if db_pw:
            env['DB_PW'] = db_pw
        
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=WORKSPACE,
            env=env
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        if result.returncode != 0:
            print(f"FAILED: {step_name} (exit {result.returncode})")
            return False
        print(f"SUCCESS: {step_name}")
        return True
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: {step_name} (>300s)")
        return False
    except Exception as e:
        print(f"ERROR: {step_name}: {e}")
        return False


def main():
    now = datetime.now()
    print(f"=== Stock Data Update Check ===")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')} (America/New_York)")
    print(f"DB_PW: {'loaded from registry' if get_db_pw() else 'NOT in registry'}")
    
    # Check if market is open
    closed, reason = is_market_closed_today()
    print(f"Market status: {reason}")
    
    if closed:
        print("MARKET CLOSED - skipping stock data fetch")
        print(f"  Reason: {reason}")
        sys.exit(0)
    
    # Check if already loaded today
    if check_already_loaded():
        print("Data already loaded today - skipping")
        sys.exit(0)
    
    # Run the full pipeline
    print("\nMarket open - running Finviz pipeline...")
    
    # Step 1: Scrape
    if not run_step(SCRAPE_SCRIPT, "Scrape Finviz"):
        print("Scrape failed - aborting")
        sys.exit(1)
    
    # Step 2: Load
    if not run_step(LOAD_SCRIPT, "Load to DB"):
        print("Load failed - aborting")
        sys.exit(1)
    
    print("\n=== PIPELINE COMPLETE ===")


if __name__ == '__main__':
    main()
