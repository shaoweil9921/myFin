# Discord Trading Signal Pipeline

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

## Message Format Requirement

Messages **must** have a `TradingWithAshley` header to be parsed:

```
TradingWithAshley — 9/15/2026 10:38 AM
Ticker: MU
Strategy: Covered Call
Expiration: 9/18/26
Strike: 1000
Premium: $2.72
```

The parser extracts `author_posted_at` from this header (e.g. `9/15/2026 10:38 AM`) and uses it as `signal_date`. Messages without this header are fetched and saved to DB but will not generate signals.

## Signal Validation Rules

A message only generates a signal if it passes the header check AND:

**Options** — ALL required:
- `option_type` — CALL, PUT, or inferred from strategy (LEAPS defaults to CALL)
- `strike_price` — numeric strike
- `expiration_date` — parsed expiry date

**Stocks/ETF** — ALL required:
- `entry_price` — numeric purchase price
- `trade_direction` — LONG or SHORT

**LEAPS** — Special case:
- `strategy_type` containing "LEAP" or "LEAPS" is recognized as `OPTION` asset class
- `option_type` defaults to `CALL` (LEAPS are typically long-dated calls)
- Still requires `strike_price` and `expiration_date`

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
- **Note:** Major tickers like NVDA, TSLA, AAPL, MSFT, AMZN, GOOGL, META are NOT in the blocklist — they are real tickers and must pass through.

## Database Schema

### discord_trade_signal (key columns)

| Column | Type | Notes |
|--------|------|-------|
| stock_ticker | VARCHAR | e.g. "MU", "SPY" |
| asset_class | VARCHAR | STOCK, OPTION, ETF, etc. |
| option_type | VARCHAR | CALL or PUT |
| strategy_type | VARCHAR | e.g. Covered Call, LEAPS, Iron Condor |
| strike_price | NUMERIC | e.g. 130.00 |
| expiration_date | DATE | Option expiry |
| entry_premium | NUMERIC | Price paid for option |
| premium_price | NUMERIC | Alias for entry_premium (both set) |
| trade_direction | VARCHAR | LONG or SHORT |
| entry_price | NUMERIC | Stock entry price |
| target_price | NUMERIC | |
| stop_loss | NUMERIC | |
| risk_reward_ratio | NUMERIC | For stock trades |
| risk_reward_ratio_opt | NUMERIC | For option trades |
| signal_status | VARCHAR | ACTIVE, CLOSED, EXPIRED, CANCELLED |
| signal_date | DATE | Trade date |
| confidence | VARCHAR | HIGH, MEDIUM, LOW |

### discord_message (key columns)

| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL | Internal PK |
| message_id | VARCHAR | Discord snowflake ID |
| channel_id | INT FK | -> discord_channel.id |
| author_username | VARCHAR | |
| content | TEXT | Raw message content |
| cleaned_content | TEXT | Discord markup stripped |
| message_timestamp | TIMESTAMPTZ | Discord server timestamp |
| author_posted_at | TIMESTAMPTZ | Parsed from content header |

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
6. **LEAPS not recognized** — parser now detects "LEAPS"/"LEAP" strategy, defaults option_type to CALL
7. **LEAPS messages skipped** — signal filter now allows LEAPS through without literal "call"/"put" in text
8. **Cursor behind — messages missed** — channel 2 cursor `last_message_id` set to unsaved message ID; fix: manually update cursor to newest saved message ID in `discord_channel`
9. **NVDA/TSLA/AAPL/MSFT/AMZN/GOOGL/META filtered as tickers** — these real tickers were in COMMON_WORDS blocklist, causing wrong ticker extraction (e.g. MA instead of NVDA). Removed from blocklist.
10. **Month-name expiry not parsed** — `EXPIRY_RE` only matched numeric format like `10/16/2026`. Added support for `OCT 16, 2026` format.
11. **`Strike(s): $560` not matched** — the `(s)` in the label broke the strike regex. Updated to `strike(?:\s*\(s\))?`.
12. **`Strategy: CSP` not detected as strategy** — `STRATEGY_LINE_RE` used `^` anchor (line start), but `clean_text` collapses newlines to spaces, so "Strategy:" was never at line start. Removed `^` anchor.
13. **`CSP`/Sold Put/CC/Covered Call not mapped to option_type** — parser only checked raw `call`/`put` keywords. Added strategy-based option_type inference: CSP/Sold Put → PUT, CC/Covered Call → CALL.
14. **Premium $10.80 not captured for CSP** — CSP messages use `Entry: $10.80 credit` (not `Premium:`). Added credit-pattern detection for CSP/Sold Put to capture entry credit as premium.
