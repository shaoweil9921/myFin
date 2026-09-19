"""
parse_signals.py - Extract trading signals from discord_message table
and save to trading_signal table.

Usage:
    python parse_signals.py                  # scan all unparsed messages
    python parse_signals.py --message-id XYZ # parse a specific message
    python parse_signals.py --channel-id ABC # parse all messages in channel
    python parse_signals.py --dry-run        # show what would be extracted

Environment:
    DISCORD_BOT_TOKEN - for fetching channel/server metadata
"""

import os
import sys
import re
import uuid
import json
import psycopg2
import requests
import argparse
from datetime import datetime
from typing import Optional

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BASE_URL = "https://discord.com/api/v10"
HEADERS = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json",
}

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "asdfghjk1234%",
    "dbname": "fintech",
}


# ─────────────────────────────────────────────
# PATTERN MATCHERS
# ─────────────────────────────────────────────

# Ticker: 2-5 uppercase letters, standalone
TICKER_RE = re.compile(r'\b([A-Z]{2,5})\b')

# Entry price patterns
ENTRY_PRICE_RE = re.compile(
    r'(?:entry|buy|purchase|entry price|at|entered?|got)[:\s]*\$?([0-9,]+\.?[0-9]*)',
    re.IGNORECASE
)

# Price patterns - must handle $ prefix
_PRICE_NUM = r'\$?\s*[0-9,]+\.?[0-9]*'
_ENTRY_RE = re.compile(
    r'(?:entry|buy|purchase|entry price|entered?|got)[:\s]*(\$?[0-9,]+\.?[0-9]*)',
    re.IGNORECASE
)
_TARGET_RE = re.compile(
    r'(?:target|take profit|tp|profit)[:\s]*(?:at\s*)?(\$?[0-9,]+\.?[0-9]*)',
    re.IGNORECASE
)
_STOP_RE = re.compile(
    r'(?:stop|stoploss|stop loss|sl|stopped)[:\s]*(?:at\s*)?(\$?[0-9,]+\.?[0-9]*)',
    re.IGNORECASE
)

# Target price patterns
TARGET_RE = re.compile(
    r'(?:target|take profit|tp|profit|taking|exit)[:\s]*\$?([0-9,]+\.?[0-9]*)',
    re.IGNORECASE
)

# Stop loss patterns
STOP_RE = re.compile(
    r'(?:stop|stoploss|stop loss|sl|stopped|if it drops)[:\s]*\$?([0-9,]+\.?[0-9]*)',
    re.IGNORECASE
)

# Strategy type patterns
STRATEGY_RE = re.compile(
    r'\b(swing trade|swing|day trade|day trading|daytrade|options?|scalp|scalping|positional|long.?term|short.?term|momentum|breakout|cnt|cover|put|call|bull spread|bear spread|iron condor|straddle|strangle)\b',
    re.IGNORECASE
)

# Trade direction
DIRECTION_RE = re.compile(
    r'\b(long|short|bullish|bull|bearish|bear|buy|call|put|sell)\b',
    re.IGNORECASE
)

# Price with ~ (approximate)
APPROX_PRICE_RE = re.compile(r'\$?([0-9,]+\.?[0-9]*)\s*~')

# Position size patterns
SIZE_RE = re.compile(
    r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:shares?|contracts?|lots?|pcs?|options?)\b',
    re.IGNORECASE
)

# Date patterns within text
DATE_RE = re.compile(
    r'(?:on|for|dated|signal)?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
    re.IGNORECASE
)


def clean_text(text: str) -> str:
    """Remove Discord mentions and formatting."""
    if not text:
        return ""
    # Remove <@USER>, <#CHANNEL>, <@&ROLE>, :emoji:, etc.
    text = re.sub(r'<@!?\d+>', '', text)
    text = re.sub(r'<#\d+>', '', text)
    text = re.sub(r'<@&\d+>', '', text)
    text = re.sub(r'<:[a-zA-Z0-9_]+:\d+>', '', text)
    text = re.sub(r':[a-zA-Z0-9_]+:', '', text)
    text = re.sub(r'\*+', '', text)       # bold/italic
    text = re.sub(r'_+', '', text)
    text = re.sub(r'~~+', '', text)
    text = re.sub(r'\n+', ' ', text)
    return text.strip()


