"""
Jarsy Launch and Login — Fully Automated
=========================================
Launches Chrome with jarsy_profile, logs in via Google OAuth if needed.
Reuses existing session if already logged in.
Returns (success: bool, message: str)
"""
import json, os, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright

# ── Config ──────────────────────────────────────────────────────────────────
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
JARSY_PROFILE = r"C:\Users\shaowei_l\AppData\Local\Google\Chrome\User Data\jarsy_profile"
DEBUG_PORT = 9222
JARSY_URL = "https://app.jarsy.com/layout/Home"
PE_URL = "https://app.jarsy.com/layout/PrivateEquity"
EMAIL = "shaowei.liu@gmail.com"
PASSWORD = os.environ.get("JARSY_PASSWORD", "")  # Set as Windows env var
# ─────────────────────────────────────────────────────────────────────────────

def find_free_port(start=9222):
    for port in range(start, start + 10):
        try:
            with socket.socket() as s:
                s.bind(("", port))
                return port
        except OSError:
            continue
    raise RuntimeError("No free port found")


def is_chrome_running(port):
    """Check if Chrome is running with debug port."""
    try:
        import urllib.request
        req = urllib.request.urlopen(f"http://localhost:{port}/json", timeout=3)
        tabs = json.loads(req.read())
        return len(tabs) >= 0  # Chrome is running
    except Exception:
        return False


def wait_for_jarsy_tab(port, timeout=20):
    """Wait for a Jarsy tab to appear in Chrome."""
    import urllib.request
    for _ in range(timeout):
        try:
            req = urllib.request.urlopen(f"http://localhost:{port}/json", timeout=3)
            tabs = json.loads(req.read())
            for tab in tabs:
                if "jarsy" in tab.get("url", "").lower():
                    return True
        except Exception:
            pass
        time.sleep(1)
    return False


def is_logged_in(page):
    """Check if page shows Private Equity content (logged in)."""
    try:
        text = page.inner_text("body")
        return "Private Equity Live" in text or "Private Equity Presale" in text
    except Exception:
        return False


def is_login_modal(page):
    """Check if page shows a login modal."""
    try:
        text = page.inner_text("body")[:500]
        return "log in" in text.lower() or "sign in" in text.lower()
    except Exception:
        return False


def auto_login_google(page, timeout=60):
    """
    Attempt fully-automated Google OAuth login.
    Returns True if login succeeded (PE content visible), False otherwise.
    Falls back gracefully if Google blocks automation.
    """
    if not PASSWORD:
        print("  JARSY_PASSWORD env var not set — cannot auto-login")
        return False

    try:
        # Look for Google sign-in button
        google_buttons = [
            page.get_by_text("Sign in with Google"),
            page.get_by_text("Continue with Google"),
            page.locator('button:has-text("Google")'),
        ]
        btn = None
        for b in google_buttons:
            try:
                if b.is_visible(timeout=2000):
                    btn = b
                    break
            except Exception:
                pass

        if not btn:
            print("  No Google sign-in button found")
            return False

        print("  Clicking Google sign-in button...")
        btn.click()

        # Wait for popup / navigation
        time.sleep(3)

        # Handle all open pages (main + popup)
        all_pages = page.context.pages
        oauth_page = None
        for p in all_pages:
            try:
                url = p.url.lower()
                if "accounts.google.com" in url or "oauth" in url:
                    oauth_page = p
                    break
            except Exception:
                pass

        if not oauth_page:
            # Maybe it navigated within same page
            print("  Waiting for Google OAuth page...")
            time.sleep(3)
            all_pages = page.context.pages
            for p in all_pages:
                try:
                    if "accounts.google.com" in p.url:
                        oauth_page = p
                        break
                except Exception:
                    pass

        if oauth_page:
            print("  On OAuth page — entering email...")
            # Enter email
            email_field = oauth_page.locator('input[type="email"], input[name="identifier"]')
            email_field.fill(EMAIL)
            oauth_page.locator('div[id="identifierNext"], button:has-text("Next")').first.click()
            time.sleep(3)

            print("  Entering password...")
            pw_field = oauth_page.locator('input[type="password"]')
            pw_field.fill(PASSWORD)
            oauth_page.locator('div[id="passwordNext"], button:has-text("Next")').first.click()
            time.sleep(5)

            # Handle "Choose an account" screen if it appears
            for p in page.context.pages:
                try:
                    if "accounts.google.com" in p.url:
                        accounts_text = p.inner_text("body")[:300]
                        if EMAIL in accounts_text:
                            # Click the matching account
                            p.get_by_text(EMAIL).click()
                            time.sleep(3)
                            break
                except Exception:
                    pass

        # Wait for login to complete — look for PE content
        print(f"  Waiting up to {timeout}s for PE content...")
        for remaining in range(timeout, 0, -5):
            try:
                page_text = page.inner_text("body")
                if "Private Equity Live" in page_text or "Private Equity Presale" in page_text:
                    print("  ✓ Login successful — PE content visible")
                    return True
            except Exception:
                pass
            time.sleep(5)

        # Check if we're on jarsy PE page now
        if "PrivateEquity" in page.url or is_logged_in(page):
            return True

        return False

    except Exception as e:
        print(f"  Auto-login error: {e}")
        return False


