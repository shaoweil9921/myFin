"""
04_weekly_ashley_to_obsidian.py
================================
Process Coach Steve's weekly MACD messages from swl-coach-weekly Discord channel
and save them as structured Obsidian notes.

Usage:
  python 04_weekly_ashley_to_obsidian.py                    # process all new messages
  python 04_weekly_ashley_to_obsidian.py --msg-id <id>      # process specific message
  python 04_weekly_ashley_to_obsidian.py --reprocess        # overwrite existing files

Output: C:\\Data\\Obsidian_root\\Obsidian_trading\\Ashley_trading\\Weekly\\YYYY-MM-DD_sector_macd.md
"""
import os
import sys
import json
import re
import argparse
import base64
import requests
import psycopg2
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": os.environ.get("DB_PASSWORD", ""),
    "dbname": "fintech",
}

CHANNEL_ID = 4  # swl-coach-weekly in discord_channel table
OBSIDIAN_FOLDER = r"C:\Data\Obsidian_root\Obsidian_trading\Ashley_trading\Weekly"
TRACK_FILE = os.path.join(os.path.dirname(__file__), "weekly_ashley_processed.json")

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def load_processed():
    """Load set of already-processed message IDs."""
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE) as f:
            return set(json.load(f))
    return set()


def save_processed(processed_set):
    with open(TRACK_FILE, "w") as f:
        json.dump(sorted(processed_set), f, indent=2)


def get_msg_date(created_at):
    """Extract YYYY-MM-DD from a datetime string."""
    dt = created_at
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
    return dt.strftime("%Y-%m-%d")


def build_obsidian_content(msg_date, author, content, table_data, whats_changed, image_paths):
    """Build the full Obsidian markdown content."""

    # Format date for header
    date_display = datetime.strptime(msg_date, "%Y-%m-%d").strftime("%B %d, %Y")

    # Clean content (remove @everyone, fix encoding issues)
    clean_content = content.replace("\xa0", " ").replace(" @everyone ", " ")

    # Image embeds at bottom
    image_embeds = ""
    if image_paths:
        image_embeds = "\n## Attachments\n\n" + "\n".join(
            f"![]({path.replace(chr(92), '/')})" for path in image_paths
        )

    return f"""---
created: {msg_date}
source: Coach Steve / Ashley Weekly MACD
tags: [sector-analysis, macd, trading, weekly]
---

# Sector MACD Analysis — {msg_date}

## Discord Message ({author} — {date_display})

> {clean_content.replace(chr(10), chr(10) + "> ")}

## What's Changed (from image)

{whats_changed}

{table_data}

{image_embeds}

---

## Related

- [[Weekly MACD Analysis]] — anchor note
"""


