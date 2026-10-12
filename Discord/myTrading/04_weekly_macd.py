"""
04_weekly_macd.py
=================
Master script to generate Coach Steve's weekly MACD Obsidian file for a given date.

Usage:
  python 04_weekly_macd.py --date 2026-10-11
  python 04_weekly_macd.py --date 2026-10-11 --reprocess
"""
import os
import sys
import json
import argparse
import base64
import requests
import psycopg2
from datetime import datetime
from pathlib import Path

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": os.environ.get("DB_PW", ""),
    "dbname": "fintech",
}

CHANNEL_ID = 4  # swl-coach-weekly
OBSIDIAN_FOLDER = r"C:\Data\Obsidian_root\Obsidian_trading\Ashley_trading\Weekly"
TRACK_FILE = os.path.join(os.path.dirname(__file__), "weekly_ashley_processed.json")


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def load_processed():
    if os.path.exists(TRACK_FILE):
        with open(TRACK_FILE) as f:
            return set(json.load(f))
    return set()


def save_processed(msg_id):
    processed = load_processed()
    processed.add(str(msg_id))
    with open(TRACK_FILE, "w") as f:
        json.dump(sorted(processed), f, indent=2)


def is_processed(msg_id):
    return str(msg_id) in load_processed()


def build_obsidian_content(msg_date, author, content, table_data, whats_changed, image_paths):
    date_display = datetime.strptime(msg_date, "%Y-%m-%d").strftime("%B %d, %Y")
    clean_content = content.replace("\xa0", " ").replace(" @everyone ", " ")

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

# Sector MACD Analysis --- {msg_date}

## Discord Message ({author} --- {date_display})

> {clean_content.replace(chr(10), chr(10) + "> ")}

## What's Changed (from image)

{whats_changed}

{table_data}

{image_embeds}

---

## Related

- [[Weekly MACD Analysis]] --- anchor note
"""


def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_vision(image_path, prompt):
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        return "[ERROR: DEEPSEEK_API_KEY not set]"

    base64_img = encode_image(image_path)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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
        "Ticker | Sector | % of S&P | MACD (Weekly) | Date | weeks In | Avg Cross Lasts | Avg Gain Per Bull Cross | "
        "Under 200 Day MA | YTD | YTD Week | YTD 9/18 | YTD 9/11 | YTD 9/4 | "
        "RSI | RSI 9/18 | RSI 9/11 | RSI 9/4 | Close to Bullish Stocks | Bullish Stock Tickers | Bearish Stock Tickers\n"
        "Include every row. Be precise with numbers and percentages."
    )
    return extract_vision(image_path, prompt)


def extract_whats_changed(image_path):
    prompt = (
        "This is a trading commentary screenshot titled 'What's Changed'. "
        "Extract all bullet points as a numbered list. Include the full text of each point."
    )
    return extract_vision(image_path, prompt)


def process_for_date(date_str, reprocess=False):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT m.message_id, m.author_username, m.content, m.created_at,
               m.local_image_path
        FROM discord_message m
        WHERE m.channel_id = %s
          AND DATE(m.created_at AT TIME ZONE 'America/New_York') = %s
          AND m.local_image_path IS NOT NULL
          AND m.local_image_path != %s
        ORDER BY m.created_at DESC
        LIMIT 1
    """, (CHANNEL_ID, date_str, "[]"))

    row = cur.fetchone()
    if not row:
        print(f"[SKIP] No weekly MACD message found for {date_str}")
        conn.close()
        return False

    msg_db_id, author, content, created_at, local_image_path_json = row
    msg_id = str(msg_db_id)

    if is_processed(msg_id) and not reprocess:
        print(f"[SKIP] Already processed: {msg_id}")
        conn.close()
        return False

    image_paths = []
    if local_image_path_json:
        try:
            paths = json.loads(local_image_path_json)
            if isinstance(paths, list):
                image_paths = [p for p in paths if p and os.path.exists(p)]
        except Exception:
            pass

    if not image_paths:
        print(f"[SKIP] No valid image paths for message {msg_id}")
        conn.close()
        return False

    table_path = next((p for p in image_paths if "_att_0." in p), image_paths[0])
    changed_path = next((p for p in image_paths if "_att_1." in p), None)

    print(f"  Extracting MACD table from: {os.path.basename(table_path)}")
    table_data = extract_macd_table(table_path)

    whats_changed = ""
    if changed_path:
        print(f"  Extracting What's Changed from: {os.path.basename(changed_path)}")
        whats_changed = extract_whats_changed(changed_path)

    obs_path = Path(OBSIDIAN_FOLDER) / f"{date_str}_sector_macd.md"
    content_md = build_obsidian_content(
        date_str, author, content or "", table_data, whats_changed, image_paths
    )
    with open(obs_path, "w", encoding="utf-8") as f:
        f.write(content_md)

    save_processed(msg_id)
    print(f"  [OK] Saved: {obs_path.name}")
    conn.close()
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate Coach Steve's weekly MACD Obsidian file")
    parser.add_argument("--date", required=True, help="Date in YYYY-MM-DD format")
    parser.add_argument("--reprocess", action="store_true", help="Overwrite existing file")
    args = parser.parse_args()

    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"[ERROR] Invalid date format: {args.date}. Use YYYY-MM-DD.")
        sys.exit(1)

    print(f"Processing weekly MACD for {args.date}...")
    success = process_for_date(args.date, reprocess=args.reprocess)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