def launch_and_login():
    """Main entry point. Returns (success, message)."""
    port = DEBUG_PORT

    # ── Step 1: Check if Chrome is already running with Jarsy ───────────────
    if is_chrome_running(port):
        print(f"Chrome already running on port {port}")
        if wait_for_jarsy_tab(port, timeout=10):
            print("Jarsy tab found — checking login state...")

            # Connect and check
            with sync_playwright() as p:
                try:
                    browser = p.chromium.connect_over_cdp(f"http://localhost:{port}", timeout=10000)
                    ctx = browser.contexts[0]
                    page = ctx.pages[0] if ctx.pages else ctx.new_page()
                    page.goto(PE_URL, timeout=20000)
                    page.wait_for_timeout(5000)

                    if is_logged_in(page):
                        print("Already logged in — browser session is valid")
                        browser.close()
                        return True, "already_logged_in"
                    else:
                        print("Chrome running but not logged in — attempting auto-login...")
                        if auto_login_google(page, timeout=60):
                            browser.close()
                            return True, "auto_login_success"
                        browser.close()
                        return False, "login_required"
                except Exception as e:
                    print(f"Connect error: {e}")
                    # Fall through to re-launch

    # ── Step 2: Launch fresh Chrome with jarsy_profile ───────────────────
    print(f"Launching Chrome with jarsy_profile on port {port}...")
    profile_dir = JARSY_PROFILE

    proc = subprocess.Popen(
        [
            CHROME_EXE,
            f"--remote-debugging-port={port}",
            "--user-data-dir=" + profile_dir,
            "--profile-directory=jarsy_profile",
            JARSY_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("Waiting for Chrome to start...")
    time.sleep(8)

    if not is_chrome_running(port):
        print("Chrome failed to start!")
        return False, "chrome_start_failed"

    # ── Step 3: Connect and check login state ─────────────────────────────
    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(f"http://localhost:{port}", timeout=15000)
        except Exception as e:
            print(f"CDP connect failed: {e}")
            proc.terminate()
            return False, f"cdp_connect_failed: {e}"

        ctx = browser.contexts[0]
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        print("Navigating to Private Equity...")
        page.goto(PE_URL, timeout=30000)
        page.wait_for_timeout(8000)

        if is_logged_in(page):
            print("✓ Already logged in — session valid")
            # Keep Chrome running, just close playwright connection
            browser.close()
            return True, "already_logged_in"

        print("Not logged in — attempting Google OAuth auto-login...")
        if auto_login_google(page, timeout=60):
            browser.close()
            return True, "auto_login_success"

        print("✗ Auto-login failed or timed out")
        browser.close()

    # ── Step 4: Return failure info ───────────────────────────────────────
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    return False, "login_required"


if __name__ == "__main__":
    success, msg = launch_and_login()
    print(f"\nResult: success={success}, msg={msg}")
    if not success:
        sys.exit(1)
