"""
Jarsy Auth Script — One-time cookie extraction
===========================================
Run this ONCE to authenticate and save Jarsy session cookies.

Steps:
1. In your OpenClaw session, run: browser(action="start", profile="user")
2. Then navigate to: https://app.jarsy.com/layout/Home
3. Run this script: python jarsy_auth.py

The script uses CDP (via the browser tool's active connection) to extract
Jarsy cookies from your Chrome session and saves them to jarsy_cookies.json.

Alternative (without browser tool):
    python jarsy_auth.py --browser-auto
    (launches Chrome with --remote-debugging-port and automates it)
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarsy_cookies.json")
COOKIE_META_FILE = COOKIE_FILE.replace(".json", "_meta.json")


def save_cookies(cookies, email):
    """Save cookies to JSON file."""
    data = {
        "cookies": cookies,
        "email": email,
        "saved_at": time.time(),
    }
    with open(COOKIE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    meta = {
        "saved_at": time.time(),
        "email": email,
        "count": len(cookies),
    }
    with open(COOKIE_META_FILE, "w") as f:
        json.dump(meta, f)
    print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")


def load_cookies():
    """Load saved cookies."""
    if not os.path.exists(COOKIE_FILE):
        return None
    with open(COOKIE_FILE) as f:
        return json.load(f)


def is_fresh():
    """Check if saved cookies are < 25 days old."""
    if not os.path.exists(COOKIE_FILE):
        return False
    age_days = (time.time() - os.path.getmtime(COOKIE_FILE)) / 86400
    return age_days < 25


def get_cookie_age():
    """Return cookie age in days or None."""
    if not os.path.exists(COOKIE_FILE):
        return None
    return (time.time() - os.path.getmtime(COOKIE_FILE)) / 86400


# ─────────────────────────────────────────────────────────────────────────────
# Method 1: Playwright + Chrome profile (works when Chrome is NOT running)
# ─────────────────────────────────────────────────────────────────────────────

def auth_via_playwright_chrome(email, timeout=120):
    """
    Copy Chrome profile to a temp dir, launch Chrome with debugging enabled,
    navigate to Jarsy, extract cookies, close, cleanup.

    Works even if Chrome is already running (uses a profile copy).
    """
    import shutil
    from playwright.sync_api import sync_playwright

    chrome_exe = os.path.join(os.environ["PROGRAMFILES"], "Google", "Chrome", "Application", "chrome.exe")
    if not os.path.exists(chrome_exe):
        chrome_exe = os.path.join(os.environ["PROGRAMFILES(X86)"], "Google", "Chrome", "Application", "chrome.exe")

    default_profile = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data", "Default")

    # Copy profile to temp dir
    tmpdir = tempfile.mkdtemp(prefix="jarsy_chrome_")
    tmp_profile = os.path.join(tmpdir, "ChromeProfile")
    print(f"Copying Chrome profile to temp dir...")
    try:
        shutil.copytree(default_profile, tmp_profile, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("Cache*", "Code Cache*", "GPUCache*",
                                                      "ShaderCache*", "DawnCache*", "GrShaderCache*",
                                                      "Network*", "Sessions*", "Session Storage*",
                                                      "Service Worker*", "blob_storage*"))
    except Exception as e:
        print(f"Profile copy error (non-critical): {e}")

    with sync_playwright() as pw:
        context = None
        try:
            print("Launching Chrome with copied profile...")
            context = pw.chromium.launch_persistent_context(
                user_data_dir=tmp_profile,
                channel="chrome",
                headless=False,
                viewport={"width": 1280, "height": 800},
                args=["--disable-blink-features=AutomationControlled"],
            )

            page = context.pages[0] if context.pages else context.new_page()
            print("Navigating to Jarsy...")
            page.goto("https://app.jarsy.com/layout/Home", wait_until="networkidle", timeout=timeout * 1000)
            time.sleep(3)

            if "login" in page.url.lower():
                print("Login required — complete in browser window...")
                page.wait_for_url(
                    lambda url: "app.jarsy.com" in url and "login" not in url.lower(),
                    timeout=timeout * 1000,
                )
                time.sleep(3)

            print(f"Logged in: {page.url}")
            cookies = context.cookies()
            jarsy = [c for c in cookies if "jarsy" in c.get("domain", "").lower()]
            print(f"Got {len(jarsy)} Jarsy cookies")
            if jarsy:
                save_cookies(jarsy, email)
                return True
            return False

        except Exception as e:
            print(f"Error: {e}")
            return False
        finally:
            if context:
                context.close()
        # Cleanup temp profile
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Method 2: Launch Chrome with debugging port (if Chrome is closed)
# ─────────────────────────────────────────────────────────────────────────────

def auth_via_debug_port(email, timeout=120):
    """
    Launch Chrome with --remote-debugging-port, wait for CDP, navigate to Jarsy,
    get cookies, close Chrome.
    """
    import socket
    import websocket

    def find_free_port():
        with socket.socket() as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    port = find_free_port()
    chrome_exe = os.path.join(os.environ["PROGRAMFILES"], "Google", "Chrome", "Application", "chrome.exe")
    user_data = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data")

    print(f"Launching Chrome on debug port {port}...")
    proc = subprocess.Popen(
        [
            chrome_exe,
            f"--remote-debugging-port={port}",
            "--user-data-dir=" + user_data,
            "--profile-directory=Default",
            "https://app.jarsy.com/layout/Home",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    time.sleep(8)

    try:
        import urllib.request

        # Wait for CDP endpoint
        for attempt in range(15):
            try:
                req = urllib.request.urlopen(f"http://localhost:{port}/json", timeout=3)
                tabs = json.loads(req.read())
                if tabs:
                    break
            except Exception:
                time.sleep(1)
        else:
            print("Chrome didn't start with debug port")
            return False

        # Find Jarsy tab
        jarsy_tab = None
        for tab in tabs:
            if "jarsy" in tab.get("url", "").lower():
                jarsy_tab = tab
                break
        if not jarsy_tab:
            jarsy_tab = tabs[0]

        ws_url = jarsy_tab.get("webSocketDebuggerUrl")
        if not ws_url:
            print("No CDP websocket URL")
            return False

        print(f"Connecting to CDP: {jarsy_tab.get('url', '')[:60]}")
        ws = websocket.create_connection(ws_url, timeout=15)
        msg_id = [0]

        def cdp_send(method, params=None):
            msg_id[0] += 1
            cmd = {"id": msg_id[0], "method": method}
            if params:
                cmd["params"] = params
            ws.send(json.dumps(cmd))
            resp = json.loads(ws.recv())
            return resp.get("result", {})

        # Wait for navigation
        time.sleep(5)

        # Get cookies
        result = cdp_send("Network.getAllCookies")
        all_cookies = result.get("cookies", [])
        ws.close()

        jarsy_cookies = [c for c in all_cookies if "jarsy" in c.get("domain", "").lower()]
        print(f"Got {len(jarsy_cookies)} Jarsy cookies out of {len(all_cookies)} total")

        if jarsy_cookies:
            save_cookies(jarsy_cookies, email)
            return True
        return False

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def main():
    parser = argparse.ArgumentParser(description="Jarsy auth — save session cookies")
    parser.add_argument("--email", default="shaowei_l@hotmail.com")
    parser.add_argument("--check", action="store_true", help="Check cookie freshness only")
    parser.add_argument("--force", action="store_true", help="Force re-auth")
    parser.add_argument(
        "--method",
        choices=["auto", "playwright", "debug"],
        default="auto",
        help="Auth method",
    )
    args = parser.parse_args()

    print("=" * 50)
    print("Jarsy Auth")
    print("=" * 50)

    if args.check:
        age = get_cookie_age()
        if age is None:
            print("No cookie file found")
        elif is_fresh():
            print(f"Cookies fresh: {age:.1f} days old")
            with open(COOKIE_META_FILE) as f:
                meta = json.load(f)
            print(f"  {meta.get('count', '?')} cookies, email={meta.get('email', '?')}")
        else:
            print(f"Cookies stale: {age:.1f} days old — re-auth needed")
        return

    if not args.force and is_fresh():
        print("Cookies are fresh. Run with --force to re-authenticate.")
        return

    email = args.email
    success = False

    if args.method == "playwright" or args.method == "auto":
        print("Method: Playwright + Chrome profile copy...")
        success = auth_via_playwright_chrome(email)

    if not success and args.method in ("debug", "auto"):
        print("Method: Chrome debug port...")
        success = auth_via_debug_port(email)

    if success:
        print("Auth successful!")
    else:
        print("❌ Auth failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
