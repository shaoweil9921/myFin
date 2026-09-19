# Discord Trading Bot — Database Redesign

## Schema: `fintech` schema, objects prefixed `discord_`

---

## 1. `discord_account`

Stores Discord bot account(s). One row per bot.

| Column | Type | Notes |
|--------|------|-------|
| `id` | SERIAL PK | |
| `account_name` | VARCHAR(100) | friendly name, e.g. "Main Bot" |
| `bot_token` | VARCHAR(256) | encrypted, set via env override |
| `app_id` | VARCHAR(64) | Discord application ID |
| `owner_user_id` | VARCHAR(64) | Discord user ID of owner |
| `is_active` | BOOLEAN DEFAULT TRUE | |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ DEFAULT NOW() | |

**Indexes:** `UNIQUE(app_id)`, `idx_active`

---

## 2. `discord_channel`

Normalized channel registry. One row per tracked channel.

| Column | Type | Notes |
|--------|------|-------|
| `id` | SERIAL PK | |
| `account_id` | INT FK | → `discord_account.id` |
| `channel_id` | VARCHAR(64) | Discord channel ID, UNIQUE within account |
| `channel_name` | VARCHAR(255) | current name in Discord |
| `server_id` | VARCHAR(64) | Discord guild ID |
| `server_name` | VARCHAR(255) | current guild name |
| `category` | VARCHAR(50) | e.g. SWING, DAY_TRADE, OPTIONS, WATCHLIST, GENERAL |
| `is_tracking` | BOOLEAN DEFAULT TRUE | enable/disable without removing |
| `last_message_id` | VARCHAR(64) | last successfully fetched message ID (cursor) |
| `last_fetched_at` | TIMESTAMPTZ | |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ DEFAULT NOW() | |

**Indexes:** `UNIQUE(account_id, channel_id)`, `idx_server`, `idx_category`, `idx_tracking`

---

## 3. `discord_message`

Raw messages fetched from Discord.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `account_id` | INT FK | → `discord_account.id` |
| `channel_id` | INT FK | → `discord_channel.id` |
| `message_id` | VARCHAR(64) NOT NULL | Discord message ID |
| `author_id` | VARCHAR(64) NOT NULL | Discord user ID |
| `author_username` | VARCHAR(255) | |
| `author_nickname` | VARCHAR(255) | nickname in server |
| `author_roles` | TEXT[] | role names at time of fetch |
| `content` | TEXT | raw content |
| `cleaned_content` | TEXT | mentions/bold/italic stripped |
| `embed_titles` | TEXT | newline-joined embed titles |
| `embed_descriptions` | TEXT | newline-joined embed descriptions |
| `embed_urls` | TEXT[] | URLs from embeds |
| `embed_images` | TEXT[] | image URLs from embeds |
| `attachments` | JSONB | `[{filename, url, size, content_type}]` |
| `reactions` | JSONB | `[{emoji, count, user_ids}]` |
| `thread_id` | VARCHAR(64) | |
| `thread_name` | VARCHAR(255) | |
| `reply_to_message_id` | VARCHAR(64) | if this is a reply |
| `is_pinned` | BOOLEAN DEFAULT FALSE | |
| `message_type` | VARCHAR(50) | DEFAULT, REPLY, THREAD_STARTER, etc. |
| `has_mentions` | BOOLEAN DEFAULT FALSE | |
| `has_bot_mention` | BOOLEAN DEFAULT FALSE | |
| `edited_at` | TIMESTAMPTZ | |
| `message_timestamp` | TIMESTAMPTZ | Discord timestamp |
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |

**Constraints:** `UNIQUE(channel_id, message_id)`
**Indexes:** `idx_msg_account`, `idx_msg_timestamp DESC`, `idx_msg_author`,
             `idx_msg_mentions WHERE has_mentions`, `idx_msg_pinned`

---

## 4. `discord_trade_signal`

Extracted trade signals — supports both **stock/ETF** and **options** trades.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGSERIAL PK | |
| `account_id` | INT FK | → `discord_account.id` |
| `channel_id` | INT FK | → `discord_channel.id` |
| `message_id` | BIGINT FK | → `discord_message.id` (nullable, if message was saved) |
| `signal_id` | VARCHAR(64) NOT NULL UNIQUE | UUID from extractor |

### Classification
| Column | Type | Notes |
|--------|------|-------|
| `asset_class` | VARCHAR(20) NOT NULL | STOCK, ETF, OPTION, FUTURE, FOREX, CRYPTO |
| `signal_status` | VARCHAR(20) DEFAULT 'ACTIVE' | ACTIVE, CLOSED, EXPIRED, CANCELLED |
| `signal_date` | DATE NOT NULL | when signal was published |
| `confidence` | VARCHAR(10) | HIGH, MEDIUM, LOW |

### Author / Source
| Column | Type | Notes |
|--------|------|-------|
| `author_id` | VARCHAR(64) | Discord user ID |
| `author_username` | VARCHAR(255) | Discord username |
| `signal_text` | TEXT | original message text that triggered extraction |
| `tags` | TEXT[] | GIN indexed — earnings, momentum, breakout, etc. |

