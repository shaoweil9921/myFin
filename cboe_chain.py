"""CBOE delayed options chain helper.

Why this exists
---------------
yfinance's option chain is not complete: it silently omits listed strikes
(the OKTA 2026-11-13 $157.50 call is listed and trading on CBOE with 22
open interest, but yfinance's call chain jumps 152.5 -> 160.0). Any code
that treats the yfinance chain as the authoritative list of listed strikes
will therefore flag real contracts as invalid.

CBOE's delayed-quote payload is a full chain for the underlying:
    https://cdn.cboe.com/api/global/delayed_quotes/options/<SYM>.json

Usage:
    from cboe_chain import cboe_contract, cboe_quote

    q = cboe_quote("OKTA", "2026-11-13", 157.5, "call")
    # -> {"symbol": "OKTA261113C00157500", "bid": 19.8, "ask": 22.95, ...}
"""
import json
import re
import urllib.request

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_CBOE_URL = "https://cdn.cboe.com/api/global/delayed_quotes/options/%s.json"

# e.g. OKTA261113C00157500
_OCC_RE = re.compile(r"^[A-Z]+(\d{2})(\d{4})([CP])(\d{8})$")

_cache = {}


def _get(ticker):
    """Fetch (and cache) the raw CBOE payload for a ticker."""
    t = str(ticker).strip().upper()
    if t in _cache:
        return _cache[t]
    url = _CBOE_URL % t
    req = urllib.request.Request(url, headers=_HEADERS)
    try:
        payload = json.loads(
            urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        )
    except Exception:
        payload = None
    _cache[t] = payload
    return payload


def _parse(symbol):
    """OCC symbol -> (expiry_iso, right, strike) or None."""
    m = _OCC_RE.match(symbol or "")
    if not m:
        return None
    yy, mmdd, right, k = m.groups()
    return (f"20{yy}-{mmdd[:2]}-{mmdd[2:]}", right, int(k) / 1000.0)


def cboe_quote(ticker, expiration, strike, otype):
    """Quote one contract from the CBOE delayed chain.

    ``expiration`` may be a date, datetime, or "YYYY-MM-DD" string.
    Returns a dict with symbol/bid/ask/last/oi/volume, or None if the
    contract is not listed.
    """
    if hasattr(expiration, "strftime"):
        exp_iso = expiration.strftime("%Y-%m-%d")
    else:
        exp_iso = str(expiration)[:10]
    right = "C" if str(otype).strip().lower() == "call" else "P"
    target = float(strike)

    payload = _get(ticker)
    if not payload:
        return None
    for o in payload.get("data", {}).get("options", []):
        parsed = _parse(o.get("option"))
        if not parsed:
            continue
        e_iso, r, k = parsed
        if e_iso != exp_iso or r != right:
            continue
        if abs(k - target) > 0.005:
            continue
        return {
            "symbol": o.get("option"),
            "bid": float(o.get("bid") or 0),
            "ask": float(o.get("ask") or 0),
            "last": float(o.get("last_trade_price") or 0),
            "prev_day_close": float(o.get("prev_day_close") or 0),
            "open_interest": float(o.get("open_interest") or 0),
            "volume": float(o.get("volume") or 0),
            "spot": payload.get("data", {}).get("current_price"),
            "prev_close": payload.get("data", {}).get("prev_day_close"),
        }
    return None


def cboe_contract(ticker, expiration, strike, otype):
    """True if the exact contract is listed on CBOE."""
    return cboe_quote(ticker, expiration, strike, otype) is not None


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if len(args) == 4:
        print(json.dumps(cboe_quote(args[0], args[1], float(args[2]), args[3]), indent=2))
    else:
        print("usage: python cboe_chain.py TICKER YYYY-MM-DD STRIKE call|put")
