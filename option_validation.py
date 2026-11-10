"""Validation for option symbols before they are quoted.

Why this exists
---------------
`letter_position_tracker.py` builds an OCC-style Yahoo symbol by string
concatenation:

    f"{ticker.upper()}{exp:%y%m%d}{'C'|'P'}{int(strike*1000):08d}"

Nothing in that string construction proves the ticker is a real, tradeable
underlying, that the expiry is a real option expiry, or that the strike
exists. A typo'd ticker, a letter tickers-parsed-as-date, or a strike that
was never listed can therefore produce a *different, valid-looking* symbol
that Yahoo will happily quote - and the tracker would record a price for an
option that was never part of the letter.

The rule here is: never trust a composed symbol. Validate the components,
then confirm the exact strike exists in that ticker's real option chain for
that expiry. Only then is the symbol allowed to be quoted.

Validation order (cheapest first, network last):
  1. syntax      - ticker shape, expiry shape, strike range, option type
  2. calendar    - expiry is a weekday, in a sane window relative to the letter
  3. chain       - the exact strike exists in the ticker's chain for that expiry

All failures return a human-readable reason so the tracker can log *why* a
position could not be priced instead of silently reporting n/a.
"""

import re
from datetime import date, datetime, timedelta

try:
    from cboe_chain import cboe_contract
except Exception:  # pragma: no cover - CBOE helper optional
    cboe_contract = None

# US equity tickers: 1-5 letters, optionally with a class suffix (BRK.B).
_TICKER_RE = re.compile(r"^[A-Z]{1,5}(?:[.-][A-Z]{1,2})?$")

# The longest expiry Yahoo will accept for a standard option symbol.
_MAX_OPTION_TENOR_DAYS = 1095  # 3 years

# OCC strike field is 8 digits of strike*1000 -> max representable strike.
_MAX_STRIKE = 9999.99

# Option expiries do not fall on weekends.
_EXPIRY_WEEKDAYS = {0, 1, 2, 3, 4}

# Valid option type strings used across the letter tables.
_OPTION_TYPES = {"call", "put"}


def normalize_ticker(ticker):
    """Uppercase and strip a ticker, returning '' for junk input."""
    if ticker is None:
        return ""
    return str(ticker).strip().upper()


def validate_ticker(ticker):
    """Validate ticker syntax. Returns (ok, reason)."""
    t = normalize_ticker(ticker)
    if not t:
        return False, "empty ticker"
    if len(t) > 7:
        return False, f"ticker too long: {t!r}"
    if not _TICKER_RE.match(t):
        return False, f"ticker is not a valid symbol: {t!r}"
    # A bare single letter is very likely a mis-parse (e.g. a date fragment
    # like "A" from "2026-09-06" split on a separator). Reject it.
    if len(t) == 1:
        return False, f"single-letter ticker is likely mis-parsed: {t!r}"
    return True, ""


def validate_option_type(otype):
    """Validate the option type. Returns (ok, reason)."""
    if otype is None:
        return False, "missing option type"
    o = str(otype).strip().lower()
    if o not in _OPTION_TYPES:
        return False, f"option type must be call or put, got {otype!r}"
    return True, ""


def validate_strike(strike):
    """Validate the strike price. Returns (ok, reason)."""
    try:
        s = float(strike)
    except (TypeError, ValueError):
        return False, f"strike is not numeric: {strike!r}"
    if s != s or s in (float("inf"), float("-inf")):
        return False, "strike is not a finite number"
    if s <= 0:
        return False, f"strike must be positive, got {s}"
    if s > _MAX_STRIKE:
        return False, f"strike {s} exceeds OCC 8-digit encoding limit"
    return True, ""


def validate_expiry(expiration, letter_date=None, today=None):
    """Validate an option expiry date.

    Checks that the expiry is a real date, lands on a weekday (option
    expirations never do), and sits inside a sane window relative to the
    letter date (and to today, so a stale letter is not quoted forward).

    Returns (ok, reason).
    """
    if expiration is None:
        return False, "missing expiration"

    if isinstance(expiration, str):
        try:
            expiration = datetime.strptime(expiration.strip(), "%Y-%m-%d").date()
        except ValueError:
            return False, f"expiration is not a parseable date: {expiration!r}"
    elif isinstance(expiration, datetime):
        expiration = expiration.date()
    elif not isinstance(expiration, date):
        return False, f"expiration is not a date: {expiration!r}"

    if expiration.weekday() not in _EXPIRY_WEEKDAYS:
        return False, f"expiration {expiration} falls on a weekend"

    if letter_date is not None:
        if isinstance(letter_date, datetime):
            letter_date = letter_date.date()
        if expiration <= letter_date:
            return False, (
                f"expiration {expiration} is not after letter date {letter_date}"
            )
        tenor = (expiration - letter_date).days
        if tenor > _MAX_OPTION_TENOR_DAYS:
            return False, (
                f"expiration {expiration} is {tenor} days after letter date "
                f"{letter_date} (max {_MAX_OPTION_TENOR_DAYS})"
            )

    if today is not None:
        if isinstance(today, datetime):
            today = today.date()
        # Allow a short grace period: quotes can still be pulled for a few
        # days after expiry, but not months later.
        if (today - expiration).days > 30:
            return False, (
                f"expiration {expiration} is more than 30 days before {today} "
                "(stale position)"
            )

    return True, ""


def occ_symbol(ticker, strike, expiration, otype):
    """Build the OCC-style Yahoo symbol. Assumes the parts are already valid."""
    t = normalize_ticker(ticker)
    if isinstance(expiration, datetime):
        expiration = expiration.date()
    code = "C" if str(otype).strip().lower() == "call" else "P"
    return f"{t}{expiration:%y%m%d}{code}{int(round(float(strike) * 1000)):08d}"


