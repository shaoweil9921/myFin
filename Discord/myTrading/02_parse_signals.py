"""02_parse_signals.py - Extract trading signals from discord_message -> discord_trade_signal"""
import os, sys
import re
import uuid
import json
import psycopg2
import requests
import argparse
from datetime import datetime, date

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": os.environ.get("DB_PASSWORD", ""),
    "dbname": "fintech",
}

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
BASE_URL = "https://discord.com/api/v10"
HEADERS = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}


# ──────────────────────────────────────────────────────────────
# REGEX PATTERNS
# ──────────────────────────────────────────────────────────────

TICKER_RE = re.compile(r'\b([A-Z]{2,5})\b')
APPROX_RE = re.compile(r'~\s*\$?\s*([0-9,]+\.?[0-9]*)')

# Price extractors
def _price_pat(*keywords):
    kw = '|'.join(keywords)
    return re.compile(
        rf'(?:{kw})[:\s]*(?:at\s+)?\$?\s*([0-9,]+\.?[0-9]*)',
        re.IGNORECASE
    )

_ENTRY_RE   = _price_pat('entry', 'buy', 'purchase', 'entered?', 'got')
_TARGET_RE  = _price_pat('target', 'take profit', 'tp', 'profit')
_STOP_RE    = _price_pat('stop', 'stoploss', 'stop loss', 'sl', 'stopped')

# Option patterns
STRIKE_RE = re.compile(
    r'\b([0-9,]+\.?[0-9]*)\s*(?:strike|strike price|call|put)\b',
    re.IGNORECASE
)
EXPIRY_RE = re.compile(
    r'(?:exp(?:iry|iration)?|expires?|by)\s*[:.\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
    re.IGNORECASE
)
CONTRACT_RE = re.compile(
    r'(\d+)\s*(?:contract|contracts|opts?|options?)\b',
    re.IGNORECASE
)
PREMIUM_RE = re.compile(
    r'(?:premium|paid|cost|price)\s*[:\s]*\$?([0-9,]+\.?[0-9]*)',
    re.IGNORECASE
)
CALL_RE = re.compile(r'\bcall\b', re.IGNORECASE)
PUT_RE  = re.compile(r'\bput\b',  re.IGNORECASE)

# Strategy / direction
STRATEGY_RE = re.compile(
    r'\b(swing trade|swing|day trade|daytrade|options?|scalp|scalping|positional|momentum|breakout|cnt|iron condor|straddle|strangle)\b',
    re.IGNORECASE
)
DIRECTION_RE = re.compile(
    r'\b(long|short|bullish|bull|bearish|bear|buy|call|put|sell)\b',
    re.IGNORECASE
)

# Common words that look like tickers
COMMON_WORDS = {
    'THE', 'AND', 'FOR', 'NOT', 'ARE', 'BUT', 'YOU', 'ALL', 'CAN', 'HAD',
    'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY', 'GET', 'HAS', 'HIM', 'HIS',
    'HOW', 'ITS', 'MAY', 'NEW', 'NOW', 'OLD', 'SEE', 'WAY', 'WHO', 'BOY',
    'DID', 'GOT', 'OMG', 'LOL', 'IDK', 'FYI', 'ETA', 'CEO', 'IPO', 'FDA',
    'USA', 'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'GDP', 'CPI', 'PPI',
    'FED', 'SEC', 'FTC', 'EPA', 'HSA', 'IRA', '401K', 'ROI', 'YTD', 'MTD',
    'QTD', 'YOY', 'MOIC', 'HIGH', 'LOW', 'NEWS', 'CALL', 'PUT', 'OPEN',
    'CLOSE', 'STOP', 'NEXT', 'THIS', 'THAT', 'WITH', 'FROM', 'HAVE', 'MORE',
    'THAN', 'INTO', 'YEAR', 'MOST', 'JUST', 'OVER', 'ALSO', 'SOME', 'LIKE',
    'GOOGL', 'GOOG', 'AMZN', 'META', 'TSLA', 'NVDA', 'MSFT', 'AAPL',
}


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r'<@!?\d+>', '', text)
    text = re.sub(r'<#\d+>', '', text)
    text = re.sub(r'<@&\d+>', '', text)
    text = re.sub(r'<:[a-zA-Z0-9_]+:\d+>', '', text)
    text = re.sub(r':[a-zA-Z0-9_]+:', '', text)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'_+', '', text)
    text = re.sub(r'~~+', '', text)
    text = re.sub(r'\n+', ' ', text)
    return text.strip()


