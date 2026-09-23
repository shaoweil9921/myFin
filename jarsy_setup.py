"""
Jarsy Setup - Launch Playwright browser, user logs in, cookies saved.
Run ONCE: this opens a browser for you to log into Jarsy.
Cookies are saved to jarsy_cookies.json for cron job reuse.
"""
import json, pickle, base64
from playwright.sync_api import sync_playwright

COOKIE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_cookies.pkl"
PROFILE_DIR = r"C:\Users\shaowei_l\AppData\Local\Google\Chrome\User Data\jarsy_profile"

def save_cookies(ctx):
    """Save cookies from context to file"""
    cookies = ctx.cookies()
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(cookies, f)
    print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")
    for c in cookies:
        print(f"  {c['name']}: {c.get('value','')[:30]}...")

def load_cookies():
    """Load cookies from file"""
    with open(COOKIE_FILE, "rb") as f:
        return pickle.load(f)

with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        viewport={"width": 1400, "height": 900},
        timeout=30000
    )

    page = browser.pages[0] if browser.pages else browser.new_page()
    page.goto("https://app.jarsy.com/layout/Home", timeout=20000)
    page.wait_for_timeout(3000)

    print(f"Current URL: {page.url}")
    print(f"Title: {page.title()}")

    # Check if already logged in
    if "Log in" not in page.inner_text("body")[:500]:
        print("Already logged in!")
    else:
        print("\n=== NOT LOGGED IN ===")
        print("Please log into Jarsy in the browser window that opened.")
        print("Use Google login: shaowei.luo@gmail.com")
        print("\nAfter logging in, this script will save your cookies.")
        print("Press Enter here after you've logged in...")
        input()

    # Save cookies
    save_cookies(browser.context)

    # Verify we can access Private Equity
    page.goto("https://app.jarsy.com/layout/PrivateEquity", timeout=20000)
    page.wait_for_timeout(5000)
    print(f"\nPrivate Equity URL: {page.url}")
    text = page.inner_text("body")[:300]
    print(f"Page content: {text}")

    browser.close()
    print("\nDone! Cookies saved. Cron job can now use them.")