### ── STOCK / ETF fields ─────────────────────────────────
*(NULL when asset_class = OPTION)*

| Column | Type | Notes |
|--------|------|-------|
| `stock_ticker` | VARCHAR(10) | normalized uppercase |
| `trade_direction` | VARCHAR(10) | LONG, SHORT |
| `position_type` | VARCHAR(10) | SHARES, OPTION (for stock play via option) |
| `quantity` | NUMERIC(12,2) | shares (or notional for options-based stock plays) |
| `entry_price` | NUMERIC(12,4) | |
| `entry_price_approx` | BOOLEAN DEFAULT FALSE | True if entry was marked ~ |
| `target_price` | NUMERIC(12,4) | |
| `stop_loss` | NUMERIC(12,4) | |
| `target_pct` | NUMERIC(8,2) | calculated % gain |
| `stop_pct` | NUMERIC(8,2) | calculated % loss |
| `risk_reward_ratio` | NUMERIC(6,2) | target_pct / stop_pct |
| `notional_value` | NUMERIC(14,2) | quantity × entry_price |

### ── OPTIONS fields ─────────────────────────────────────
*(NULL when asset_class = STOCK/ETF)*

| Column | Type | Notes |
|--------|------|-------|
| `underlying_ticker` | VARCHAR(10) | e.g. AAPL (for the option) |
| `option_type` | VARCHAR(4) | CALL or PUT |
| `expiration_date` | DATE | option expiry |
| `strike_price` | NUMERIC(12,4) | strike |
| `strike_type` | VARCHAR(10) | ITM, OTM, ATM (computed) |
| `contracts` | NUMERIC(8,2) | number of contracts (1 contract = 100 shares) |
| `entry_premium` | NUMERIC(12,4) | premium paid per share |
| `entry_premium_approx` | BOOLEAN DEFAULT FALSE | |
| `target_premium` | NUMERIC(12,4) | target premium |
| `stop_premium` | NUMERIC(12,4) | stop premium |
| `target_pct_opt` | NUMERIC(8,2) | % gain on premium |
| `stop_pct_opt` | NUMERIC(8,2) | % loss on premium |
| `risk_reward_ratio_opt` | NUMERIC(6,2) | |
| `bid_ask_spread` | NUMERIC(8,4) | observed spread at entry |
| `delta` | NUMERIC(6,4) | theoretical delta at entry (optional) |
| `delta_target` | NUMERIC(6,4) | target delta for exit |

### Position tracking
| Column | Type | Notes |
|--------|------|-------|
| `exit_price` | NUMERIC(12,4) | actual exit price |
| `exit_date` | DATE | |
| `realized_pnl` | NUMERIC(14,2) | realized P&L in $ |
| `realized_pnl_pct` | NUMERIC(8,2) | as % of notional |
| `closed_reason` | VARCHAR(50) | TARGET_HIT, STOPPED, TIME_STOP, MANUAL |
| `notes` | TEXT | |

### Audit
| Column | Type | Notes |
|--------|------|-------|
| `created_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `updated_at` | TIMESTAMPTZ DEFAULT NOW() | |
| `last_price_check` | TIMESTAMPTZ | when price was last updated |

**Indexes:**
- `UNIQUE(signal_id)`
- `idx_signal_account`
- `idx_signal_channel`
- `idx_signal_ticker` — `stock_ticker` or `underlying_ticker`
- `idx_signal_date DESC`
- `idx_signal_status`
- `idx_signal_confidence`
- `idx_signal_active` — partial on `(stock_ticker, signal_date DESC) WHERE signal_status = 'ACTIVE'`
- `idx_signal_tags` — GIN on `tags`
- `idx_signal_expiry` — partial on `(expiration_date) WHERE asset_class = 'OPTION' AND signal_status = 'ACTIVE'`

**Constraints:**
- `CHECK (asset_class IN ('STOCK','ETF','OPTION','FUTURE','FOREX','CRYPTO'))`
- `CHECK (option_type IN ('CALL','PUT') OR option_type IS NULL)`
- `CHECK (trade_direction IN ('LONG','SHORT') OR trade_direction IS NULL)`
- `CHECK (expiration_date >= signal_date)`

---

## 5. Cron Job: Fetch Discord Messages

**Schedule:** Every 15 minutes, Mon–Fri, only during market hours
**Market hours check:** `public.market_holidays` + `9:30–16:00 ET`

Uses `channel.last_message_id` as cursor — only fetches messages **newer** than last fetch.

```sql
-- Market hours check (inside trigger script):
SELECT NOT EXISTS (
    SELECT 1 FROM public.market_holidays
    WHERE date = CURRENT_DATE
) AND
    CURRENT_TIME BETWEEN '09:30:00' AND '16:00:00'
    AND EXTRACT(DOW FROM CURRENT_DATE) BETWEEN 1 AND 5
```

---

## Summary of Tables

| Table | Purpose |
|-------|---------|
| `discord_account` | Bot account registry |
| `discord_channel` | Channel registry with cursor + category |
| `discord_message` | Raw messages |
| `discord_trade_signal` | Extracted signals (stock + options) |

**Prefix:** `discord_` throughout.