def extract_price(text, pattern):
    m = pattern.search(text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(',', ''))
    except ValueError:
        return None


def is_approx(text, price):
    if not price:
        return False
    for m in APPROX_RE.finditer(text):
        try:
            p = float(m.group(1).replace(',', ''))
            if abs(p - price) < 1.0:
                return True
        except ValueError:
            pass
    return False


def extract_tickers(text):
    """Extract tickers, filtering common words and parenthetical base/underlying."""
    matches = TICKER_RE.findall(text)
    filtered = []
    for t in matches:
        if t in COMMON_WORDS:
            continue
        # Skip if ticker appears ONLY in a parenthetical base/underlying explanation
        # e.g. "GGLL (lev ticker on GOOGL)" -> skip GOOGL
        pat = re.compile(
            rf'\(\s*(?:[^)]*\s+(?:on|based|tracking|leveraged?|inverse|underlying)\s+)?'
            + t + r'\s*\)',
            re.IGNORECASE
        )
        if pat.search(text):
            continue
        filtered.append(t)
    return filtered


def extract_direction(text):
    d = text.lower()
    if re.search(r'\bbull(ish)?\b', d): return 'LONG'
    if re.search(r'\bbear(ish)?\b', d): return 'SHORT'
    if re.search(r'\bshort\b', d):     return 'SHORT'
    if re.search(r'\blong\b', d):      return 'LONG'
    if CALL_RE.search(d):              return 'CALL'
    if PUT_RE.search(d):               return 'PUT'
    return None


def extract_strategy(text):
    d = text.lower()
    if 'swing' in d:          return 'SWING'
    if 'day trade' in d or 'daytrade' in d: return 'DAY_TRADE'
    if re.search(r'\bcall\b', d) and re.search(r'\$[\d.]+', text): return 'OPTIONS_CALL'
    if re.search(r'\bput\b', d)  and re.search(r'\$[\d.]+', text): return 'OPTIONS_PUT'
    if 'scalp' in d:          return 'SCALP'
    if 'breakout' in d:       return 'BREAKOUT'
    if 'momentum' in d:       return 'MOMENTUM'
    if 'cnt' in d:            return 'CNT'
    return None


def calc_pct(target, entry, direction):
    if not target or not entry:
        return None
    try:
        if direction in ('LONG', 'BULL', 'CALL'):
            return round((target - entry) / entry * 100, 2)
        elif direction in ('SHORT', 'BEAR', 'PUT'):
            return round((entry - target) / entry * 100, 2)
    except ZeroDivisionError:
        pass
    return None


def parse_expiry(text, signal_date):
    """Parse expiration date from text."""
    m = EXPIRY_RE.search(text)
    if not m:
        return None
    try:
        parts = re.split(r'[/-]', m.group(1))
        month, day = int(parts[0]), int(parts[1])
        year = int(parts[2]) if len(parts) == 3 else signal_date.year
        if year < 100:
            year += 2000
        return date(year, month, day)
    except (ValueError, IndexError):
        return None


def detect_asset_class(text):
    """Detect whether this is an OPTION or STOCK trade."""
    d = text.lower()
    is_option = (
        CALL_RE.search(d) or PUT_RE.search(d) or
        'strike' in d or 'expiry' in d or 'expiration' in d or
        'contracts' in d or 'premium' in d
    )
    return 'OPTION' if is_option else 'STOCK'


