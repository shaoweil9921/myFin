"""
Jarsy Launch and Login - Cookie-Based Session
==============================================
Uses saved cookies from jarsy_cookies.pkl (captured from logged-in session).
Launches Chrome with jarsy_profile, injects cookies, navigates to Jarsy PE.
No manual login needed as long as cookies are fresh.
"""
import json, os, pickle, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright

# Config
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
JARSY_PROFILE = r"C:\Users\shaowei_l\AppData\Local\Google\Chrome\User Data\jarsy_profile"
DEBUG_PORT = 9222
COOKIE_FILE = r"C:\Users\shaowei_l\.openclaw\workspace\jarsy_cookies.pkl"
JARSY_URL = "https://app.jarsy.com/layout/Home"
PE_URL = "https://app.jarsy.com/layout/PrivateEquity"
COOKIE_MAX_AGE_DAYS = 25


def is_chrome_running(port):
    try:
        import urllib.request
        req = urllib.request.urlopen(f"http://localhost:{port}/json", timeout=3)
        json.loads(req.read())
        return True
    except Exception:
        return False


def cookie_age():
    """Return cookie file age in days, or None if no file."""
    if not os.path.exists(COOKIE_FILE):
        return None
    return (time.time() - os.path.getmtime(COOKIE_FILE)) / 86400


def load_cookies():
    with open(COOKIE_FILE, "rb") as f:
        return pickle.load(f)


def is_logged_in(page):
    try:
        text = page.inner_text("body")
        return "Private Equity Live" in text or "Private Equity Presale" in text
    except Exception:
        return False


def check_cookie_freshness():
    age = cookie_age()
    if age is None:
        return False, "no_cookie_file"
    if age > COOKIE_MAX_AGE_DAYS:
        return False, f"cookie_stale_{age:.0f}_days"
    return True, f"fresh_{age:.1f}_days"


def wait_for_pe_content(page, timeout=20):
    """Wait for PE tab content to load (tokens appear after JS render)."""
    start = time.time()
    while time.time() - start < timeout:
        if is_logged_in(page):
            return True
        time.sleep(2)
    return is_logged_in(page)


def launch_with_cookies():
    """
    Launch Chrome with jarsy_profile, inject cookies, navigate.
    Returns (success, message).
    """
    port = DEBUG_PORT

    # Check if Chrome already running on debug port
    reuse_chrome = is_chrome_running(port)
    if reuse_chrome:
        print(f"Chrome already on port {port} -- connecting...")
    else:
        print(f"Launching Chrome on port {port}...")
        proc = subprocess.Popen(
            [
                CHROME_EXE,
                f"--remote-debugging-port={port}",
                "--user-data-dir=" + JARSY_PROFILE,
                "--profile-directory=jarsy_profile",
                JARSY_URL,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(6)
        if not is_chrome_running(port):
            print("Chrome failed to start!")
            return False, "chrome_start_failed"

    # Load cookies
    try:
        cookies = load_cookies()
        print(f"Loaded {len(cookies)} cookies from {COOKIE_FILE}")
    except Exception as e:
        print(f"Could not load cookies: {e}")
        return False, "cookie_load_failed"

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}", timeout=20000)
        except Exception as e:
            print(f"CDP connect failed: {e}")
            return False, "cdp_connect_failed"

        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # Inject cookies before navigating
        print("Injecting cookies...")
        try:
            # Clear existing Jarsy cookies first
            existing = ctx.cookies()
            jarsy_domains = set()
            for c in existing:
                d = c.get("domain", "")
                if "jarsy" in d or "privy" in d or "cf" in d:
                    jarsy_domains.add(d)
            if jarsy_domains:
                ctx.clear_cookies()
        except Exception:
            pass

        # Add cookies to context
        ctx.add_cookies(cookies)
        print(f"Added {len(cookies)} cookies to context")

        # Navigate to PE page
        print("Navigating to Private Equity...")
        page.goto(PE_URL, timeout=30000)
        page.wait_for_timeout(5000)

        # Wait for PE content to appear (JS renders after page load)
        print("Waiting for PE content to render...")
        pe_ready = wait_for_pe_content(page, timeout=20)

        if pe_ready:
            token_count = page.inner_text("body").count("- Jarsy")
            print(f"[OK] Logged in -- {token_count} tokens visible")
            browser.close()
            return True, f"logged_in_{token_count}_tokens"

        # Try one more time with longer wait
        print("PE content not found -- trying longer wait...")
        page.wait_for_timeout(15000)
        pe_ready = is_logged_in(page)

        if pe_ready:
            token_count = page.inner_text("body").count("- Jarsy")
            print(f"[OK] Logged in after retry -- {token_count} tokens")
            browser.close()
            return True, f"logged_in_{token_count}_tokens"

        # Capture screenshot for debugging
        try:
            page.screenshot(path="jarsy_login_debug.png", full_page=True)
            print("Debug screenshot saved: jarsy_login_debug.png")
        except Exception:
            pass

        print("X Session cookies did not log in -- cookies may be expired")
        browser.close()
        return False, "cookie_login_failed"


def main():
    # Check cookie freshness
    fresh, age_msg = check_cookie_freshness()
    if not fresh:
        print(f"Cookie problem: {age_msg}")
        print("Run save_cookies.py after manual login to refresh session.")
        sys.exit(1)

    print(f"Cookies: {age_msg}")
    success, msg = launch_with_cookies()
    print(f"\nResult: success={success}, msg={msg}")
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
