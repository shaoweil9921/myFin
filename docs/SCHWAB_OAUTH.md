# Schwab OAuth Re-authentication

**Status (as of 2026-09-23):** Refresh token is revoked. Full OAuth re-auth needed.

**Last checked:** 2026-09-23 11:45 PM ET

---

## The Problem

- Refresh token: `…nIDlANsFCv6takDqp1PWvtcqh7qlz…` (REVOKED)
- Access token: expired
- Refresh attempt returned: `invalid_grant` — token is invalid, expired, or revoked
- Re-auth required

## Credentials (still valid)

- **API Key:** `ydIVYBppTj7v8z3KnOfZngGgXNfSWswlwK4HwhVmfC1GURGn`
- **App Secret:** `wKuriHpjt5pGiAaZV04HO6VQxTyRNxzIj1ZHSMhBj6BAxkHXNv6LQ6whysY9A8MK`
- **Redirect URI:** `https://127.0.0.1:9876/schwab` (local server, NOT Tailscale)
- **Token file:** `C:\Users\shaowei_l\.schwab_tokens.json`

## Token URLs

- **Token endpoint:** `https://api.schwabapi.com/v1/oauth/token`
- **Auth endpoint:** `https://api.schwabapi.com/v1/oauth/authorize`
- **Note:** Path is `/oauth/` NOT `/oauth2/` (different from what you'd expect)

## OAuth Flow (manual)

### Step 1 — Start redirect server
```python
# Simple redirect server to catch the OAuth code
import http.server, urllib.parse, json, base64, requests, os

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if '/schwab' in self.path:
            params = urllib.parse.parse_qs(self.path.split('?')[1])
            code = params.get('code', [None])[0]
            print(f"CODE: {code}")
            # Exchange immediately
            creds = 'ydIVYBppTj7v8z3KnOfZngGgXNfSWswlwK4HwhVmfC1GURGn:wKuriHpjt5pGiAaZV04HO6VQxTyRNxzIj1ZHSMhBj6BAxkHXNv6LQ6whysY9A8MK'
            b64 = base64.b64encode(creds.encode()).decode()
            headers = {'Authorization': f'Basic {b64}', 'Content-Type': 'application/x-www-form-urlencoded'}
            payload = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': 'https://127.0.0.1:9876/schwab'}
            r = requests.post('https://api.schwabapi.com/v1/oauth/token', headers=headers, data=payload)
            tokens = r.json()
            with open(os.path.expanduser('~/.schwab_tokens.json'), 'w') as f:
                json.dump(tokens, f, indent=2)
            print(f"Status: {r.status_code}, tokens saved")
            self.send_response(200)
            self.wfile.write(b"OK - tokens saved. Close this tab.")
        else:
            self.send_response(404)

server = http.server.HTTPServer(('127.0.0.1', 9876), Handler)
print("Waiting for Schwab redirect...")
server.handle_request()
```

### Step 2 — Open auth URL in browser
```
https://api.schwabapi.com/v1/oauth/authorize?client_id=ydIVYBppTj7v8z3KnOfZngGgXNfSWswlwK4HwhVmfC1GURGn&redirect_uri=https%3A%2F%2F127.0.0.1%3A9876%2Fschwab&response_type=code
```

### Step 3 — Login and approve quickly
- Schwab redirects to `127.0.0.1:9876/schwab?code=XXX` 
- Server catches the code and exchanges it immediately
- Must be FAST — code expires in ~75 seconds

## Why It Failed Before

- Old redirect URI was `https://desktop-rntitap.tail4c8778.ts.net/schwab` (Tailscale)
- OpenClaw gateway intercepts Tailscale redirects → code captured by gateway, not the app
- Fixed by using `https://127.0.0.1:9876/schwab` as redirect URI

## Old Scripts (for reference)

Located in: `C:\Users\shaowei_l\Downloads\openclaw_workspace_20260405\`

- `schwab_oauth_manual.py` — the old manual OAuth script
- `schwab_refresh.py` — token refresh (works while refresh token valid)
- `schwab_api_monitor.py` — API health check
- `schwab_api.py` — main API wrapper

## Token File Format

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "Bearer",
  "expires_in": 1800,
  "scope": "...",
  "id_token": "..."
}
```

## Quick Test After Auth

```python
import requests, json
tokens = json.load(open(os.path.expanduser('~/.schwab_tokens.json')))
headers = {'Authorization': f"Bearer {tokens['access_token']}", 'Accept': 'application/json'}
r = requests.get('https://api.schwabapi.com/v1/marketdata/v1/quotes/SPY', headers=headers)
print(r.status_code, r.json())
```

## Priority

Medium — Schwab has real positions not on Alpaca. Worth re-auth if time allows.
