"""
Jarsy Extraction Script — CDP via profile="user"
==============================================
This script is designed to run INSIDE an OpenClaw agent session that has
browser tool access. It uses profile="user" to connect to the running Chrome,
navigates to Jarsy, and extracts data.

Usage (from OpenClaw agent):
    python jarsy_extract.py

The script uses browser tool via subprocess to access Chrome with profile="user".
It extracts data and saves directly to the database.
"""

import json
import os
import subprocess
import sys
import time
from datetime import date

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "database": "fintech",
    "user": "postgres",
    "password": "asdfghjk1234%",
}


def get_conn():
    import psycopg2
    return psycopg2.connect(**DB_CONFIG)


def db_check_holiday():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT holiday_name FROM market_holidays WHERE date = CURRENT_DATE")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def db_get_today_scan():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT scan_id, status FROM scan "
        "WHERE scan_name = 'Jarsy Presale' AND DATE(scan_time) = CURRENT_DATE"
    )
    row = cur.fetchone()
    conn.close()
    return row


def db_insert_scan(status="started"):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO scan (scan_name, scan_time, status, source) "
        "VALUES ('Jarsy Presale', NOW(), %s, 'jarsy') RETURNING scan_id",
        (status,),
    )
    scan_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return scan_id


def db_update_scan(scan_id, status, note=None):
    conn = get_conn()
    cur = conn.cursor()
    if note:
        cur.execute(
            "UPDATE scan SET status = %s, scan_note = %s WHERE scan_id = %s",
            (status, note, scan_id),
        )
    else:
        cur.execute("UPDATE scan SET status = %s WHERE scan_id = %s", (status, scan_id))
    conn.commit()
    conn.close()


