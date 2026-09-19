"""
Discord Channel Reader -> PostgreSQL
Reads messages from a Discord channel and saves them to the fintech.discord_message table.

Usage:
    python save_to_postgres.py --channel-id <CHANNEL_ID> --limit <NUM>
    python save_to_postgres.py --channel-id <CHANNEL_ID> --all       # all messages

Environment:
    DISCORD_BOT_TOKEN - Bot token
    DB credentials hardcoded for fintech DB (localhost:5432)
"""

import os
import sys
import json
import requests
import psycopg2
import argparse
from datetime import datetime

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


def get_db_conn():
    return psycopg2.connect(**DB_CONFIG)


def fetch_messages(channel_id: str, limit: int = 50, before: str = None):
    url = f"{BASE_URL}/channels/{channel_id}/messages"
    params = {"limit": min(limit, 100)}
    if before:
        params["before"] = before

    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 403:
        print(f"[ERROR] Forbidden: check bot permissions for channel {channel_id}")
    elif resp.status_code == 404:
        print(f"[ERROR] Channel not found: {channel_id}")
    else:
        print(f"[ERROR] HTTP {resp.status_code}: {resp.text}")
    return []


def parse_message(msg: dict) -> dict:
    """Extract relevant fields from a Discord message."""
    author = msg.get("author", {})

    embeds = msg.get("embeds", [])
    embed_titles = "|".join([e.get("title", "") for e in embeds if e.get("title")])
    embed_descriptions = "|".join([e.get("description", "")[:500] for e in embeds if e.get("description")])

    attachments = msg.get("attachments", [])
    attach_list = [
        {"filename": a.get("filename"), "url": a.get("url"), "size": a.get("size")}
        for a in attachments
    ]

    timestamp = msg.get("timestamp", "")
    if timestamp:
        timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

    return {
        "message_id": msg.get("id"),
        "channel_id": msg.get("channel_id"),
        "author_id": author.get("id"),
        "author_username": author.get("username", ""),
        "content": msg.get("content", ""),
        "embed_titles": embed_titles or None,
        "embed_descriptions": embed_descriptions or None,
        "attachments": json.dumps(attach_list) if attach_list else None,
        "raw_json": json.dumps(msg),
        "timestamp": timestamp,
    }


def save_messages(messages: list, conn) -> int:
    """Insert messages into postgres. Returns count of new rows inserted."""
    cur = conn.cursor()
    inserted = 0

    for msg in messages:
        parsed = parse_message(msg)
        try:
            cur.execute("""
                INSERT INTO discord_message (
                    message_id, channel_id, author_id, author_username,
                    content, embed_titles, embed_descriptions,
                    attachments, raw_json, timestamp
                ) VALUES (
                    %(message_id)s, %(channel_id)s, %(author_id)s, %(author_username)s,
                    %(content)s, %(embed_titles)s, %(embed_descriptions)s,
                    %(attachments)s, %(raw_json)s, %(timestamp)s
                )
                ON CONFLICT (message_id) DO UPDATE SET
                    content = EXCLUDED.content,
                    embed_titles = EXCLUDED.embed_titles,
                    embed_descriptions = EXCLUDED.embed_descriptions,
                    attachments = EXCLUDED.attachments
            """, parsed)
            inserted += 1
        except Exception as e:
            print(f"[WARN] Failed to insert message {parsed.get('message_id')}: {e}")

    conn.commit()
    cur.close()
    return inserted


def main():
    parser = argparse.ArgumentParser(description="Read Discord channel and save to PostgreSQL")
    parser.add_argument("--channel-id", required=True, help="Discord channel ID")
    parser.add_argument("--limit", type=int, default=100, help="Number of messages to fetch")
    parser.add_argument("--all", action="store_true", help="Fetch all messages (paginated)")
    args = parser.parse_args()

    if not BOT_TOKEN:
        print("[ERROR] DISCORD_BOT_TOKEN not set")
        return

    print(f"[READER] Fetching messages from channel {args.channel_id}...")
    conn = get_db_conn()

    if args.all:
        all_messages = []
        before = None
        total = 0
        while True:
            batch = fetch_messages(args.channel_id, limit=100, before=before)
            if not batch:
                break
            all_messages.extend(batch)
            total += len(batch)
            before = batch[-1]["id"]
            print(f"   Fetched {len(batch)} messages... (total: {total})")
            if len(batch) < 100:
                break

        print(f"\n[DB] Saving {len(all_messages)} messages to PostgreSQL...")
        inserted = save_messages(all_messages, conn)
        print(f"[DONE] Total fetched: {total} | Inserted/Updated: {inserted}")
    else:
        messages = fetch_messages(args.channel_id, limit=args.limit)
        print(f"[DB] Saving {len(messages)} messages to PostgreSQL...")
        inserted = save_messages(messages, conn)
        print(f"[DONE] Inserted/Updated: {inserted}")

    conn.close()


if __name__ == "__main__":
    main()
