"""
Jarsy Token Extraction — CDP Method
=================================
Reads websocket URL from jarsy_ws.txt (created by jarsy_one_shot.py or jarsy_launch_and_login.py).
Connects via CDP, extracts tokens from PE page, saves JSON.
Leaves browser running after extraction.
"""
import json, re, sys, pickle, time
from playwright.sync_api import sync_playwright

WS_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_ws.txt"
COOKIE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_cookies.pkl"
PRESALE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_presale.json"
LIVE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_live.json"
PE_URL = "https://app.jarsy.com/layout/PrivateEquity"
SKIP_LINES = {"Buy / Sell", "Sell", "-", "", "LOCKING PERIOD", "EARLY ACCESS", "- -"}


def is_pe_page(page):
    try:
        body = page.inner_text("body")
        return "Private Equity Live" in body or "Private Equity Presale" in body
    except Exception:
        return False


def parse_tokens(lines):
    tokens = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        if "- Jarsy" not in line:
            i += 1
            continue
        company_name = line.strip()
        i += 1
        while i < n and lines[i].strip() in SKIP_LINES:
            i += 1
        if i >= n:
            break
        symbol = lines[i].strip()
        i += 1
        while i < n and lines[i].strip() in SKIP_LINES:
            i += 1
        if i >= n:
            break
        price = ""
        while i < n:
            stripped = lines[i].strip()
            if stripped in ("Buy / Sell", "Sell"):
                break
            m = re.search(r"(?:Price:\s*)?\$?([\d,]+\.?\d*)", stripped)
            if m:
                price = m.group(1).replace(",", "")
                i += 1
                break
            i += 1
        tokens.append({"symbol": symbol, "name": company_name, "price": price, "holding": "-"})
    return tokens


def extract():
    # Read websocket URL
    try:
        with open(WS_FILE) as f:
            ws_url = f.read().strip()
        print(f"Using websocket: {ws_url[:80]}")
    except FileNotFoundError:
        print(f"WS file not found: {WS_FILE}")
        print("Run: python jarsy_one_shot.py first")
        sys.exit(1)

    browser = None
    try:
        with sync_playwright() as p:
            # Connect via CDP using websocket URL
            browser = p.chromium.connect_over_cdp(ws_url, timeout=30000)
            
            # Get context and pages
            ctx = browser.contexts[0]
            print(f"Pages in context: {len(ctx.pages)}")
            
            # Find PE page
            page = None
            for pg in ctx.pages:
                print(f"  Page: {pg.url}")
                if "PrivateEquity" in pg.url:
                    page = pg
            
            if not page:
                print("No PE page found, creating one...")
                page = ctx.new_page()
                page.goto(PE_URL, timeout=60000)
                page.wait_for_timeout(8000)
            
            print(f"Using page: {page.url}")
            
            # Live tab
            print("Clicking Live tab...")
            try:
                page.get_by_text("Private Equity Live").click(timeout=5000)
            except Exception:
                pass
            page.wait_for_timeout(8000)
            body = page.inner_text("body")
            live_count = body.count("- Jarsy")
            print(f"  Live tokens in DOM: {live_count}")
            live_tokens = parse_tokens(body.split("\n"))
            print(f"  Parsed: {len(live_tokens)}")

            # Presale tab
            print("Clicking Presale tab...")
            try:
                page.get_by_text("Private Equity Presale").click(timeout=5000)
            except Exception:
                pass
            page.wait_for_timeout(4000)
            body2 = page.inner_text("body")
            presale_count = body2.count("- Jarsy")
            print(f"  Presale tokens in DOM: {presale_count}")
            presale_tokens = parse_tokens(body2.split("\n"))
            print(f"  Parsed: {len(presale_tokens)}")

            with open(PRESALE_FILE, "w") as f:
                json.dump(presale_tokens, f, indent=2)
            with open(LIVE_FILE, "w") as f:
                json.dump(live_tokens, f, indent=2)

            print(f"\nSaved {len(presale_tokens)} presale -> {PRESALE_FILE}")
            print(f"Saved {len(live_tokens)} live -> {LIVE_FILE}")
            
            for t in live_tokens[:5]:
                print(f"  {t['symbol']}: {t['name'][:40]}")

            return len(presale_tokens), len(live_tokens)

    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass


if __name__ == "__main__":
    try:
        n_pre, n_live = extract()
        print(f"\nSUCCESS: {n_pre} presale, {n_live} live")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
