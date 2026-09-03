"""
Jarsy CDP Auth Script
====================
Run this ONCE inside an OpenClaw agent session that has browser tool access.
It uses the browser with profile="user" to access your running Chrome,
extracts Jarsy session cookies via CDP, and saves them to jarsy_cookies.json.

Usage (inside OpenClaw agent):
    1. browser(action="start", profile="user")
    2. browser(action="navigate", url="https://app.jarsy.com/layout/Home")
    3. browser(action="act", kind="evaluate", fn="() => { window.__jarsyCookies = document.cookie; return document.cookie; }")
    4. python jarsy_cdp_auth.py --action save_from_browser
       OR just run this script and it will handle the browser interaction

More reliably — use the CDP API directly from browser console:
    Run in Chrome DevTools console on app.jarsy.com:
        copy(document.cookie)
    Then paste into a file or use below.

Simpler approach:
    python jarsy_cdp_auth.py --action quick_save
    (uses playwright with --remote-debugging-port to get cookies from running Chrome)
"""

import argparse
import json
import os
import subprocess
import sys
import time
import tempfile

COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarsy_cookies.json")


def save_cookie_metadata(cookies, email):
    """Save cookies + metadata to JSON."""
    data = {
        "cookies": cookies,
        "email": email,
        "saved_at": time.time(),
    }
    with open(COOKIE_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")
    meta = {
        "saved_at": time.time(),
        "email": email,
        "count": len(cookies),
    }
    with open(COOKIE_FILE.replace(".json", "_meta.json"), "w") as f:
        json.dump(meta, f)
    print("Metadata saved.")


def quick_save(email):
    """
    Launch Chrome with --remote-debugging-port, wait for CDP connection,
    navigate to Jarsy, extract cookies, save, close Chrome.
    Works without needing Chrome to already be running with debugging.
    """
    import socket

    # Find a free port
    def find_free_port():
        with socket.socket() as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    port = find_free_port()
    print(f"Using CDP port: {port}")

    # Launch Chrome with debugging enabled
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    chrome_exe = None
    for p in chrome_paths:
        if os.path.exists(p):
            chrome_exe = p
            break

    if not chrome_exe:
        print("Chrome not found!")
        return False

    user_data_dir = os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data")
    profile_dir = os.path.join(user_data_dir, "Default")

    print(f"Launching Chrome with --remote-debugging-port={port}...")
    proc = subprocess.Popen(
        [
            chrome_exe,
            f"--remote-debugging-port={port}",
            "--user-data-dir=" + user_data_dir,
            "--profile-directory=Default",
            "https://app.jarsy.com/layout/Home",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for Chrome to start and CDP to be ready
    time.sleep(8)

    try:
        import urllib.request

        # Wait for CDP endpoint
        for attempt in range(20):
            try:
                req = urllib.request.urlopen(f"http://localhost:{port}/json", timeout=3)
                tabs = json.loads(req.read())
                if tabs:
                    print(f"Chrome ready! {len(tabs)} tabs")
                    break
            except Exception:
                time.sleep(1)
        else:
            print("Chrome didn't start in time")
            return False

        # Find Jarsy tab
        jarsy_tab = None
        for tab in tabs:
            if "jarsy" in tab.get("url", "").lower():
                jarsy_tab = tab
                break

        if not jarsy_tab:
            print("No Jarsy tab found — opening it")
            # Use first tab
            jarsy_tab = tabs[0]
            ws_url = jarsy_tab.get("webSocketDebuggerUrl")

            # Navigate to Jarsy via CDP
            import websocket

            ws = websocket.create_connection(ws_url, timeout=10)
            msg_id = [0]

            def cdp_send(method, params=None):
                msg_id[0] += 1
                cmd = {"id": msg_id[0], "method": method}
                if params:
                    cmd["params"] = params
                ws.send(json.dumps(cmd))
                resp = json.loads(ws.recv())
                return resp.get("result", {})

            # Navigate
            cdp_send("Page.navigate", {"url": "https://app.jarsy.com/layout/Home"})
            time.sleep(5)

            # Refresh tabs
            req = urllib.request.urlopen(f"http://localhost:{port}/json", timeout=3)
            tabs = json.loads(req.read())
            for tab in tabs:
                if "jarsy" in tab.get("url", "").lower():
                    jarsy_tab = tab
                    break

        ws_url = jarsy_tab.get("webSocketDebuggerUrl")
        print(f"Jarsy tab: {jarsy_tab.get('url', '')[:80]}")

        # Connect via CDP WebSocket
        import websocket

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

        # Get all cookies
        print("Getting cookies...")
        result = cdp_send("Network.getAllCookies")
        all_cookies = result.get("cookies", [])
        ws.close()

        # Filter to Jarsy cookies
        jarsy_cookies = []
        for c in all_cookies:
            domain = c.get("domain", "")
            if "jarsy" in domain.lower():
                jarsy_cookies.append(c)

        print(f"Total cookies: {len(all_cookies)}, Jarsy: {len(jarsy_cookies)}")

        if jarsy_cookies:
            save_cookie_metadata(jarsy_cookies, email)
            print("✅ Done!")
            return True
        else:
            print("❌ No Jarsy cookies found")
            return False

    finally:
        # Kill Chrome
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="Jarsy CDP Auth")
    parser.add_argument("--action", choices=["quick_save", "check"], default="quick_save")
    parser.add_argument("--email", default="shaowei_l@hotmail.com")
    args = parser.parse_args()

    print("=" * 50)
    print("Jarsy CDP Auth")
    print("=" * 50)

    if args.action == "check":
        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE) as f:
                data = json.load(f)
            age = (time.time() - data.get("saved_at", 0)) / 86400
            print(f"Cookie file: {age:.1f} days old, {len(data.get('cookies', []))} cookies")
        else:
            print("No cookie file found")
        return

    print(f"Email: {args.email}")
    print("Starting Chrome with debugging enabled...")
    success = quick_save(args.email)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
