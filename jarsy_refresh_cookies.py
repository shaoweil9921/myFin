"""
Jarsy Cookie Refresh - Definitive Fix
======================================
Opens Chrome on debug port 9222, user logs in, waits for full OAuth roundtrip,
navigates to PE, waits for content, saves cookies.
The key: Chrome stays running on 9222 so extract.py can connect.
"""
import pickle, time, subprocess, os, sys
from playwright.sync_api import sync_playwright

PROFILE_DIR = r"C:\Users\shaowei_l\AppData\Local\Google\Chrome\User Data\jarsy_profile"
COOKIE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_cookies.pkl"
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9222

def is_pe_page(page):
    try:
        body = page.inner_text("body")
        return "Private Equity Live" in body or "Private Equity Presale" in body
    except Exception:
        return False

def get_debug_url(port):
    """Get CDP websocket URL from Chrome debug port."""
    import urllib.request
    try:
        req = urllib.request.urlopen(f"http://localhost:{port}/json", timeout=5)
        tabs = json.loads(req.read())
        for tab in tabs:
            if "jarsy" in tab.get("url","").lower():
                return tab.get("webSocketDebuggerUrl")
        return tabs[0].get("webSocketDebuggerUrl") if tabs else None
    except Exception:
        return None

# ── Step 1: Launch Chrome on debug port ───────────────────────────────────────
print("Step 1: Launching Chrome on debug port 9222...")
chrome_proc = None
try:
    # Check if Chrome is already running on 9222
    ws_url = get_debug_url(DEBUG_PORT)
    if ws_url:
        print("Chrome already on port 9222")
    else:
        print("Starting Chrome...")
        chrome_proc = subprocess.Popen(
            [CHROME_EXE,
             f"--remote-debugging-port={DEBUG_PORT}",
             "--user-data-dir=" + PROFILE_DIR,
             "--profile-directory=jarsy_profile",
             "https://app.jarsy.com/layout/Home"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(6)
        ws_url = get_debug_url(DEBUG_PORT)
        if not ws_url:
            print("Chrome failed to start")
            sys.exit(1)
        print("Chrome started on port 9222")
except Exception as e:
    print(f"Launch error: {e}")
    sys.exit(1)

# ── Step 2: Connect via CDP and check/login ────────────────────────────────────
print("\nStep 2: Connecting to Chrome via CDP...")
import json

ws_url = get_debug_url(DEBUG_PORT)
print(f"WebSocket URL: {ws_url[:80]}...")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(ws_url, timeout=30000)
    ctx = browser.contexts[0]
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    
    print(f"Current URL: {page.url}")
    
    if is_pe_page(page):
        print("[OK] Already logged in!")
    else:
        print("\n=== NOT LOGGED IN ===")
        print("Please log in with email in the browser window.")
        print("Navigate to Private Equity page after logging in.")
        print("Waiting up to 10 minutes...")
        
        for i in range(120):
            time.sleep(5)
            try:
                if is_pe_page(page):
                    print(f"\n[LOGIN DETECTED at {i*5}s]")
                    break
                if i % 12 == 0:
                    print(f"  Still waiting... ({i*5}s) URL={page.url}")
            except Exception as e:
                print(f"  Error: {e}")
        else:
            print("Timeout!")
            browser.close()
            sys.exit(1)
    
    # Extra wait for session tokens
    print("\nWaiting 15s for session tokens to fully settle...")
    time.sleep(15)
    
    # Navigate to PE page
    print("Navigating to Private Equity...")
    page.goto("https://app.jarsy.com/layout/PrivateEquity", timeout=30000)
    page.wait_for_timeout(8000)
    
    # Check cookies
    all_cookies = ctx.cookies()
    jarsy = [c for c in all_cookies if "jarsy" in c.get("domain","") or "privy" in c.get("domain","")]
    print(f"\nCookies in browser ({len(all_cookies)} total, {len(jarsy)} Jarsy/Privy):")
    for c in jarsy:
        print(f"  {c['name']}: domain={c['domain']} httpOnly={c.get('httpOnly')} value={str(c['value'])[:60]}")
    
    # Check privy-token
    pt = next((c for c in jarsy if c["name"] == "privy-token"), None)
    ps = next((c for c in jarsy if c["name"] == "privy-session"), None)
    print(f"\nprivy-token: {'FOUND (len=' + str(len(str(pt.get('value','')))) + ')' if pt else 'MISSING'}")
    print(f"privy-session: value={str(ps.get('value','')[:20]) if ps else 'MISSING'}")
    
    # Save
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(all_cookies, f)
    print(f"\nSaved {len(all_cookies)} cookies to {COOKIE_FILE}")
    
    # Verify PE page
    if is_pe_page(page):
        print("PE page: LOGGED IN ✓")
    else:
        print("PE page: NOT logged in ⚠️")
    
    print("\nChrome left running on port 9222.")
    print("Run: python jarsy_extract.py to test extraction.")
    
    # Keep browser open
    print("\nKeeping browser open. Press Ctrl+C to close...")
    try:
        time.sleep(600)
    except KeyboardInterrupt:
        pass
    browser.close()

if chrome_proc:
    chrome_proc.terminate()