def extract_tickers(text: str):
    """Extract potential ticker symbols."""
    matches = TICKER_RE.findall(text)
    # Filter out common words that look like tickers
    common_words = {
        'THE', 'AND', 'FOR', 'NOT', 'ARE', 'BUT', 'YOU', 'ALL',
        'CAN', 'HAD', 'HER', 'WAS', 'ONE', 'OUR', 'OUT', 'DAY',
        'GET', 'HAS', 'HIM', 'HIS', 'HOW', 'ITS', 'MAY', 'NEW',
        'NOW', 'OLD', 'SEE', 'WAY', 'WHO', 'BOY', 'DID', 'GOT',
        'OMG', 'LOL', 'IDK', 'FYI', 'ETA', 'CEO', 'IPO', 'FDA',
        'USA', 'USD', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'GDP',
        'CPI', 'PPI', 'FED', 'SEC', 'FTC', 'EPA', 'HSA', 'IRA',
        '401K', 'ROI', 'YTD', 'MTD', 'QTD', 'YOY', 'MOIC',
        'HIGH', 'LOW', 'NEWS', 'CALL', 'PUT', 'OPEN', 'CLOSE',
        'STOP', 'NEXT', 'THIS', 'THAT', 'WITH', 'FROM', 'HAVE',
        'MORE', 'THAN', 'INTO', 'YEAR', 'MOST', 'JUST', 'OVER',
    }
    return [t for t in matches if t not in common_words]


def extract_price(text: str, pattern: re.Pattern) -> Optional[float]:
    """Extract first price match from text."""
    match = pattern.search(text)
    if match:
        try:
            val = match.group(1).replace(',', '').replace('$', '').strip()
            return float(val)
        except ValueError:
            return None
    return None


def is_approx_price(text: str, price: float) -> bool:
    """Check if price was marked as approximate (~)."""
    # Look for ~ before the price
    pattern = re.compile(r'~\s*\$?\s*[0-9,]+\.?[0-9]*')
    for m in pattern.finditer(text):
        try:
            p = float(m.group().replace('~', '').replace('$', '').replace(',', '').strip())
            if abs(p - price) < 0.5:
                return True
        except ValueError:
            pass
    return False


def extract_strategy(text: str) -> Optional[str]:
    """Determine strategy type from text."""
    text_lower = text.lower()
    if 'swing' in text_lower:
        return 'SWING'
    elif 'day trade' in text_lower or 'daytrade' in text_lower:
        return 'DAY_TRADE'
    elif re.search(r'\bcall\b', text_lower) and re.search(r'\$[\d.]+', text):
        return 'OPTIONS_CALL'
    elif re.search(r'\bput\b', text_lower) and re.search(r'\$[\d.]+', text):
        return 'OPTIONS_PUT'
    elif 'scalp' in text_lower:
        return 'SCALP'
    elif 'breakout' in text_lower:
        return 'BREAKOUT'
    elif 'momentum' in text_lower:
        return 'MOMENTUM'
    elif 'cnt' in text_lower:
        return 'CNT'
    return None


def extract_direction(text: str) -> Optional[str]:
    """Determine trade direction."""
    text_lower = text.lower()
    if re.search(r'\bbull(ish)?\b', text_lower):
        return 'BULL'
    elif re.search(r'\bbear(ish)?\b', text_lower):
        return 'BEAR'
    elif re.search(r'\bshort\b', text_lower):
        return 'SHORT'
    elif re.search(r'\blong\b', text_lower):
        return 'LONG'
    elif re.search(r'\bcall\b', text_lower):
        return 'CALL'
    elif re.search(r'\bput\b', text_lower):
        return 'PUT'
    elif re.search(r'\bbuy\b', text_lower):
        return 'LONG'
    return None


