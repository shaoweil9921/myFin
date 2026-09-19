"""
Discord Channel Reader for myTrading Bot
Reads messages from a specified Discord channel using the Discord Bot API.

Usage:
    python read_channel.py --channel-id <CHANNEL_ID> --limit <NUM_MESSAGES>

Environment:
    DISCORD_BOT_TOKEN - Your bot token (set in Windows env vars)

Example:
    python read_channel.py --channel-id 123456789012345678 --limit 50
"""

import os
import sys
import requests
import argparse
from datetime import datetime

# Fix Windows UTF-8 output
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BASE_URL = "https://discord.com/api/v10"
HEADERS = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json",
}


def fetch_messages(channel_id: str, limit: int = 50, before: str = None):
    """Fetch messages from a Discord channel."""
    url = f"{BASE_URL}/channels/{channel_id}/messages"
    params = {"limit": min(limit, 100)}  # Discord max 100 per request
    if before:
        params["before"] = before

    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code == 200:
        return resp.json()
    elif resp.status_code == 403:
        print(f"[ERROR] Forbidden: Bot lacks permission to read channel {channel_id}")
        print(f"   Make sure the bot has 'Read Message History' permission in this channel.")
    elif resp.status_code == 404:
        print(f"[ERROR] Channel {channel_id} not found or bot is not in that server.")
    else:
        print(f"[ERROR] HTTP {resp.status_code}: {resp.text}")
    return []


def format_message(msg: dict) -> str:
    """Format a Discord message for clean output."""
    timestamp = msg.get("timestamp", "")
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        time_str = dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        time_str = timestamp

    author = msg.get("author", {})
    username = author.get("username", "unknown")
    discriminator = author.get("discriminator", "0")
    display_name = f"{username}#{discriminator}" if discriminator != "0" else username

    content = msg.get("content", "")
    if not content:
        content = "[no text content]"

    # Handle embeds
    embeds = msg.get("embeds", [])
    embed_info = ""
    if embeds:
        for emb in embeds:
            if emb.get("title"):
                embed_info += f"\n   [Embed] {emb['title']}"
            if emb.get("description"):
                embed_info += f"\n   {emb['description'][:200]}"

    # Handle attachments
    attachments = msg.get("attachments", [])
    attach_info = ""
    if attachments:
        for att in attachments:
            attach_info += f"\n   [File] {att.get('filename', 'unknown')} ({att.get('size', 0)} bytes)"

    return f"[{time_str}] {display_name}: {content}{embed_info}{attach_info}"


def print_messages(messages: list):
    """Print formatted messages, newest first."""
    if not messages:
        print("No messages found.")
        return

    # Messages come newest-last from API, reverse for chronological order
    for msg in reversed(messages):
        print(format_message(msg))
        print()


def main():
    parser = argparse.ArgumentParser(description="Read Discord channel messages")
    parser.add_argument("--channel-id", required=True, help="Discord channel ID")
    parser.add_argument("--limit", type=int, default=50, help="Number of messages to fetch (max 100)")
    parser.add_argument("--all", action="store_true", help="Fetch all messages (paginate through all)")
    args = parser.parse_args()

    if not BOT_TOKEN:
        print("[ERROR] DISCORD_BOT_TOKEN not set in environment variables.")
        print("   Run: [Environment]::SetEnvironmentVariable('DISCORD_BOT_TOKEN', 'YOUR_TOKEN', 'User')")
        return

    print(f"[READER] Fetching messages from channel {args.channel_id}...")
    print(f"   Limit: {args.limit} messages")
    print("-" * 60)

    if args.all:
        # Paginate through all messages
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

        print(f"\n{'='*60}")
        print(f"[STATS] Total messages fetched: {len(all_messages)}")
        print(f"{'='*60}\n")
        print_messages(all_messages)
    else:
        messages = fetch_messages(args.channel_id, limit=args.limit)
        print(f"\n[STATS] Messages fetched: {len(messages)}")
        print_messages(messages)


if __name__ == "__main__":
    main()
