"""
Jarsy Login Helper - Opens browser for user to log in, saves cookies.
User manually logs into Jarsy, script saves cookies when page shows "Private Equity" content.
"""
import pickle, time
from playwright.sync_api import sync_playwright

PROFILE_DIR = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_profile"
COOKIE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_cookies.pkl"

print("Starting browser...")
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
        viewport={"width": 1400, "height": 900},
        timeout=30000
    )
    page = ctx.pages[0]
    page.goto("https://app.jarsy.com/layout/Home", timeout=20000)
    page.wait_for_timeout(3000)

    print(f"Browser opened at: {page.url}")
    print("Please log into Jarsy with Google in the browser window.")
    print("After logging in, navigate to Private Equity page.")
    print("This script will detect login and save cookies automatically.")
    print("Waiting up to 10 minutes...")

    # Wait for login by watching for PE page content
    for i in range(120):  # 120 * 5s = 10 min
        time.sleep(5)
        try:
            url = page.url
            body = page.inner_text("body")
            # Check if we're on PE page (indicates successful login)
            if "Private Equity Live" in body or "Private Equity Presale" in body:
                print(f"\n[LOGIN DETECTED at {i*5}s]")
                break
            if i % 12 == 0:  # Print every minute
                print(f"  Still waiting... ({i*5}s) URL={url}")
        except Exception as e:
            print(f"  Error: {e}")
    else:
        print("Timeout!")
        ctx.close()
        exit(1)

    # Save cookies
    cookies = ctx.cookies()
    with open(COOKIE_FILE, "wb") as f:
        pickle.dump(cookies, f)
    print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")

    # Test extraction
    page.get_by_text("Private Equity Live").click()
    page.wait_for_timeout(3000)
    page.get_by_text("Private Equity Presale").click()
    page.wait_for_timeout(2000)
    body = page.inner_text("body")
    presale_count = body.count("- Jarsy")
    print(f"Presale tokens visible: {presale_count}")

    ctx.close()
    print("Done!")
