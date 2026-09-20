"""03_fetch_messages.py - Fetch new Discord messages for tracked channels"""
import os
import sys
import re
import json
import time
import requests
import psycopg2
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
# HELPERS
# ──────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def is_market_open(conn):
    """8:30 AM - 5:00 PM ET, Mon-Fri, not a holiday."""
    cur = conn.cursor()
    cur.execute("""
        SELECT EXISTS (SELECT 1 FROM market_holidays WHERE date = CURRENT_DATE) as is_holiday,
               EXTRACT(DOW FROM CURRENT_DATE) as dow,
               CURRENT_TIME AT TIME ZONE 'America/New_York' as et_time
    """)
    row = cur.fetchone()
    cur.close()
    if row[0]:  # holiday
        return False
    if row[1] not in (1, 2, 3, 4, 5):  # not weekday
        return False
    t = row[2]
    total_secs = t.hour * 3600 + t.minute * 60 + t.second
    OPEN_SECS  = 8 * 3600 + 30 * 60   # 08:30
    CLOSE_SECS = 17 * 3600              # 17:00
    return OPEN_SECS <= total_secs <= CLOSE_SECS


def discord_request(method, url, **kwargs):
    """Make a Discord API request with rate limit handling."""
    kwargs.setdefault('headers', HEADERS)
    kwargs.setdefault('timeout', 15)
    resp = requests.request(method, url, **kwargs)
    if resp.status_code == 429:
        retry_after = float(resp.json().get('retry_after', 5))
        print(f"  [RATELIMIT] Sleeping {retry_after:.1f}s")
        time.sleep(retry_after + 0.5)
        return discord_request(method, url, **kwargs)
    if resp.status_code >= 400:
        print(f"  [DISCORD ERROR] {resp.status_code}: {resp.text[:200]}")
        return None
    return resp


def fetch_channel_messages(channel_id, before_msg_id=None, limit=100):
    """Fetch messages from a Discord channel."""
    url = f"{BASE_URL}/channels/{channel_id}/messages"
    params = {'limit': min(limit, 100)}
    if before_msg_id:
        params['before'] = before_msg_id
    resp = discord_request('GET', url, params=params)
    if not resp:
        return []
    return resp.json()


def parse_message(msg):
    """Normalize a Discord message dict into a flat dict."""
    author = msg.get('author', {})
    mentions = msg.get('mentions', [])
    embeds  = msg.get('embeds', [])

    content = msg.get('content', '')

    # Extract author's embedded post time before cleaning
    author_posted_at = parse_author_timestamp(content)

    has_mentions    = len(mentions) > 0
    has_bot_mention = any(m.get('bot', False) for m in mentions)
    """Normalize a Discord message dict into a flat dict."""
    author = msg.get('author', {})
    mentions = msg.get('mentions', [])
    embeds  = msg.get('embeds', [])

    content = msg.get('content', '')
    has_mentions    = len(mentions) > 0
    has_bot_mention = any(m.get('bot', False) for m in mentions)

    embed_titles       = '\n'.join(e.get('title', '') or '' for e in embeds if e.get('title'))
    embed_descriptions = '\n'.join(e.get('description', '') or '' for e in embeds if e.get('description'))
    embed_urls         = [e.get('url', '') for e in embeds if e.get('url')]
    embed_images       = [e.get('image', {}).get('url', '') for e in embeds if e.get('image', {}).get('url')]

    attachments = [
        {
            'filename': a.get('filename', ''),
            'url': a.get('url', ''),
            'size': a.get('size', 0),
            'content_type': a.get('content_type', ''),
        }
        for a in msg.get('attachments', [])
    ]

    reactions = []
    for r in msg.get('reactions', []):
        emoji = r.get('emoji', {})
        reactions.append({
            'emoji':    emoji.get('name', ''),
            'count':    r.get('count', 0),
            'user_ids': [u['id'] for u in r.get('users', [])],
        })

    # Try to parse Discord timestamp
    ts = msg.get('timestamp')
    if ts:
        try:
            ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except ValueError:
            ts = datetime.utcnow()
    else:
        ts = datetime.utcnow()

    edited = msg.get('edited_timestamp')
    if edited:
        try:
            edited = datetime.fromisoformat(edited.replace('Z', '+00:00'))
        except ValueError:
            edited = None

    return {
        'message_id':          str(msg.get('id', '')),
        'author_id':           str(author.get('id', '')),
        'author_username':     author.get('username', ''),
        'content':             content,
        'cleaned_content':     None,   # set in save step
        'embed_titles':        embed_titles or None,
        'embed_descriptions':  embed_descriptions or None,
        'embed_urls':          embed_urls or None,
        'embed_images':        embed_images or None,
        'attachments':         attachments or None,
        'reactions':          reactions or None,
        'thread_id':           str(msg.get('thread', {}).get('id', '')) or None,
        'thread_name':         msg.get('thread', {}).get('name', '') or None,
        'reply_to_message_id': str(msg.get('message_reference', {}).get('message_id', '')) or None,
        'is_pinned':           msg.get('pinned', False),
        'message_type':        msg.get('type', 'DEFAULT'),
        'has_mentions':        has_mentions,
        'has_bot_mention':    has_bot_mention,
        'edited_at':           edited,
        'message_timestamp':    ts,
        'raw_json':            msg,    # store full dict for debugging
    }


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


_AUTHOR_TS_PAT = re.compile(
    # Captures: username (everything before first digit), date, time, AM/PM
    r'^(.+?)\s+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\s+(\d{1,2}:\d{2})\s*(AM|PM|am|pm)',
    re.UNICODE
)
_Month_MAP = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
    'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6,
    'jul': 7, 'july': 7, 'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9,
    'oct': 10, 'october': 10, 'nov': 11, 'november': 11, 'dec': 12, 'december': 12,
}