def db_insert_presale(scan_id, tokens):
    import psycopg2
    conn = get_conn()
    cur = conn.cursor()
    count = 0
    for tok in tokens:
        cur.execute(
            """
            INSERT INTO jarsy_asset (extract_date, token_name, symbol, price, holding, action, scan_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (extract_date, symbol) DO UPDATE SET
                token_name = EXCLUDED.token_name, price = EXCLUDED.price,
                holding = EXCLUDED.holding, action = EXCLUDED.action, updated_at = NOW()
            """,
            (date.today(), tok["name"], tok["symbol"], tok["price"],
             tok.get("holding", "-"), "Buy", scan_id),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


def db_insert_live(scan_id, tokens):
    import psycopg2
    conn = get_conn()
    cur = conn.cursor()
    count = 0
    for tok in tokens:
        cur.execute(
            """
            INSERT INTO jarsy_asset_live (extract_date, token_name, symbol, price, holding, action, scan_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (extract_date, symbol) DO UPDATE SET
                token_name = EXCLUDED.token_name, price = EXCLUDED.price,
                holding = EXCLUDED.holding, action = EXCLUDED.action, updated_at = NOW()
            """,
            (date.today(), tok["name"], tok["symbol"], tok["price"],
             tok.get("holding", "-"), "Buy", scan_id),
        )
        count += 1
    conn.commit()
    conn.close()
    return count


# ─────────────────────────────────────────────────────────────────────────────
# OpenClaw browser tool CDP commands
# This script is run from an OpenClaw agent which has browser access.
# We use openclaw CLI commands to drive the browser.
# ─────────────────────────────────────────────────────────────────────────────

OPENCLAW = "openclaw"


def browser_start_user():
    """Start browser with profile=user (attaches to running Chrome)."""
    result = subprocess.run(
        [OPENCLAW, "browser", "start", "--profile", "user"],
        capture_output=True, text=True, timeout=30,
    )
    return result.returncode == 0, result.stdout, result.stderr


def browser_navigate(url, timeout=60):
    """Navigate browser to URL, return True on success."""
    result = subprocess.run(
        [OPENCLAW, "browser", "navigate", "--url", url, "--timeout", str(timeout)],
        capture_output=True, text=True, timeout=timeout + 10,
    )
    return result.returncode == 0


def browser_snapshot():
    """Get browser snapshot."""
    result = subprocess.run(
        [OPENCLAW, "browser", "snapshot"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        try:
            return json.loads(result.stdout)
        except Exception:
            return None
    return None


def browser_eval(js):
    """Evaluate JavaScript in browser, return result."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        f.flush()
        fname = f.name
    try:
        result = subprocess.run(
            [OPENCLAW, "browser", "eval", "--file", fname],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            try:
                return json.loads(result.stdout)
            except Exception:
                return result.stdout.strip()
        return None
    finally:
        os.unlink(fname)


def browser_get_cookies():
    """Get all cookies from current browser session via CDP."""
    js = """
        () => {
            // Use Chrome's cookie API via document.cookie
            // For full cookie access, we use the Network.getCookies CDP method
            // Since we can't call CDP directly from JS, we return document.cookie
            // which gives non-HttpOnly cookies
            return document.cookie;
        }
    """
    return browser_eval(js)


def browser_click(selector):
    """Click an element matching selector."""
    result = subprocess.run(
        [OPENCLAW, "browser", "click", "--selector", selector],
        capture_output=True, text=True, timeout=15,
    )
    return result.returncode == 0


def browser_stop():
    """Stop browser."""
    subprocess.run([OPENCLAW, "browser", "stop"], capture_output=True, timeout=10)


# ─────────────────────────────────────────────────────────────────────────────
# Data extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_pe_data():
    """
    Navigate to Jarsy Private Equity page and extract both Presale and Live tables.
    Uses OpenClaw browser tool commands.
    """
    import re

    # Navigate to Private Equity
    print("Navigating to Jarsy...")
    success = browser_navigate("https://app.jarsy.com/layout/PrivateEquity", timeout=90)
    if not success:
        print("Navigation failed")
        return None

    time.sleep(5)

    # Check if logged in
    url = browser_eval("() => window.location.href")
    print(f"Current URL: {url}")
    if "login" in str(url).lower():
        print("Not logged in!")
        return None

    # Extract data via JavaScript
    extract_js = """
        () => {
            // Try to find token data from the page
            const results = { tokens: [], method: 'dom' };

            // Look for data in React state / props
            const findData = (node, depth=0) => {
                if (depth > 10) return;
                try {
                    const keys = Object.keys(node);
                    for (const k of keys) {
                        if (k.includes('token') || k.includes('symbol') || k.includes('holding')) {
                            const v = node[k];
                            if (Array.isArray(v) && v.length > 0 && v[0] && (v[0].symbol || v[0].name)) {
                                results.tokens = v;
                                results.method = 'react';
                                return;
                            }
                        }
                        if (node[k] && typeof node[k] === 'object') {
                            findData(node[k], depth+1);
                        }
                    }
                } catch(e) {}
            };

            // Check for window state
            if (window.__NEXT_DATA__) {
                try {
                    const data = JSON.parse(window.__NEXT_DATA__);
                    if (data.props && data.props.pageProps) {
                        findData(data.props.pageProps);
                    }
                } catch(e) {}
            }

            // Look for table data in DOM
            if (results.tokens.length === 0) {
                const rows = [];
                document.querySelectorAll('table tbody tr, [class*=row], [class*=item]').forEach(el => {
                    const text = el.innerText || el.textContent || '';
                    const match = text.match(/J[A-Z]{3,8})\\s+\\$?([\\d,]+\\.?\\d*)/);
                    if (match) {
                        rows.push({ symbol: match[1], price: match[2].replace(',',''), name: match[1], holding: '-' });
                    }
                });
                if (rows.length > 0) {
                    results.tokens = rows;
                    results.method = 'text';
                }
            }

            // Also try __jarsy state
            if (window.__jarsy) {
                findData(window.__jarsy);
            }

            return results;
        }
    """

    # Get presale
    print("Extracting Presale data...")
    presale_result = browser_eval(extract_js)
    presale_tokens = []
    if presale_result and isinstance(presale_result, dict) and presale_result.get("tokens"):
        presale_tokens = presale_result["tokens"]
        print(f"  Found {len(presale_tokens)} presale tokens via {presale_result.get('method', '?')}")
    else:
        # Fallback: parse page text
        print("  Trying text extraction...")
        text_js = """
            () => {
                const text = document.body.innerText;
                const pattern = /J([A-Z]{2,8})\\s+\\$?([\\d,]+\\.?\\d*)\\s*(\\w+[%]?)?/g;
                const matches = [];
                let m;
                while ((m = pattern.exec(text)) !== null) {
                    matches.push({ symbol: 'J'+m[1], price: m[2].replace(',',''), name: 'J'+m[1], holding: m[3] || '-' });
                }
                return matches;
            }
        """
        presale_tokens = browser_eval(text_js) or []
        print(f"  Text extraction: {len(presale_tokens)} tokens")

    # Try switching to Live tab
    live_tokens = []
    print("Trying Live tab...")
    try:
        # Look for Live tab/button
        live_js = """
            () => {
                const tabs = document.querySelectorAll('[class*=tab], button, [role=tab]');
                for (const t of tabs) {
                    if (/live/i.test(t.textContent)) { t.click(); return true; }
                }
                return false;
            }
        """
        clicked = browser_eval(live_js)
        if clicked:
            time.sleep(3)
            live_tokens = browser_eval(extract_js) or []
            if isinstance(live_tokens, dict):
                live_tokens = live_tokens.get("tokens", [])
            print(f"  Live: {len(live_tokens)} tokens")
    except Exception as e:
        print(f"  Live tab error: {e}")

    return {"presale": presale_tokens, "live": live_tokens}


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("Jarsy Extraction (OpenClaw browser)")
    print("=" * 50)

    # 1. Holiday check
    holiday = db_check_holiday()
    if holiday:
        print(f"Market holiday: {holiday} — exiting")
        sys.exit(0)

    # 2. Check/create scan
    scan_row = db_get_today_scan()
    if scan_row:
        scan_id, status = scan_row
        if status == "completed":
            print(f"Scan {scan_id} already completed — exiting")
            sys.exit(0)
        print(f"Resuming scan {scan_id} (status={status})")
    else:
        scan_id = db_insert_scan()
        print(f"Created scan {scan_id}")

    # 3. Browser
    db_update_scan(scan_id, "in_progress", "Extracting via profile=user")
    print("Starting browser...")

    try:
        data = extract_pe_data()
    finally:
        browser_stop()

    if not data:
        print("Extraction failed")
        db_update_scan(scan_id, "login_required", "Extraction failed")
        sys.exit(1)

    # 4. Save to DB
    presale = data.get("presale", [])
    live = data.get("live", [])

    if presale:
        n = db_insert_presale(scan_id, presale)
        print(f"Saved {n} presale tokens")
    else:
        print("No presale tokens extracted")

    if live:
        n = db_insert_live(scan_id, live)
        print(f"Saved {n} live tokens")
    else:
        print("No live tokens extracted")

    db_update_scan(
        scan_id, "completed",
        f"Done: {len(presale)} presale, {len(live)} live"
    )
    print(f"Done! Scan {scan_id}")


if __name__ == "__main__":
    main()