def _chain_cache():
    """Process-local cache of option chains, keyed by (ticker, expiry).

    The tracker validates every open position on every run, and loading a
    chain is a network round-trip. Several positions commonly share a ticker
    and expiry, so cache the loaded chain and reuse it.
    """
    cache = getattr(_chain_cache, "_store", None)
    if cache is None:
        cache = {}
        _chain_cache._store = cache
    return cache


def load_chain(yf, ticker, expiration):
    """Load (calls, puts) for a ticker/expiry, with caching.

    Returns (calls, puts, error). On error, calls/puts are None.
    """
    t = normalize_ticker(ticker)
    if isinstance(expiration, datetime):
        expiration = expiration.date()
    key = (t, expiration)
    cache = _chain_cache()
    if key in cache:
        return cache[key]

    try:
        # yfinance compares against Ticker.options, which is a list of
        # ISO-format *strings*. Passing a date object never matches, even
        # for a valid expiry, so always pass the string form.
        chain = yf.Ticker(t).option_chain(date=expiration.isoformat())
        result = (chain.calls, chain.puts, None)
    except Exception as e:
        result = (None, None, str(e))

    cache[key] = result
    return result


def validate_against_chain(yf, ticker, strike, expiration, otype):
    """Confirm the exact strike exists in the ticker's real option chain.

    This is the guard that stops an unrelated Yahoo symbol from being
    accepted: if the composed symbol does not correspond to a listed strike
    for this ticker and expiry, the symbol is wrong no matter what Yahoo
    returns for it.

    Returns (ok, reason).
    """
    t = normalize_ticker(ticker)
    if isinstance(expiration, datetime):
        expiration = expiration.date()

    calls, puts, err = load_chain(yf, t, expiration)
    if err is not None:
        return False, f"could not load option chain for {t} {expiration}: {err}"

    is_call = str(otype).strip().lower() == "call"
    table = calls if is_call else puts
    if table is None or len(table) == 0:
        kind = "call" if is_call else "put"
        return False, f"no {kind} chain for {t} {expiration}"

    target = float(strike)
    for listed in table["strike"]:
        try:
            if abs(float(listed) - target) < 0.005:
                return True, ""
        except (TypeError, ValueError):
            continue

    available = sorted({round(float(x), 2) for x in table["strike"]})

    # yfinance's chain is NOT complete. It silently omits strikes that are
    # listed and trading elsewhere (e.g. OKTA 2026-11-13 $157.50 call: live
    # on CBOE with 22 OI, absent from yfinance's call chain). Before calling a
    # contract invalid, confirm against the full CBOE chain. A contract that
    # neither source lists really is invalid.
    if cboe_contract is not None:
        try:
            if cboe_contract(t, expiration, target, is_call):
                return True, ""
        except Exception:
            pass

    shown = ", ".join(str(x) for x in available[:12])
    return False, (
        f"strike {target} is not listed for {t} {expiration} "
        f"(yfinance listed: {shown}{'...' if len(available) > 12 else ''})"
    )


def validate_option(yf, ticker, strike, expiration, otype,
                    letter_date=None, today=None, check_chain=True):
    """Full validation of an option contract.

    Returns (ok, reason, symbol). ``symbol`` is the composed OCC symbol and
    is only meaningful when ok is True.
    """
    ok, reason = validate_ticker(ticker)
    if not ok:
        return False, reason, None

    ok, reason = validate_option_type(otype)
    if not ok:
        return False, reason, None

    ok, reason = validate_strike(strike)
    if not ok:
        return False, reason, None

    ok, reason = validate_expiry(expiration, letter_date=letter_date, today=today)
    if not ok:
        return False, reason, None

    if check_chain:
        ok, reason = validate_against_chain(yf, ticker, strike, expiration, otype)
        if not ok:
            return False, reason, None

    return True, "", occ_symbol(ticker, strike, expiration, otype)


if __name__ == "__main__":
    # Self-test of the offline checks (no network).
    cases = [
        (validate_ticker("NVDA"), True),
        (validate_ticker("A"), False),
        (validate_ticker("TOOLONGTICKER"), False),
        (validate_ticker(""), False),
        (validate_option_type("call"), True),
        (validate_option_type("CALL"), True),
        (validate_option_type("c"), False),
        (validate_strike(240.0), True),
        (validate_strike(0), False),
        (validate_strike(-5), False),
        (validate_strike("abc"), False),
        (validate_expiry(date(2026, 10, 9), letter_date=date(2026, 10, 4)), True),
        (validate_expiry(date(2026, 10, 10), letter_date=date(2026, 10, 4)), False),
        (validate_expiry(date(2026, 10, 9), letter_date=date(2026, 10, 9)), False),
        (validate_expiry(date(2026, 9, 12), letter_date=date(2026, 10, 4)), False),
        (validate_expiry(date(2026, 10, 11), letter_date=date(2026, 10, 4)), False),
        (validate_expiry(date(2030, 10, 9), letter_date=date(2026, 10, 4)), False),
    ]
    failures = 0
    for (ok, reason), expected in cases:
        status = "OK  " if ok == expected else "FAIL"
        if ok != expected:
            failures += 1
        print(f"  [{status}] {reason or 'valid'}")

    # Expiry format must round-trip through the symbol builder.
    sym = occ_symbol("nvda", 240.0, date(2026, 10, 9), "put")
    print(f"\n  symbol: {sym}")
    if sym != "NVDA261009P00240000":
        failures += 1
        print("  [FAIL] symbol construction")

    print(f"\n{'ALL PASS' if not failures else f'{failures} FAILURE(S)'}")
    raise SystemExit(1 if failures else 0)
