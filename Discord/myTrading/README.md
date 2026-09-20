# myTrading Discord Bot

OpenClaw-integrated Discord bot for trading research and alerts.

## Overview

- **Bot Name:** myTrading
- **Platform:** Discord (OpenClaw Gateway)
- **Repo:** https://github.com/shaoweil9921/myTrading
- **Bot Token:** stored in Windows env var `DISCORD_BOT_TOKEN`
- **Server ID:** `1550885500657737748` (SWL server)
- **Bot User ID:** `1550877390924812358`
- **Database:** `fintech` on 127.0.0.1:5432, user=postgres

## Tracked Channels

| DB ID | Channel ID | Name | Category |
|-------|-----------|------|----------|
| 1 | `1550893507118637096` | swl-small-trades | SWING |
| 2 | `1550930741309866065` | swl-challenge-trades | SWING |

## Architecture

```
Discord API
    ↓ (03_fetch_messages.py)
discord_message table
    ↓ (02_parse_signals.py)
discord_trade_signal table
```

### Pipeline Scripts

| Script | Purpose |
|--------|---------|
| `01_schema_setup.py` | Create/repair DB schema |
| `03_fetch_messages.py` | Fetch messages from Discord API → `discord_message` |
| `02_parse_signals.py` | Parse signals from messages → `discord_trade_signal` |

### Cron Jobs

| Job | Schedule | Script |
|-----|----------|--------|
| Fetch messages | Mon–Fri every 15 min (market hours) | `03_fetch_messages.py` |
| Parse signals | Mon–Fri 4:30 PM ET | `02_parse_signals.py` |

## Schema Summary

### `discord_account`
Bot account registry (1 row per bot).

### `discord_channel`
Channel registry with cursor (`last_message_id`). Name refreshed on each fetch.

### `discord_message`
Raw messages. Key columns:
- `id` — internal PK (BIGSERIAL)
- `account_id` → `discord_account.id`
- `channel_id` → `discord_channel.id`
- `message_id` — Discord snowflake
- `author_posted_at` — parsed from message content (e.g. "TradingWithAshley — 9/14/2026 3:24 PM"), used as `signal_date`
- `UNIQUE(channel_id, message_id)` prevents duplicates

### `discord_trade_signal`
Extracted signals. Key columns:
- `account_id` → `discord_account.id`
- `channel_id` → `discord_channel.id`
- `message_id` → `discord_message.id` (links signal back to source message)
- `signal_id` — UUID, unique constraint
- `stock_ticker` — used for BOTH stock and options (no separate `underlying_ticker`)
- `signal_date` — from `author_posted_at`; falls back to `message_timestamp` if missing
- `chk_expiry` — `expiration_date >= signal_date`

## Environment Variables

| Variable | Value |
|----------|-------|
| `DISCORD_BOT_TOKEN` | Discord bot token |
| `DB_PASSWORD` | PostgreSQL password (`asdfghjk1234%`) |

## Setup

```bash
# Run schema setup
python 01_schema_setup.py

# Fetch messages
python 03_fetch_messages.py --force  # bypasses market hours check

# Parse signals
python 02_parse_signals.py

# Re-parse from scratch (reset signals)
# 1. DELETE FROM discord_trade_signal;
# 2. python 02_parse_signals.py
```

## Key Bugs Fixed (2026-09-19/20)

1. **Cursor saved oldest msg** — Discord returns newest-first; code was saving the last (oldest) in batch. Fixed: `last_msg_id = messages[0]['id']`
2. **author_posted_at all NULL** — regex pattern didn't match "TradingWithAshley — 9/15/2026" format. Backfilled existing rows.
3. **Strike/premium/strategy not parsed for OPTIONS** — parsing code was in `else` branch (non-OPTION). Moved inside `if asset_class == 'OPTION'`.
4. **signal.message_id FK wrong table** — pointed to `discord_message_old_flat` (1 row). Fixed FK and backfilled via content match.
5. **message.account_id NULL** — `account_id` missing from INSERT. Added through full call chain.
6. **Column order bug** — INSERT VALUES had `channel_id, account_id` but DB column order is `account_id, channel_id`. Fixed.
7. **Duplicate SOFI signals** — dedup query used `message_id` FK which was broken. Replaced with `NOT EXISTS` on content prefix match.
8. **author_posted_at NULL → chk_expiry violation** — `signal_date` defaulted to today when `author_posted_at` was NULL, causing `expiration_date < signal_date` violations.

## Current Signals

| ID | Ticker | Asset | Strategy | Strike | Prem | Signal Date |
|----|--------|-------|----------|--------|------|------------|
| 2 | GGLL | STOCK | — | — | — | 2026-09-19 |
| 3 | SOFI | OPTION CALL | Covered Call | 18.50 | — | 2026-09-14 |
| 35 | MU | OPTION CALL | Covered Call | 1000 | 2.72 | 2026-09-15 |
| 36 | NBIS | OPTION CALL | Covered Call | 235 | 1.4 | 2026-09-15 |
