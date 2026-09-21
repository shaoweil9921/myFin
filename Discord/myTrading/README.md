# Discord Trading Signal Pipeline

## Overview

Fetches Discord messages from tracked channels, parses trading signals, and stores them in PostgreSQL (`fintech` database).

## Scripts

| Script | Purpose |
|--------|---------|
| `01_schema_setup.py` | Creates DB schema (discord_account, discord_channel, discord_message, discord_trade_signal) |
| `03_fetch_messages.py` | Fetches new messages from Discord API, saves to `discord_message` |
| `02_parse_signals.py` | Parses messages into trade signals in `discord_trade_signal` |
| `add_channels.py` | Add new channels to track |
| `test_pipeline.py` | Validation tests — run after schema/parser changes |

## Usage

```bash
# Fetch new messages from all channels
python 03_fetch_messages.py

# Force re-fetch (ignore cursor, get latest)
python 03_fetch_messages.py --force

# Fetch from one channel only
python 03_fetch_messages.py --channel-id 2

# Parse unparsed messages into signals
python 02_parse_signals.py

# Dry run (preview without inserting)
python 02_parse_signals.py --dry-run

# Run validation tests
python test_pipeline.py
```

## Database Schema

### discord_message
Stores raw Discord messages.

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL | Internal PK |
| message_id | VARCHAR | Discord snowflake ID |
| channel_id | INT FK | -> discord_channel.id |
| author_id | VARCHAR | Discord user ID |
| author_username | VARCHAR | |
| content | TEXT | Raw message content |
| cleaned_content | TEXT | Discord markup stripped |
| embed_urls | JSONB | Array of URL strings |
| embed_images | JSONB | Array of image URL strings |
| attachments | JSONB | Array of attachment objects |
| message_timestamp | TIMESTAMPTZ | Discord server timestamp |
| author_posted_at | DATE | Parsed from content (e.g. "9/15/2026") |
| local_image_path | JSONB or TEXT | Array of local file paths |
| is_parsed | BOOLEAN | Whether signal was parsed |

### discord_trade_signal
Stores parsed trade signals.

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL | Internal PK |
| signal_id | UUID | Unique identifier |
| message_id | INT FK | -> discord_message.id |
| channel_id | INT FK | -> discord_channel.id |
| stock_ticker | VARCHAR | e.g. "MU", "SPY" |
| asset_class | VARCHAR | STOCK, OPTION, ETF, etc. |
| option_type | VARCHAR | CALL or PUT |
| strike_price | NUMERIC | e.g. 130.00 |
| expiration_date | DATE | Option expiry |
| entry_premium | NUMERIC | Price paid for option |
| trade_direction | VARCHAR | LONG or SHORT |
| entry_price | NUMERIC | Stock entry price |
| target_price | NUMERIC | |
| stop_loss | NUMERIC | |
| signal_status | VARCHAR | ACTIVE, CLOSED, CANCELLED |
| signal_date | DATE | Trade date |
| confidence | VARCHAR | HIGH, MEDIUM, LOW |

## Signal Validation Rules

A message only generates a signal if:

**Options** — ALL required:
- `option_type` — CALL or PUT
- `strike_price` — numeric strike
- `expiration_date` — parsed expiry date

**Stocks/ETF** — ALL required:
- `entry_price` — numeric purchase price
- `trade_direction` — LONG or SHORT

## Parser Behavior

- Only the **first ticker** in a message is used (`tickers[:1]`)
- Ticker extraction uses `\b[A-Z]{2,5}\b` regex, filtered against common-word blocklist
- Signals are deduplicated by `message_id` — each Discord message parsed once
- `author_posted_at` extracted from content like "TradingWithAshley — 9/15/2026 10:38 AM"
- Images saved to `C:\DiscordData\{channel_id}\{year}\{month}\{message_id}_att_{n}.png`

## Known Ticker False Positives (filtered)

- Strategy abbreviations: `CC`, `CSP`, `PMCC`, `CSP`
- Common words: `ETF`, `RSI`, `MACD`, `DJI`, `AM`, `PM`
- Financial acronyms: `FDA`, `SEC`, `FED`, `CPI`, `PPI`, etc.

## Image Storage

```
C:\DiscordData\
  {discord_channel_id}\
    {year}\
      {month}\
        {message_id}_att_0.png
        {message_id}_att_1.png
        {message_id}_emb_0.png
```

## Channels

| ID | Name | Discord ID |
|----|------|-----------|
| 1 | swl-small-trades | 1550893507118637096 |
| 2 | swl-challenge-trades | 1550930741309866065 |
| 3 | swl-coach-trades | 1551368477846143006 |
| 4 | swl-coach-weekly | 1551368575112183808 |

## Common Issues Fixed

1. **Missing message_timestamp** — parse_message() uses Discord `timestamp` field
2. **Literal 'null' strings in embed columns** — embed_urls/embed_images migrated to JSONB, insert uses `json.dumps() if non-empty else None`
3. **Duplicate signals** — parser now uses `tickers[:1]`, dedup by `message_id`
4. **FK violation on message_id** — signal.message_id references internal PK (discord_message.id), not Discord snowflake
5. **CC/covered call extracted as ticker** — "CC" added to COMMON_WORDS blocklist