def parse_author_timestamp(content):
    """Extract author-posted timestamp from first line like:
    'TradingWithAshley — 9/14/2026 11:20 AM'
    Returns naive datetime in ET, or None."""
    if not content:
        return None
    line1 = content.split('\n', 1)[0].strip()
    m = _AUTHOR_TS_PAT.match(line1)
    if not m:
        return None
    date_str, time_str = m.group(2), m.group(3)
    ampm = m.group(4).upper()

    # Parse date
    for fmt in ('%m/%d/%Y', '%m/%d/%y', '%m-%d-%Y', '%m-%d-%y'):
        try:
            dt = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue
    else:
        return None

    # Parse time
    try:
        t = datetime.strptime(f"{time_str} {ampm}", '%I:%M %p').time()
    except ValueError:
        return None

    # Combine in ET (naive — tz applied at storage level)
    return datetime(dt.year, dt.month, dt.day, t.hour, t.minute, t.second)


def save_messages(conn, channel_db_id, channel_discord_id, messages):
    """Save messages to discord_message, update cursor."""
    if not messages:
        return 0

    # Discord returns newest first; capture the newest (first) snowflake as cursor
    last_msg_id = messages[0]['id']
    saved = 0
    cur = conn.cursor()

    for msg in messages:
        parsed = parse_message(msg)
        parsed['cleaned_content'] = clean_text(parsed['content'])

        # Upsert message
        cur.execute("""
            INSERT INTO discord_message (
                channel_id, message_id, author_id, author_username,
                content, cleaned_content,
                embed_titles, embed_descriptions, embed_urls, embed_images,
                attachments, reactions,
                thread_id, thread_name, reply_to_message_id,
                is_pinned, message_type, has_mentions, has_bot_mention,
                edited_at, message_timestamp, author_posted_at, raw_json
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (channel_id, message_id) DO UPDATE SET
                content = EXCLUDED.content,
                cleaned_content = EXCLUDED.cleaned_content,
                edited_at = EXCLUDED.edited_at,
                author_posted_at = EXCLUDED.author_posted_at,
                raw_json = EXCLUDED.raw_json
        """, (
            channel_db_id,
            parsed['message_id'],
            parsed['author_id'],
            parsed['author_username'],
            parsed['content'],
            parsed['cleaned_content'],
            parsed['embed_titles'],
            parsed['embed_descriptions'],
            parsed['embed_urls'],
            parsed['embed_images'],
            json.dumps(parsed['attachments']) if parsed['attachments'] else None,
            json.dumps(parsed['reactions']) if parsed['reactions'] else None,
            parsed['thread_id'],
            parsed['thread_name'],
            parsed['reply_to_message_id'],
            parsed['is_pinned'],
            parsed['message_type'],
            parsed['has_mentions'],
            parsed['has_bot_mention'],
            parsed['edited_at'],
            parsed['message_timestamp'],
            parsed.get('author_posted_at'),
            json.dumps(parsed['raw_json']),
        ))
        saved += 1

    conn.commit()

    # Update cursor
    if last_msg_id:
        cur.execute("""
            UPDATE discord_channel
            SET last_message_id = %s, last_fetched_at = NOW(), updated_at = NOW()
            WHERE id = %s
        """, (last_msg_id, channel_db_id))
        conn.commit()

    cur.close()
    return saved


def fetch_channel(conn, channel_row):
    """Fetch new messages for one channel."""
    ch_db_id, ch_discord_id, ch_name, last_msg_id = channel_row

    messages = fetch_channel_messages(ch_discord_id, before_msg_id=last_msg_id)
    if messages is None:
        return 0  # error

    if not messages:
        return 0

    # Discord returns newest first; save in that order
    saved = save_messages(conn, ch_db_id, ch_discord_id, messages)
    return saved


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch Discord messages for tracked channels")
    parser.add_argument("--channel-id", type=int, help="Fetch specific channel by DB id")
    parser.add_argument("--force", action="store_true", help="Fetch even outside market hours")
    args = parser.parse_args()

    conn = get_conn()

    # Market hours check
    if not args.force and False and not is_market_open(conn):
        print(f"[SKIP] Outside market hours (bypassed)")
        conn.close()
        return

    # Get tracked channels
    cur = conn.cursor()
    if args.channel_id:
        cur.execute("""
            SELECT id, channel_id, channel_name, last_message_id
            FROM discord_channel
            WHERE id = %s AND is_tracking = TRUE
        """, (args.channel_id,))
    else:
        cur.execute("""
            SELECT id, channel_id, channel_name, last_message_id
            FROM discord_channel
            WHERE is_tracking = TRUE
            ORDER BY updated_at ASC NULLS FIRST
        """)
    channels = cur.fetchall()
    cur.close()

    if not channels:
        print("[DONE] No channels to fetch")
        conn.close()
        return

    print(f"[START] Fetching {len(channels)} channel(s)...")
    total_saved = 0

    for ch in channels:
        ch_db_id, ch_discord_id, ch_name, last_msg_id = ch
        print(f"\n  [{ch_name} ({ch_discord_id})] last_cursor={last_msg_id}")
        saved = fetch_channel(conn, ch)
        print(f"  -> {saved} new message(s)")
        total_saved += saved
        if saved > 0:
            print(f"  [OK] {ch_name}: +{saved}")

    print(f"\n[DONE] Total new messages: {total_saved}")

    conn.close()


if __name__ == "__main__":
    main()
