"""
Jarsy Token Extraction - Playwright profile method
Uses jarsy_profile (logged-in session) for extraction
Saves to jarsy_presale.json and jarsy_live.json
"""
import json, re, sys
from playwright.sync_api import sync_playwright

PROFILE_DIR = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_profile"
PRESALE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_presale.json"
LIVE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_live.json"

def parse_tokens(lines):
    tokens = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        if "- Jarsy" not in line:
            i += 1
            continue

        company_name = line
        i += 1

        # Skip tab/whitespace lines
        while i < n and lines[i].strip() == '' and '\t' in lines[i]:
            i += 1
        if i >= n:
            break

        next_line = lines[i].strip()

        if next_line == 'EARLY ACCESS':
            # Presale: company -> EARLY ACCESS -> symbol -> (no price)
            i += 1
            while i < n and lines[i].strip() in ('', '-', 'Buy / Sell', 'Sell'):
                i += 1
            symbol = lines[i].strip() if i < n else ''
            i += 1
            price = ''

        elif next_line == 'LOCKING PERIOD':
            # Live lock: company -> LOCKING PERIOD -> symbol -> ... -> $price -> Buy/Sell
            i += 1
            while i < n and lines[i].strip() in ('', '-', '\t'):
                i += 1
            symbol = lines[i].strip() if i < n else ''
            i += 1
            # Skip to price
            price = ''
            while i < n:
                stripped = lines[i].strip()
                if stripped in ('Buy / Sell', 'Sell'):
                    break
                if stripped.startswith('$') and len(stripped) > 1 and stripped[1].isdigit():
                    price = stripped[1:].replace(',', '')
                    i += 1
                    break
                i += 1

        else:
            # Normal: company -> symbol -> ... -> $price -> Buy/Sell
            symbol = next_line
            i += 1
            # Skip until we find $price or Buy/Sell
            price = ''
            while i < n:
                stripped = lines[i].strip()
                if stripped in ('Buy / Sell', 'Sell'):
                    break
                if stripped.startswith('$') and len(stripped) > 1 and stripped[1].isdigit():
                    price = stripped[1:].replace(',', '')
                    i += 1
                    break
                i += 1

        tokens.append({"symbol": symbol, "name": company_name,
                      "price": price, "holding": "-"})
    return tokens

def extract():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            viewport={"width": 1400, "height": 900},
            timeout=30000
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://app.jarsy.com/layout/PrivateEquity", timeout=30000)
        page.wait_for_timeout(8000)

        # Live tab
        page.get_by_text("Private Equity Live").click(timeout=5000)
        page.wait_for_timeout(8000)
        live_tokens = parse_tokens(page.inner_text("body").split("\n"))
        print(f"Live tokens: {len(live_tokens)}")

        # Presale tab
        page.get_by_text("Private Equity Presale").click(timeout=5000)
        page.wait_for_timeout(3000)
        presale_tokens = parse_tokens(page.inner_text("body").split("\n"))
        print(f"Presale tokens: {len(presale_tokens)}")

        with open(PRESALE_FILE, "w") as f:
            json.dump(presale_tokens, f, indent=2)
        with open(LIVE_FILE, "w") as f:
            json.dump(live_tokens, f, indent=2)

        print(f"Saved {len(presale_tokens)} presale -> {PRESALE_FILE}")
        print(f"Saved {len(live_tokens)} live -> {LIVE_FILE}")

        ctx.close()
        return len(presale_tokens), len(live_tokens)

if __name__ == "__main__":
    try:
        n_pre, n_live = extract()
        print(f"SUCCESS: {n_pre} presale, {n_live} live")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