def calc_pct(target: float, entry: float, direction: str) -> Optional[float]:
    """Calculate target percentage."""
    if not target or not entry:
        return None
    if direction in ('LONG', 'BULL', 'CALL'):
        return round((target - entry) / entry * 100, 2)
    elif direction in ('SHORT', 'BEAR', 'PUT'):
        return round((entry - target) / entry * 100, 2)
    return None


def parse_signal_message(msg: dict) -> list:
    """
    Parse a single Discord message and extract trading signals.
    Returns list of signal dicts (one per ticker found).
    """
    raw_text = msg.get('content', '')
    cleaned = clean_text(raw_text)

    if not cleaned:
        return []

    tickers = extract_tickers(cleaned)
    if not tickers:
        return []

    # Deduplicate tickers - take first one most likely
    # But collect all for now
    signals = []

    entry_price = extract_price(cleaned, _ENTRY_RE)
    target_price = extract_price(cleaned, _TARGET_RE)
    stop_price = extract_price(cleaned, _STOP_RE)
    approx_entry = is_approx_price(cleaned, entry_price) if entry_price else False

    strategy = extract_strategy(cleaned)
    direction = extract_direction(cleaned)

    if entry_price and target_price and not direction:
        direction = 'LONG'

    target_pct = calc_pct(target_price, entry_price, direction) if (target_price and entry_price) else None
    stop_pct = calc_pct(stop_price, entry_price, direction) if (stop_price and entry_price) else None

    if target_pct and stop_pct and stop_pct > 0:
        try:
            rr = round(target_pct / stop_pct, 2)
        except ZeroDivisionError:
            rr = None
    else:
        rr = None

    for ticker in tickers[:3]:  # max 3 tickers per message
        sig = {
            'signal_id': str(uuid.uuid4()),
            'ticker': ticker,
            'ticker_normalized': ticker.upper(),
            'strategy_type': strategy,
            'trade_direction': direction,
            'entry_price': entry_price,
            'entry_price_approx': approx_entry,
            'target_price': target_price,
            'stop_loss': stop_price,
            'target_pct': target_pct,
            'stop_pct': stop_pct,
            'risk_reward_ratio': rr,
            'source_message_id': msg.get('message_id') or msg.get('id'),
            'source_channel_id': msg.get('channel_id'),
            'source_channel_name': msg.get('channel_name'),
            'source_server_name': msg.get('server_name'),
            'author_username': msg.get('author_username'),
            'signal_text': raw_text[:500],
            'confidence': 'MEDIUM' if entry_price and target_price else 'LOW',
            'signal_date': msg.get('signal_date') or (
                msg.get('timestamp').date() if msg.get('timestamp') else datetime.now().date()
            ),
        }
        signals.append(sig)

    return signals


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def get_db_conn():
    return psycopg2.connect(**DB_CONFIG)