def parse_msg(msg_row, conn):
    """
    Parse ONE discord_message row -> list of discord_trade_signal dicts.
    msg_row: (id, channel_id, message_timestamp, author_username, content, raw_json)
    """
    if not msg_row:
        return []

    msg_id, channel_id, msg_ts, author_username, content, raw_json = msg_row
    if not content:
        return []

    cleaned = clean_text(content)
    tickers = extract_tickers(cleaned)
    if not tickers:
        return []

    # Determine signal_date
    if msg_ts:
        if isinstance(msg_ts, str):
            try:
                signal_date = datetime.fromisoformat(msg_ts.replace('Z', '+00:00')).date()
            except ValueError:
                signal_date = date.today()
        elif isinstance(msg_ts, datetime):
            signal_date = msg_ts.date()
        else:
            signal_date = date.today()
    else:
        signal_date = date.today()

    # Get account_id and channel_id FK from DB
    cur = conn.cursor()
    cur.execute(
        "SELECT account_id, channel_id FROM discord_message WHERE id = %s",
        (msg_id,)
    )
    row = cur.fetchone()
    cur.close()
    if not row:
        return []
    account_id, ch_fk = row

    entry_price  = extract_price(cleaned, _ENTRY_RE)
    target_price = extract_price(cleaned, _TARGET_RE)
    stop_price   = extract_price(cleaned, _STOP_RE)
    asset_class  = detect_asset_class(cleaned)

    direction = extract_direction(cleaned)
    strategy  = extract_strategy(cleaned)

    if entry_price and target_price and not direction:
        direction = 'LONG'

    target_pct = calc_pct(target_price, entry_price, direction) if (target_price and entry_price) else None
    stop_pct   = calc_pct(stop_price,   entry_price, direction) if (stop_price   and entry_price) else None

    if target_pct and stop_pct and stop_pct > 0:
        try:
            rr = round(target_pct / stop_pct, 2)
        except ZeroDivisionError:
            rr = None
    else:
        rr = None

    confidence = 'HIGH' if (entry_price and target_price and stop_price) else \
                'MEDIUM' if (entry_price and target_price) else 'LOW'

    signals = []
    for ticker in tickers[:3]:
        sig = {
            'account_id':      account_id,
            'channel_id':      ch_fk,
            'message_id':      msg_id,
            'signal_id':       str(uuid.uuid4()),
            'asset_class':    asset_class,
            'signal_status':   'ACTIVE',
            'signal_date':     signal_date,
            'confidence':      confidence,
            'author_username': author_username,
            'signal_text':     content[:1000],
            'tags':           [],
            'stock_ticker':   ticker.upper() if asset_class == 'STOCK' else None,
            'trade_direction': direction if asset_class == 'STOCK' else None,
            'entry_price':     entry_price,
            'entry_price_approx': is_approx(cleaned, entry_price),
            'target_price':    target_price,
            'stop_loss':       stop_price,
            'target_pct':      target_pct,
            'stop_pct':        stop_pct,
            'risk_reward_ratio': rr,
        }

        # Options fields
        if asset_class == 'OPTION':
            sig['underlying_ticker'] = ticker.upper()
            sig['option_type'] = 'CALL' if CALL_RE.search(cleaned) else 'PUT' if PUT_RE.search(cleaned) else None
            sig['expiration_date'] = parse_expiry(cleaned, signal_date)

            strike_m = STRIKE_RE.search(cleaned)
            if strike_m:
                try:
                    sig['strike_price'] = float(strike_m.group(1).replace(',', ''))
                except ValueError:
                    pass

            contract_m = CONTRACT_RE.search(cleaned)
            if contract_m:
                try:
                    sig['contracts'] = float(contract_m.group(1))
                except ValueError:
                    pass

            premium = extract_price(cleaned, PREMIUM_RE)
            if premium:
                sig['entry_premium'] = premium
                sig['entry_premium_approx'] = is_approx(cleaned, premium)
                # Compute target/stop on premium
                t_pct = target_pct or 50
                s_pct = stop_pct or 25
                if sig['option_type'] == 'CALL':
                    sig['target_premium'] = round(premium * (1 + t_pct/100), 4) if premium else None
                    sig['stop_premium']   = round(premium * (1 - s_pct/100), 4) if premium else None
                elif sig['option_type'] == 'PUT':
                    sig['target_premium'] = round(premium * (1 + t_pct/100), 4) if premium else None
                    sig['stop_premium']   = round(premium * (1 - s_pct/100), 4) if premium else None
                sig['target_pct_opt'] = t_pct
                sig['stop_pct_opt']   = s_pct
                if sig['target_premium'] and sig['stop_premium'] and s_pct > 0:
                    try:
                        sig['risk_reward_ratio_opt'] = round(t_pct / s_pct, 2)
                    except ZeroDivisionError:
                        pass

        signals.append(sig)
    return signals


# ──────────────────────────────────────────────────────────────
# DATABASE
# ──────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def insert_signal(conn, sig):
    cols = list(sig.keys())
    vals = list(sig.values())
    placeholders = ['%(' + c + ')s' for c in cols]
    sql = f"""
        INSERT INTO discord_trade_signal ({','.join(cols)})
        VALUES ({','.join(placeholders)})
        ON CONFLICT (signal_id) DO UPDATE SET
            entry_price = EXCLUDED.entry_price,
            target_price = EXCLUDED.target_price,
            stop_loss = EXCLUDED.stop_loss,
            updated_at = NOW()
    """
    cur = conn.cursor()
    try:
        cur.execute(sql, sig)
        conn.commit()
        cur.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        cur.close()
        return False


