"""
Jarsy Launch and Login - Persistent Context with Debug Port
=========================================================
Launches Chrome with jarsy_profile via persistent_context.
After user logs in and PE page is loaded, saves cookies.
Browser stays running on port 9223 for extraction step.
"""
import pickle, time, subprocess
from playwright.sync_api import sync_playwright

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = r"C:\Users\shaowei_l\AppData\Local\Google\Chrome\User Data\jarsy_profile"
COOKIE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_cookies.pkl"
DEBUG_PORT = 9223
PE_URL = "https://app.jarsy.com/layout/PrivateEquity"


def is_pe_page(page):
    try:
        return "Private Equity Live" in page.inner_text("body") or "Private Equity Presale" in page.inner_text("body")
    except Exception:
        return False


with sync_playwright() as p:
    print("Launching Chrome with jarsy_profile on debug port 9223...")
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        viewport={"width": 1400, "height": 900},
        timeout=30000,
        args=[f"--remote-debugging-port={DEBUG_PORT}"],
    )
    page = ctx.pages[0]
    
    # Navigate to Jarsy
    print("Navigating to Jarsy...")
    page.goto("https://app.jarsy.com/layout/Home", timeout=20000)
    page.wait_for_timeout(3000)
    print(f"URL: {page.url}")
    
    if is_pe_page(page):
        print("[OK] Already logged in!")
    else:
        print("\n=== NOT LOGGED IN ===")
        print("Log in with email, then navigate to Private Equity page.")
        print("Waiting up to 10 minutes...")
        for i in range(120):
            time.sleep(5)
            try:
                if is_pe_page(page):
                    print(f"\n[LOGIN DETECTED at {i*5}s]")
                    break
                if i % 12 == 0:
                    print(f"  Still waiting... ({i*5}s)")
            except Exception:
                pass
        else:
            print("Timeout!")
            ctx.close()
            exit(1)
    
    # Wait for session tokens to fully settle
    print("Waiting 15s for session tokens...")
    time.sleep(15)
    
    # Save cookies
    cookies = ctx.cookies()
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(cookies, f)
    print(f"Saved {len(cookies)} cookies")
    
    # Verify on PE page
    if is_pe_page(page):
        print("PE page: LOGGED IN")
    else:
        print("PE page: NOT logged in")
    
    print(f"\nBrowser running on debug port {DEBUG_PORT}")
    print("Run: python jarsy_extract.py to test extraction")
    
    try:
        time.sleep(600)
    except KeyboardInterrupt:
        pass
    ctx.close()
