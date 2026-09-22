"""
Jarsy Token Extraction — CDP Method
===================================
Uses Chrome at localhost:9222 (from jarsy_launch_and_login.py).
Leaves browser running after extraction.
Saves to jarsy_presale.json and jarsy_live.json.
"""
import json, re, sys
from playwright.sync_api import sync_playwright

CDP_URL = "http://localhost:9222"
PRESALE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_presale.json"
LIVE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_live.json"
PE_URL = "https://app.jarsy.com/layout/PrivateEquity"

SKIP_LINES = {"Buy / Sell", "Sell", "-", "", "LOCKING PERIOD", "EARLY ACCESS", "- -"}


def parse_tokens(lines):
    tokens = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i].strip()

        # Detect token row: company name contains "- Jarsy"
        if "- Jarsy" not in line:
            i += 1
            continue

        company_name = line.strip()
        i += 1

        # Skip blank / skip lines
        while i < n and lines[i].strip() in SKIP_LINES:
            i += 1
        if i >= n:
            break

        symbol = lines[i].strip()
        i += 1

        # Skip "EARLY ACCESS" / "LOCKING PERIOD" / separators
        while i < n and lines[i].strip() in SKIP_LINES:
            i += 1
        if i >= n:
            break

        # Parse price
        price = ""
        while i < n:
            stripped = lines[i].strip()
            if stripped in ("Buy / Sell", "Sell"):
                break
            if stripped.startswith("$") and len(stripped) > 1 and stripped[1].isdigit():
                price = stripped[1:].replace(",", "")
                i += 1
                break
            # Also handle "Price: $X.XX"
            m = re.search(r"(?:Price:\s*)?\$?([\d,]+\.?\d*)", stripped)
            if m:
                price = m.group(1).replace(",", "")
                i += 1
                break
            i += 1

        tokens.append({
            "symbol": symbol,
            "name": company_name,
            "price": price,
            "holding": "-"
        })

    return tokens


def extract():
    # Connect to existing Chrome (started by jarsy_launch_and_login.py)
    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(CDP_URL, timeout=30000)
            ctx = browser.contexts[0]
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

            print("Navigating to Private Equity page...")
            page.goto(PE_URL, timeout=60000)
            page.wait_for_timeout(8000)

            # ── Live tab ────────────────────────────────────────────────────
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

            # ── Presale tab ────────────────────────────────────────────────
            print("Clicking Presale tab...")
            try:
                page.get_by_text("Private Equity Presale").click(timeout=5000)
            except Exception:
                pass
            page.wait_for_timeout(4000)

            body2 = page.inner_text("body")
            presale_count = body2.count("- Jantsy")  # typo in original — keep it for compatibility
            if presale_count == 0:
                presale_count = body2.count("- Jarsy")
            print(f"  Presale tokens in DOM: {presale_count}")
            presale_tokens = parse_tokens(body2.split("\n"))
            print(f"  Parsed: {len(presale_tokens)}")

            # ── Save ────────────────────────────────────────────────────────
            with open(PRESALE_FILE, "w") as f:
                json.dump(presale_tokens, f, indent=2)
            with open(LIVE_FILE, "w") as f:
                json.dump(live_tokens, f, indent=2)

            print(f"Saved {len(presale_tokens)} presale -> {PRESALE_FILE}")
            print(f"Saved {len(live_tokens)} live -> {LIVE_FILE}")

            # DO NOT close browser — leave it running for next extraction
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
        print(f"SUCCESS: {n_pre} presale, {n_live} live")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