def fetch_messages(conn, channel_id=None, limit=500):
    """Fetch messages that haven't been parsed yet."""
    cur = conn.cursor()
    if channel_id:
        cur.execute("""
            SELECT m.id, m.channel_id, m.message_timestamp,
                   m.author_username, m.content, m.raw_json
            FROM discord_message m
            LEFT JOIN discord_trade_signal s ON s.message_id = m.id
            WHERE m.channel_id = %s
              AND s.id IS NULL
              AND m.content IS NOT NULL AND m.content != ''
            ORDER BY m.message_timestamp DESC
            LIMIT %s
        """, (channel_id, limit))
    else:
        cur.execute("""
            SELECT m.id, m.channel_id, m.message_timestamp,
                   m.author_username, m.content, m.raw_json
            FROM discord_message m
            LEFT JOIN discord_trade_signal s ON s.message_id = m.id
            WHERE s.id IS NULL
              AND m.content IS NOT NULL AND m.content != ''
            ORDER BY m.message_timestamp DESC
            LIMIT %s
        """, (limit,))
    rows = cur.fetchall()
    cur.close()
    return rows


def main():
    parser = argparse.ArgumentParser(description="Parse trading signals from Discord messages")
    parser.add_argument("--channel-id", type=int, help="Filter by discord_channel.id (PK)")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = get_conn()

    print(f"[READ] Fetching unparsed messages...")
    rows = fetch_messages(conn, channel_id=args.channel_id, limit=args.limit)
    print(f"       Found {len(rows)} messages to parse")

    if not rows:
        print("[DONE] No new messages to parse")
        conn.close()
        return

    print(f"[PARSE] Extracting signals...")
    all_signals = []
    for row in rows:
        sigs = parse_msg(row, conn)
        all_signals.extend(sigs)

    print(f"       Found {len(all_signals)} signal(s)")

    if not all_signals:
        conn.close()
        return

    if args.dry_run:
        print("\n=== DRY RUN ===\n")
        for s in all_signals:
            print(f"  [{s['asset_class']}] {s.get('stock_ticker') or s.get('underlying_ticker')} | "
                  f"Dir:{s['trade_direction'] or s.get('option_type')} | "
                  f"Entry:${s['entry_price']} Target:${s['target_price']} Stop:${s['stop_loss']} | "
                  f"RR:{s['risk_reward_ratio'] or s.get('risk_reward_ratio_opt')} | "
                  f"{s['confidence']}")
            print(f"         {s['signal_text'][:120]}")
            print()
        conn.close()
        return

    print("[DB] Inserting signals...")
    inserted = skipped = 0
    for sig in all_signals:
        if insert_signal(conn, sig):
            t = sig.get('stock_ticker') or sig.get('underlying_ticker')
            print(f"  [INSERT] {sig['asset_class']} {t} | Entry:${sig['entry_price']} "
                  f"Target:${sig['target_price']} Stop:${sig['stop_loss']} | "
                  f"RR:{sig['risk_reward_ratio'] or sig.get('risk_reward_ratio_opt')} | "
                  f"{sig['confidence']}")
            inserted += 1
        else:
            skipped += 1

    print(f"\n[DONE] Inserted:{inserted} Skipped:{skipped}")

    # Summary
    cur = conn.cursor()
    cur.execute("""
        SELECT signal_id, asset_class,
               COALESCE(stock_ticker, underlying_ticker) as ticker,
               trade_direction, option_type,
               entry_price, target_price, stop_loss,
               risk_reward_ratio, confidence, signal_date, signal_status
        FROM discord_trade_signal
        ORDER BY signal_date DESC, created_at DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    print("\n=== Recent Signals ===")
    hdr = f"{'Ticker':<8} {'Asset':<7} {'Dir':<6} {'Entry':<8} {'Target':<8} {'Stop':<8} {'RR':<6} {'Conf':<8} {'Date':<12} Status"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{str(r[2] or ''):<8} {str(r[1] or ''):<7} "
              f"{str(r[3] or r[4] or ''):<6} "
              f"{('$' + str(r[5])) if r[5] else '':<8} "
              f"{('$' + str(r[6])) if r[6] else '':<8} "
              f"{('$' + str(r[7])) if r[7] else '':<8} "
              f"{str(r[8] or ''):<6} "
              f"{str(r[9] or ''):<8} "
              f"{str(r[10]):<12} {r[11]}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
