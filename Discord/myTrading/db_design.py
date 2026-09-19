"""
Database Schema Design - myTrading Discord Bot
Denormalized discord_message + trading_signals table
"""

DENORMALIZED_DISCORD_MESSAGE = """
-- ============================================================
-- Table: discord_message (DENORMALIZED)
-- ============================================================
-- Stores every raw message with enriched/denormalized fields
-- so queries never need joins.

CREATE TABLE IF NOT EXISTS discord_message (
    -- Primary / Identity
    id              BIGSERIAL PRIMARY KEY,
    message_id      VARCHAR(64)  NOT NULL UNIQUE,
    channel_id      VARCHAR(64)  NOT NULL,
    channel_name    VARCHAR(255),
    server_id       VARCHAR(64),
    server_name     VARCHAR(255),

    -- Author (denormalized from Discord)
    author_id       VARCHAR(64)  NOT NULL,
    author_username VARCHAR(255),
    author_nickname VARCHAR(255),   -- nickname in this server
    author_roles    TEXT[],          -- array of role names

    -- Message Content
    content         TEXT,
    cleaned_content TEXT,            -- stripped mentions/formatting

    -- Embeds (denormalized)
    embed_titles       TEXT,
    embed_descriptions  TEXT,
    embed_urls          TEXT[],      -- URLs from embeds
    embed_images        TEXT[],      -- image URLs from embeds

    -- Attachments
    attachments         JSONB,        -- [{filename, url, size, content_type}]

    -- Thread / Reply context
    thread_id           VARCHAR(64),
    thread_name         VARCHAR(255),
    reply_to_message_id VARCHAR(64),  -- if this is a reply
    is_pinned           BOOLEAN DEFAULT FALSE,

    -- Reactions (denormalized - top N)
    reactions           JSONB,        -- [{emoji, count, users}]

    -- Timestamps
    timestamp           TIMESTAMPTZ,
    edited_at           TIMESTAMPTZ,

    -- Metadata
    has_mentions       BOOLEAN DEFAULT FALSE,
    has_bot_mention     BOOLEAN DEFAULT FALSE,
    message_type        VARCHAR(50),  -- DEFAULT, REPLY, THREAD_STARTER, etc.

    -- Raw
    raw_json            JSONB,

    -- Audit
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_msg_channel_id    ON discord_message(channel_id);
CREATE INDEX IF NOT EXISTS idx_msg_server_id     ON discord_message(server_id);
CREATE INDEX IF NOT EXISTS idx_msg_timestamp     ON discord_message(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_msg_author_id     ON discord_message(author_id);
CREATE INDEX IF NOT EXISTS idx_msg_mentions     ON discord_message(has_mentions) WHERE has_mentions = TRUE;
CREATE INDEX IF NOT EXISTS idx_msg_ticker        ON discord_message(UPPER(content))  -- partial index for tickers
    WHERE content ~* '\\b[A-Z]{2,5}\\b';
"""


TRADING_SIGNALS = """
-- ============================================================
-- Table: trading_signal
-- ============================================================
-- Extracted trading signals from Discord messages.
-- Populated by parse_signals.py (separate script).

CREATE TABLE IF NOT EXISTS trading_signal (
    id                  BIGSERIAL PRIMARY KEY,
    signal_id           VARCHAR(64)  NOT NULL UNIQUE,  -- UUID from script

    -- Ticker
    ticker              VARCHAR(10)  NOT NULL,
    ticker_normalized   VARCHAR(10)  NOT NULL,  -- uppercase

    -- Strategy
    strategy_type       VARCHAR(50),            -- SWING, DAY, OPTIONS, FUTURES, etc.
    trade_direction     VARCHAR(10),             -- LONG, SHORT, BULL, BEAR, CALL, PUT

    -- Entry
    entry_price         NUMERIC(12, 4),
    entry_price_approx  BOOLEAN DEFAULT FALSE,  -- True if ~ (approx) was in text
    entry_date          DATE,

    -- Targets / Stops
    target_price        NUMERIC(12, 4),
    stop_loss           NUMERIC(12, 4),
    target_pct          NUMERIC(8, 2),          -- calculated %
    stop_pct            NUMERIC(8, 2),

    -- Position sizing
    position_size       VARCHAR(100),            -- textual: "100 shares", "5 contracts"
    notional_value      NUMERIC(14, 2),

    -- Risk/Reward
    risk_reward_ratio   NUMERIC(6, 2),

    -- Metadata from message
    source_message_id   VARCHAR(64) REFERENCES discord_message(message_id),
    source_channel_id   VARCHAR(64),
    source_channel_name VARCHAR(255),
    source_server_name  VARCHAR(255),
    author_username     VARCHAR(255),

    -- Signal text (original line that triggered extraction)
    signal_text         TEXT,
    confidence          VARCHAR(20),             -- HIGH, MEDIUM, LOW

    -- Tags / Categorization
    tags                TEXT[],                  -- [earnings, momentum, breakout, etc.]
    sector              VARCHAR(100),
    asset_class         VARCHAR(50),             -- STOCK, OPTION, ETF, FOREX, CRYPTO

    -- Status tracking
    status              VARCHAR(20) DEFAULT 'ACTIVE',  -- ACTIVE, TARGET_HIT, STOPPED, EXPIRED, CLOSED
    target_hit_date     DATE,
    stopped_date        DATE,
    closed_date         DATE,
    notes               TEXT,

    -- Timestamps
    signal_date         DATE NOT NULL,          -- when the signal was published
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),

    -- Uniqueness
    CONSTRAINT unique_ticker_signal_date UNIQUE (ticker, signal_date, entry_price)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_signal_ticker         ON trading_signal(ticker_normalized);
CREATE INDEX IF NOT EXISTS idx_signal_date            ON trading_signal(signal_date DESC);
CREATE INDEX IF NOT EXISTS idx_signal_status          ON trading_signal(status);
CREATE INDEX IF NOT EXISTS idx_signal_type            ON trading_signal(strategy_type);
CREATE INDEX IF NOT EXISTS idx_signal_channel         ON trading_signal(source_channel_id);
CREATE INDEX IF NOT EXISTS idx_signal_confidence      ON trading_signal(confidence);

-- Partial indexes for active signals
CREATE INDEX IF NOT EXISTS idx_signal_active
    ON trading_signal(ticker_normalized, signal_date DESC)
    WHERE status = 'ACTIVE';

-- GIN index for tags
CREATE INDEX IF NOT EXISTS idx_signal_tags
    ON trading_signal USING GIN (tags);
"""
