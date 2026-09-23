"""
Jarsy Login - Opens browser, waits for user to log in, saves cookies.
Launch with: python jarsy_login_wait.py
Then log into Jarsy in the browser. Script saves cookies when it detects login.
"""
import json, pickle, time, sys
from playwright.sync_api import sync_playwright

COOKIE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_cookies.pkl"
PROFILE_DIR = r"C:\Users\shaowei_l\AppData\Local\Google\Chrome\User Data\jarsy_profile"

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

    print(f"URL: {page.url}")
    print(f"Title: {page.title()}")

    # Wait up to 5 minutes for user to log in
    print("\n=== LOG IN NOW ===")
    print("Log into Jarsy in the browser window.")
    print("Using Google: shaowei.luo@gmail.com")
    print("Waiting up to 5 minutes...")

    for i in range(60):  # 60 * 5 sec = 5 min
        time.sleep(5)
        try:
            url = page.url
            text = page.inner_text("body")
            if "Log in" not in text[:300] and "log in" not in text[:300].lower():
                print(f"\n[+] Detected login at {i*5}s!")
                print(f"URL: {url}")
                break
            if i % 6 == 0:  # Print every 30s
                print(f"  ... still waiting ({i*5}s)")
        except:
            pass
    else:
        print("Timeout! No login detected.")
        browser.close()
        sys.exit(1)

    # Save cookies
    cookies = browser.context.cookies()
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(cookies, f)
    print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")

    # Verify PE page
    page.goto("https://app.jarsy.com/layout/PrivateEquity", timeout=20000)
    page.wait_for_timeout(5000)
    print(f"\nPrivate Equity URL: {page.url}")

    browser.close()
    print("Done! Cookies saved.")