def setup_tables(conn):
    """Create tables if they don't exist."""
    cur = conn.cursor()

    # Denormalized discord_message (add missing columns to existing table)
    denorm_columns = [
        ("server_id", "VARCHAR(64)"),
        ("server_name", "VARCHAR(255)"),
        ("author_nickname", "VARCHAR(255)"),
        ("author_roles", "TEXT[]"),
        ("cleaned_content", "TEXT"),
        ("embed_urls", "TEXT[]"),
        ("embed_images", "TEXT[]"),
        ("thread_id", "VARCHAR(64)"),
        ("thread_name", "VARCHAR(255)"),
        ("reply_to_message_id", "VARCHAR(64)"),
        ("is_pinned", "BOOLEAN DEFAULT FALSE"),
        ("reactions", "JSONB"),
        ("edited_at", "TIMESTAMPTZ"),
        ("has_mentions", "BOOLEAN DEFAULT FALSE"),
        ("has_bot_mention", "BOOLEAN DEFAULT FALSE"),
        ("message_type", "VARCHAR(50)"),
        ("updated_at", "TIMESTAMPTZ DEFAULT NOW()"),
    ]

    # Check and add columns one by one
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'discord_message'")
    existing = {r[0] for r in cur.fetchall()}

    for col_name, col_type in denorm_columns:
        if col_name not in existing:
            try:
                cur.execute(f"ALTER TABLE discord_message ADD COLUMN {col_name} {col_type}")
                print(f"  [SCHEMA] Added column: {col_name}")
            except Exception as e:
                print(f"  [WARN] Could not add {col_name}: {e}")

    # Create trading_signal table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trading_signal (
            id                  BIGSERIAL PRIMARY KEY,
            signal_id           VARCHAR(64)  NOT NULL UNIQUE,
            ticker              VARCHAR(10)  NOT NULL,
            ticker_normalized   VARCHAR(10)  NOT NULL,
            strategy_type       VARCHAR(50),
            trade_direction     VARCHAR(10),
            entry_price         NUMERIC(12, 4),
            entry_price_approx  BOOLEAN DEFAULT FALSE,
            entry_date          DATE,
            target_price        NUMERIC(12, 4),
            stop_loss           NUMERIC(12, 4),
            target_pct          NUMERIC(8, 2),
            stop_pct            NUMERIC(8, 2),
            position_size       VARCHAR(100),
            notional_value      NUMERIC(14, 2),
            risk_reward_ratio   NUMERIC(6, 2),
            source_message_id   VARCHAR(64),
            source_channel_id   VARCHAR(64),
            source_channel_name VARCHAR(255),
            source_server_name  VARCHAR(255),
            author_username     VARCHAR(255),
            signal_text         TEXT,
            confidence          VARCHAR(20),
            tags                TEXT[],
            sector              VARCHAR(100),
            asset_class         VARCHAR(50),
            status              VARCHAR(20) DEFAULT 'ACTIVE',
            target_hit_date     DATE,
            stopped_date        DATE,
            closed_date         DATE,
            notes               TEXT,
            signal_date         DATE NOT NULL,
            created_at          TIMESTAMPTZ DEFAULT NOW(),
            updated_at          TIMESTAMPTZ DEFAULT NOW(),
            CONSTRAINT unique_ticker_signal_date UNIQUE (ticker_normalized, signal_date, entry_price)
        )
    """)

    # Create indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_signal_ticker ON trading_signal(ticker_normalized)",
        "CREATE INDEX IF NOT EXISTS idx_signal_date ON trading_signal(signal_date DESC)",
        "CREATE INDEX IF NOT EXISTS idx_signal_status ON trading_signal(status)",
        "CREATE INDEX IF NOT EXISTS idx_signal_type ON trading_signal(strategy_type)",
        "CREATE INDEX IF NOT EXISTS idx_signal_channel ON trading_signal(source_channel_id)",
        "CREATE INDEX IF NOT EXISTS idx_signal_confidence ON trading_signal(confidence)",
        "CREATE INDEX IF NOT EXISTS idx_signal_active ON trading_signal(ticker_normalized, signal_date DESC) WHERE status = 'ACTIVE'",
        "CREATE INDEX IF NOT EXISTS idx_signal_tags ON trading_signal USING GIN (tags)",
        "CREATE INDEX IF NOT EXISTS idx_msg_channel_id ON discord_message(channel_id)",
        "CREATE INDEX IF NOT EXISTS idx_msg_server_id ON discord_message(server_id)",
        "CREATE INDEX IF NOT EXISTS idx_msg_timestamp ON discord_message(timestamp DESC)",
    ]
    for idx_sql in indexes:
        try:
            cur.execute(idx_sql)
        except Exception as e:
            print(f"  [WARN] Index: {e}")

    conn.commit()
    cur.close()


def fetch_channel_metadata(channel_id: str) -> dict:
    """Fetch channel and server name from Discord API."""
    if not BOT_TOKEN:
        return {}

    try:
        # Get channel info
        ch_resp = requests.get(f"{BASE_URL}/channels/{channel_id}", headers=HEADERS, timeout=10)
        if ch_resp.status_code != 200:
            return {}

        channel_data = ch_resp.json()
        guild_id = channel_data.get('guild_id')
        result = {
            'channel_name': channel_data.get('name', ''),
            'server_id': guild_id,
            'server_name': '',
        }

        # Get server name
        if guild_id:
            guild_resp = requests.get(f"{BASE_URL}/guilds/{guild_id}", headers=HEADERS, timeout=10)
            if guild_resp.status_code == 200:
                result['server_name'] = guild_resp.json().get('name', '')

        return result
    except Exception as e:
        print(f"  [WARN] Could not fetch Discord metadata: {e}")
        return {}


def fetch_messages_from_db(conn, channel_id: str = None, message_id: str = None, limit: int = 500):
    """Fetch messages from DB (optionally filtered)."""
    cur = conn.cursor()

    if message_id:
        cur.execute("""
            SELECT message_id, channel_id, author_username, content, timestamp, raw_json
            FROM discord_message WHERE message_id = %s
        """, (message_id,))
    elif channel_id:
        cur.execute("""
            SELECT message_id, channel_id, author_username, content, timestamp, raw_json
            FROM discord_message
            WHERE channel_id = %s
            ORDER BY timestamp DESC LIMIT %s
        """, (channel_id, limit))
    else:
        cur.execute("""
            SELECT message_id, channel_id, author_username, content, timestamp, raw_json
            FROM discord_message ORDER BY timestamp DESC LIMIT %s
        """, (limit,))

    rows = cur.fetchall()
    cur.close()

    messages = []
    for r in rows:
        msg = {
            'message_id': r[0],
            'channel_id': r[1],
            'author_username': r[2],
            'content': r[3],
            'timestamp': r[4],
            'raw_json': r[5] if isinstance(r[5], dict) else (json.loads(r[5]) if r[5] else {}),
        }
        messages.append(msg)
    return messages


def enrich_messages(messages: list) -> list:
    """Fetch Discord metadata for channels not yet enriched."""
    conn = get_db_conn()
    cur = conn.cursor()

    for msg in messages:
        channel_id = msg.get('channel_id')
        # Check if already has channel/server name
        cur.execute("""
            SELECT server_name, channel_name FROM discord_message
            WHERE channel_id = %s LIMIT 1
        """, (channel_id,))
        row = cur.fetchone()
        if row and row[0]:
            msg['server_name'] = row[0]
            msg['channel_name'] = row[1]
        else:
            # Fetch from Discord
            meta = fetch_channel_metadata(channel_id)
            msg.update(meta)

            # Update DB with metadata
            cur.execute("""
                UPDATE discord_message SET
                    server_name = %s, channel_name = %s, server_id = %s
                WHERE channel_id = %s
            """, (meta.get('server_name'), meta.get('channel_name'), meta.get('server_id'), channel_id))

    conn.commit()
    cur.close()
    conn.close()
    return messages


def insert_signal(conn, sig: dict) -> bool:
    """Insert a trading signal. Returns True if inserted, False if skipped (duplicate)."""
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO trading_signal (
                signal_id, ticker, ticker_normalized, strategy_type, trade_direction,
                entry_price, entry_price_approx, target_price, stop_loss,
                target_pct, stop_pct, risk_reward_ratio,
                source_message_id, source_channel_id, source_channel_name,
                source_server_name, author_username, signal_text, confidence, signal_date
            ) VALUES (
                %(signal_id)s, %(ticker)s, %(ticker_normalized)s, %(strategy_type)s,
                %(trade_direction)s, %(entry_price)s, %(entry_price_approx)s,
                %(target_price)s, %(stop_loss)s, %(target_pct)s, %(stop_pct)s,
                %(risk_reward_ratio)s, %(source_message_id)s, %(source_channel_id)s,
                %(source_channel_name)s, %(source_server_name)s, %(author_username)s,
                %(signal_text)s, %(confidence)s, %(signal_date)s
            )
            ON CONFLICT (signal_id) DO UPDATE SET
                entry_price = EXCLUDED.entry_price,
                target_price = EXCLUDED.target_price,
                stop_loss = EXCLUDED.stop_loss,
                updated_at = NOW()
        """, sig)
        conn.commit()
        cur.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        cur.close()
        return False  # duplicate


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Parse trading signals from Discord messages")
    parser.add_argument("--channel-id", help="Filter by channel ID")
    parser.add_argument("--message-id", help="Parse specific message")
    parser.add_argument("--limit", type=int, default=500, help="Max messages to scan")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be extracted")
    parser.add_argument("--setup", action="store_true", help="Run schema setup only")
    args = parser.parse_args()

    conn = get_db_conn()

    # Setup tables
    print("[SETUP] Creating/updating schema...")
    setup_tables(conn)

    if args.setup:
        print("[DONE] Schema setup complete.")
        conn.close()
        return

    # Fetch messages
    print(f"[READ] Fetching messages from DB...")
    messages = fetch_messages_from_db(conn, channel_id=args.channel_id, message_id=args.message_id, limit=args.limit)
    print(f"       Found {len(messages)} messages")

    # Enrich with channel/server names
    print("[ENRICH] Fetching channel metadata from Discord...")
    messages = enrich_messages(messages)

    # Parse signals
    print("[PARSE] Extracting trading signals...")
    all_signals = []
    for msg in messages:
        sigs = parse_signal_message(msg)
        for sig in sigs:
            sig['signal_date'] = sig['signal_date'] if isinstance(sig['signal_date'], datetime) else datetime.combine(
                sig['signal_date'], datetime.now().time()
            )
        all_signals.extend(sigs)

    if not all_signals:
        print("[DONE] No trading signals found.")
        conn.close()
        return

    print(f"       Found {len(all_signals)} potential signal(s)")

    if args.dry_run:
        print("\n=== DRY RUN - Signals that would be inserted ===\n")
        for s in all_signals:
            print(f"  [{s['ticker']}] {s['strategy_type'] or '?'} | "
                  f"Entry: ${s['entry_price']} | Target: ${s['target_price']} | "
                  f"Stop: ${s['stop_loss']} | Dir: {s['trade_direction']} | "
                  f"Conf: {s['confidence']}")
            print(f"         Text: {s['signal_text'][:100]}...")
            print()
        conn.close()
        return

    # Insert
    print("[DB] Inserting signals...")
    inserted = 0
    skipped = 0
    for sig in all_signals:
        if insert_signal(conn, sig):
            inserted += 1
            print(f"  [INSERT] {sig['ticker']} | Entry: ${sig['entry_price']} | "
                  f"Target: ${sig['target_price']} | Stop: ${sig['stop_loss']} | "
                  f"RR: {sig['risk_reward_ratio']} | Conf: {sig['confidence']}")
        else:
            skipped += 1

    print(f"\n[DONE] Inserted: {inserted} | Skipped (duplicate): {skipped}")

    # Show summary
    cur = conn.cursor()
    cur.execute("""
        SELECT ticker_normalized, strategy_type, trade_direction,
               entry_price, target_price, stop_loss, risk_reward_ratio,
               confidence, signal_date, status
        FROM trading_signal
        ORDER BY signal_date DESC, ticker_normalized
        LIMIT 20
    """)
    rows = cur.fetchall()
    print("\n=== Recent Trading Signals ===")
    print(f"{'Ticker':<8} {'Type':<12} {'Dir':<6} {'Entry':<8} {'Target':<8} {'Stop':<8} {'RR':<6} {'Conf':<8} {'Date':<12} {'Status'}")
    print("-" * 105)
    for r in rows:
        print(f"{r[0]:<8} {str(r[1] or ''):<12} {str(r[2] or ''):<6} "
              f"{('$'+str(r[3])) if r[3] else '':<8} "
              f"{('$'+str(r[4])) if r[4] else '':<8} "
              f"{('$'+str(r[5])) if r[5] else '':<8} "
              f"{str(r[6] or ''):<6} {str(r[7] or ''):<8} "
              f"{str(r[8]):<12} {r[9]}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
