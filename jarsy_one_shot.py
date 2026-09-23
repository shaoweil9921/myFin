"""
Jarsy One-Shot: Login + Extract
==============================="""
import pickle, time, json, re, sys
from playwright.sync_api import sync_playwright

PROFILE_DIR = r"C:\Users\shaowei_l\AppData\Local\Google\Chrome\User Data\jarsy_profile"
COOKIE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_cookies.pkl"
WS_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_ws.txt"
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


def get_text_fallback(page):
    """Try evaluate first, fallback to content parsing."""
    # Try inner_text first (fast when it works)
    try:
        return page.inner_text("body")
    except Exception:
        pass
    # Fallback: parse HTML for visible text
    try:
        html = page.content()
        # Strip tags and get visible text
        import re as _re
        text = _re.sub(r'<script[^>]*>.*?</script>', '', html, flags=_re.DOTALL)
        text = _re.sub(r'<style[^>]*>.*?</style>', '', text, flags=_re.DOTALL)
        text = _re.sub(r'<[^>]+>', '\n', text)
        text = _re.sub(r'\n+', '\n', text)
        return text
    except Exception:
        return ""


print("Starting Jarsy one-shot...")
sys.stdout.flush()

with sync_playwright() as p:
    print("Launching Chrome...")
    sys.stdout.flush()
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        viewport={"width": 1400, "height": 900},
        timeout=30000,
        args=["--remote-debugging-port=9223", "--remote-allow-origins=*"],
    )
    page = ctx.pages[0]
    print(f"Page created: {page.url}")
    sys.stdout.flush()
    
    print("Navigating to Jarsy...")
    sys.stdout.flush()
    page.goto("https://app.jarsy.com/layout/Home", timeout=20000)
    page.wait_for_timeout(5000)
    print(f"URL after nav: {page.url}")
    sys.stdout.flush()
    
    body = get_text_fallback(page)
    has_pe = "Private Equity Live" in body or "Private Equity Presale" in body
    print(f"Has PE text: {has_pe} (body len={len(body)})")
    sys.stdout.flush()
    
    if not has_pe:
        print("Not on PE page. Waiting for manual login...")
        sys.stdout.flush()
        for i in range(12):
            time.sleep(5)
            body = get_text_fallback(page)
            if "Private Equity Live" in body or "Private Equity Presale" in body:
                print(f"Login detected at {i*5}s!")
                break
            print(f"  [{i*5}s] still waiting... body_len={len(body)}")
            sys.stdout.flush()
        else:
            print("Timeout!")
            ctx.close()
            sys.exit(1)
    
    # Save WS URL
    import urllib.request
    try:
        req = urllib.request.urlopen("http://localhost:9223/json", timeout=5)
        tabs = json.loads(req.read())
        for tab in tabs:
            if "app.jarsy.com" in tab.get("url","") and "blob:" not in tab.get("url",""):
                with open(WS_FILE, "w") as f:
                    f.write(tab.get("webSocketDebuggerUrl",""))
                print(f"Saved WS URL")
                break
    except Exception as e:
        print(f"WS save error: {e}")
    
    # Navigate to PE
    print("Going to PE page...")
    sys.stdout.flush()
    page.goto(PE_URL, timeout=30000)
    page.wait_for_timeout(8000)
    
    # Live tab
    print("Clicking Live tab...")
    sys.stdout.flush()
    try:
        page.get_by_text("Private Equity Live").click(timeout=5000)
    except Exception as e:
        print(f"Click error: {e}")
    page.wait_for_timeout(8000)
    body = get_text_fallback(page)
    live_count = body.count("- Jarsy")
    print(f"  Live DOM count: {live_count}, body_len={len(body)}")
    live_tokens = parse_tokens(body.split("\n"))
    print(f"  Parsed: {len(live_tokens)}")
    sys.stdout.flush()
    
    # Presale tab
    print("Clicking Presale tab...")
    sys.stdout.flush()
    try:
        page.get_by_text("Private Equity Presale").click(timeout=5000)
    except Exception as e:
        print(f"Click error: {e}")
    page.wait_for_timeout(6000)
    body2 = get_text_fallback(page)
    presale_count = body2.count("- Jarsy")
    print(f"  Presale DOM count: {presale_count}, body_len={len(body2)}")
    presale_tokens = parse_tokens(body2.split("\n"))
    print(f"  Parsed: {len(presale_tokens)}")
    sys.stdout.flush()
    
    # Save cookies
    cookies = ctx.cookies()
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(cookies, f)
    print(f"Saved {len(cookies)} cookies")
    
    # Save JSON
    with open(PRESALE_FILE, "w") as f:
        json.dump(presale_tokens, f, indent=2)
    with open(LIVE_FILE, "w") as f:
        json.dump(live_tokens, f, indent=2)
    
    print(f"\n=== RESULTS ===")
    print(f"Presale: {len(presale_tokens)}")
    print(f"Live: {len(live_tokens)}")
    for t in live_tokens[:5]:
        print(f"  {t['symbol']}: {t['name'][:40]}")
    
    print(f"\nChrome running on port 9223")
    print("Press Ctrl+C to close")
    
    try:
        time.sleep(600)
    except KeyboardInterrupt:
        pass
    ctx.close()