def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_vision(image_path, prompt):
    """Use DeepSeek VL to extract content from an image."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return "[ERROR: DEEPSEEK_API_KEY not set]"

    base64_img = encode_image(image_path)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_img}"}}
            ]
        }],
        "max_tokens": 4096,
    }
    resp = requests.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers=headers, json=payload, timeout=90
    )
    if resp.status_code != 200:
        return f"[ERROR {resp.status_code}: {resp.text[:200]}]"
    return resp.json()["choices"][0]["message"]["content"]


def extract_macd_table(image_path):
    prompt = (
        "This is a trading spreadsheet screenshot of sector MACD analysis. "
        "Extract ALL data as a markdown table with these columns:\n"
        "Ticker | Sector | % of S&P | MACD (Weekly) | Date | Weeks In | Avg Cross Lasts | Avg Gain Per Bull Cross | "
        "Under 200 Day MA | YTD | YTD Week | YTD 9/18 | YTD 9/11 | YTD 9/4 | "
        "RSI | RSI 9/18 | RSI 9/11 | RSI 9/4 | Close to Bullish Stocks | Bullish Stock Tickers | Bearish Stock Tickers\n"
        "Include every row. Be precise with numbers and percentages. Use 🔴 for Bearish, 🟢 for Bullish."
    )
    return extract_vision(image_path, prompt)


def extract_whats_changed(image_path):
    prompt = (
        "This is a trading commentary screenshot titled 'What's Changed'. "
        "Extract all bullet points as a numbered list. Include the full text of each point. "
        "Preserve the numbers if they exist."
    )
    return extract_vision(image_path, prompt)


def process_message(msg_id, conn, reprocess=False):
    """Process a single message and save to Obsidian."""
    cur = conn.cursor()

    cur.execute("""
        SELECT m.message_id, m.author_username, m.content, m.created_at,
               m.local_image_path, c.channel_name
        FROM discord_message m
        JOIN discord_channel c ON c.id = m.channel_id
        WHERE m.message_id = %s
    """, (msg_id,))
    row = cur.fetchone()
    if not row:
        print(f"  [SKIP] Message {msg_id} not found in DB")
        cur.close()
        return False

    msg_db_id, author, content, created_at, local_image_path_json, channel_name = row
    created_at_str = str(created_at)

    # Parse image paths
    image_paths = []
    if local_image_path_json:
        try:
            paths = json.loads(local_image_path_json)
            if isinstance(paths, list):
                image_paths = [p for p in paths if p and os.path.exists(p)]
        except Exception:
            pass

    if not image_paths:
        print(f"  [SKIP] No valid image paths for message {msg_id}")
        cur.close()
        return False

    msg_date = get_msg_date(created_at_str)
    obs_path = Path(OBSIDIAN_FOLDER) / f"{msg_date}_sector_macd.md"

    # Determine which image is table vs commentary
    # att_0 = MACD table, att_1 = What's Changed
    table_path = next((p for p in image_paths if "_att_0." in p), image_paths[0])
    changed_path = next((p for p in image_paths if "_att_1." in p), None)

    # Extract data via vision
    print(f"  Extracting MACD table from: {os.path.basename(table_path)}")
    table_data = extract_macd_table(table_path)

    whats_changed = ""
    if changed_path:
        print(f"  Extracting What's Changed from: {os.path.basename(changed_path)}")
        whats_changed = extract_whats_changed(changed_path)

    # Build and save
    content = build_obsidian_content(
        msg_date, author, content or "", table_data, whats_changed, image_paths
    )
    with open(obs_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"  [OK] Saved: {obs_path.name}")
    cur.close()
    return True


def main():
    parser = argparse.ArgumentParser(description="Save Coach Steve's weekly MACD messages to Obsidian")
    parser.add_argument("--msg-id", type=str, help="Process specific message ID")
    parser.add_argument("--reprocess", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    conn = get_conn()
    processed = load_processed()

    if args.msg_id:
        # Single message
        success = process_message(args.msg_id, conn, reprocess=args.reprocess)
        if success:
            processed.add(args.msg_id)
            save_processed(processed)
    else:
        # All new messages from swl-coach-weekly
        cur = conn.cursor()
        cur.execute("""
            SELECT message_id, created_at, local_image_path
            FROM discord_message
            WHERE channel_id = %s
              AND local_image_path IS NOT NULL
              AND local_image_path != '[]'
            ORDER BY created_at DESC
        """, (CHANNEL_ID,))
        rows = cur.fetchall()
        cur.close()

        count = 0
        for msg_id, created_at, local_image_path in rows:
            msg_date = get_msg_date(str(created_at))
            obs_path = Path(OBSIDIAN_FOLDER) / f"{msg_date}_sector_macd.md"

            if not args.reprocess and str(msg_id) in processed:
                print(f"[SKIP] Already processed: {msg_id}")
                continue

            if not args.reprocess and obs_path.exists():
                print(f"[SKIP] File exists: {obs_path.name}")
                processed.add(str(msg_id))
                continue

            print(f"\nProcessing message {msg_id} ({msg_date})")
            if process_message(msg_id, conn, reprocess=args.reprocess):
                processed.add(str(msg_id))
                count += 1

        print(f"\n[DONE] Processed {count} new message(s)")
        save_processed(processed)

    conn.close()


if __name__ == "__main__":
    main()
