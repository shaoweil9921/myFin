"""01_schema_setup.py - Create new discord_* tables"""
import os, sys, psycopg2

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_CONFIG = {
    "host": "127.0.0.1", "port": 5432, "user": "postgres",
    "password": os.environ.get("DB_PASSWORD", ""), "dbname": "fintech",
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def run(conn, sql, params=None):
    cur = conn.cursor()
    cur.execute(sql, params or ())
    conn.commit()
    cur.close()

def is_old_flat(conn):
    """True if discord_message exists with VARCHAR channel_id (old flat schema)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'discord_message' AND column_name = 'channel_id'
          AND data_type = 'character varying'
    """)
    r = cur.fetchone()
    cur.close()
    return r is not None

def create_tables(conn):
    print("[SCHEMA] Creating tables...")

    # discord_account
    run(conn, """
        CREATE TABLE IF NOT EXISTS discord_account (
            id SERIAL PRIMARY KEY,
            account_name VARCHAR(100) NOT NULL,
            app_id VARCHAR(64) UNIQUE,
            owner_user_id VARCHAR(64),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    print("  [OK] discord_account")

    # discord_channel
    run(conn, """
        CREATE TABLE IF NOT EXISTS discord_channel (
            id SERIAL PRIMARY KEY,
            account_id INT REFERENCES discord_account(id) ON DELETE CASCADE,
            channel_id VARCHAR(64) NOT NULL,
            channel_name VARCHAR(255),
            server_id VARCHAR(64),
            server_name VARCHAR(255),
            category VARCHAR(50) DEFAULT 'GENERAL',
            is_tracking BOOLEAN DEFAULT TRUE,
            last_message_id VARCHAR(64),
            last_fetched_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(account_id, channel_id)
        )
    """)
    print("  [OK] discord_channel")

    # discord_message (before discord_trade_signal due to FK)
    run(conn, """
        CREATE TABLE IF NOT EXISTS discord_message (
            id BIGSERIAL PRIMARY KEY,
            account_id INT REFERENCES discord_account(id) ON DELETE SET NULL,
            channel_id INT REFERENCES discord_channel(id) ON DELETE SET NULL,
            message_id VARCHAR(64) NOT NULL,
            author_id VARCHAR(64) NOT NULL,
            author_username VARCHAR(255),
            author_nickname VARCHAR(255),
            author_roles TEXT[],
            content TEXT,
            cleaned_content TEXT,
            embed_titles TEXT,
            embed_descriptions TEXT,
            embed_urls TEXT[],
            embed_images TEXT[],
            attachments JSONB,
            reactions JSONB,
            thread_id VARCHAR(64),
            thread_name VARCHAR(255),
            reply_to_message_id VARCHAR(64),
            is_pinned BOOLEAN DEFAULT FALSE,
            message_type VARCHAR(50),
            has_mentions BOOLEAN DEFAULT FALSE,
            has_bot_mention BOOLEAN DEFAULT FALSE,
            edited_at TIMESTAMPTZ,
            message_timestamp TIMESTAMPTZ,
            author_posted_at TIMESTAMPTZ,
            raw_json JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(channel_id, message_id)
        )
    """)
    print("  [OK] discord_message")

    # discord_trade_signal
    run(conn, """
        CREATE TABLE IF NOT EXISTS discord_trade_signal (
            id BIGSERIAL PRIMARY KEY,
            account_id INT REFERENCES discord_account(id) ON DELETE SET NULL,
            channel_id INT REFERENCES discord_channel(id) ON DELETE SET NULL,
            message_id BIGINT REFERENCES discord_message(id) ON DELETE SET NULL,
            signal_id VARCHAR(64) NOT NULL UNIQUE,
            asset_class VARCHAR(20) NOT NULL DEFAULT 'STOCK',
            signal_status VARCHAR(20) DEFAULT 'ACTIVE',
            signal_date DATE NOT NULL,
            confidence VARCHAR(10),
            author_id VARCHAR(64),
            author_username VARCHAR(255),
            signal_text TEXT,
            tags TEXT[],
            stock_ticker VARCHAR(10),
            trade_direction VARCHAR(10),
            position_type VARCHAR(10),
            quantity NUMERIC(12,2),
            entry_price NUMERIC(12,4),
            entry_price_approx BOOLEAN DEFAULT FALSE,
            target_price NUMERIC(12,4),
            stop_loss NUMERIC(12,4),
            target_pct NUMERIC(8,2),
            stop_pct NUMERIC(8,2),
            risk_reward_ratio NUMERIC(6,2),
            notional_value NUMERIC(14,2),
            underlying_ticker VARCHAR(10),
            option_type VARCHAR(4),
            expiration_date DATE,
            strike_price NUMERIC(12,4),
            strike_type VARCHAR(10),
            contracts NUMERIC(8,2),
            entry_premium NUMERIC(12,4),
            entry_premium_approx BOOLEAN DEFAULT FALSE,
            target_premium NUMERIC(12,4),
            stop_premium NUMERIC(12,4),
            target_pct_opt NUMERIC(8,2),
            stop_pct_opt NUMERIC(8,2),
            risk_reward_ratio_opt NUMERIC(6,2),
            bid_ask_spread NUMERIC(8,4),
            delta NUMERIC(6,4),
            delta_target NUMERIC(6,4),
            exit_price NUMERIC(12,4),
            exit_date DATE,
            realized_pnl NUMERIC(14,2),
            realized_pnl_pct NUMERIC(8,2),
            closed_reason VARCHAR(50),
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            last_price_check TIMESTAMPTZ,
            CONSTRAINT chk_asset_class CHECK (asset_class IN ('STOCK','ETF','OPTION','FUTURE','FOREX','CRYPTO')),
            CONSTRAINT chk_option_type CHECK (option_type IN ('CALL','PUT') OR option_type IS NULL),
            CONSTRAINT chk_trade_dir CHECK (trade_direction IN ('LONG','SHORT') OR trade_direction IS NULL),
            CONSTRAINT chk_expiry CHECK (expiration_date IS NULL OR expiration_date >= signal_date)
        )
    """)
    print("  [OK] discord_trade_signal")

    # Indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_msg_account ON discord_message(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_msg_timestamp ON discord_message(message_timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_msg_author ON discord_message(author_id)",
        "CREATE INDEX IF NOT EXISTS idx_msg_pinned ON discord_message(is_pinned) WHERE is_pinned",
        "CREATE INDEX IF NOT EXISTS idx_chnl_account ON discord_channel(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_chnl_category ON discord_channel(category)",
        "CREATE INDEX IF NOT EXISTS idx_chnl_tracking ON discord_channel(is_tracking) WHERE is_tracking",
        "CREATE INDEX IF NOT EXISTS idx_signal_account ON discord_trade_signal(account_id)",
        "CREATE INDEX IF NOT EXISTS idx_signal_channel ON discord_trade_signal(channel_id)",
        "CREATE INDEX IF NOT EXISTS idx_signal_ticker ON discord_trade_signal(COALESCE(stock_ticker, underlying_ticker))",
        "CREATE INDEX IF NOT EXISTS idx_signal_date ON discord_trade_signal(signal_date DESC)",
        "CREATE INDEX IF NOT EXISTS idx_signal_status ON discord_trade_signal(signal_status)",
        "CREATE INDEX IF NOT EXISTS idx_signal_confidence ON discord_trade_signal(confidence)",
        "CREATE INDEX IF NOT EXISTS idx_signal_active ON discord_trade_signal(signal_date DESC) WHERE signal_status = 'ACTIVE'",
        "CREATE INDEX IF NOT EXISTS idx_signal_tags ON discord_trade_signal USING GIN (tags)",
        "CREATE INDEX IF NOT EXISTS idx_signal_expiry ON discord_trade_signal(expiration_date) WHERE asset_class = 'OPTION' AND signal_status = 'ACTIVE'",
    ]
    for sql in indexes:
        try:
            run(conn, sql)
        except Exception as e:
            print(f"  [WARN] {sql[:60]}: {e}")
    print("  [OK] indexes")


def seed_default(conn):
    """Seed default account and swl-small-trades channel."""
    # Ensure account
    run(conn, "INSERT INTO discord_account (account_name) VALUES ('Default Bot') ON CONFLICT DO NOTHING")
    cur = conn.cursor()
    cur.execute("SELECT id FROM discord_account WHERE account_name = 'Default Bot' LIMIT 1")
    row = cur.fetchone()
    account_id = row[0] if row else None
    if not account_id:
        print("[ERROR] Could not get default account")
        cur.close()
        return
    print(f"  [OK] Account: id={account_id}")

    # Seed swl-small-trades channel
    cur.execute("SELECT id FROM discord_channel WHERE channel_id = '1550893507118637096' LIMIT 1")
    if cur.fetchone():
        print("  [SKIP] Channel swl-small-trades already exists")
    else:
        run(conn, """
            INSERT INTO discord_channel (account_id, channel_id, channel_name, category, is_tracking)
            VALUES (%s, '1550893507118637096', 'swl-small-trades', 'SWING', TRUE)
        """, (account_id,))
        print("  [OK] Seeded swl-small-trades channel")
    cur.close()


def main():
    conn = get_conn()

    # Step 1: rename old flat table if it exists
    if is_old_flat(conn):
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM discord_message")
        cnt = cur.fetchone()[0]
        print(f"[MIGRATE] Old flat discord_message has {cnt} rows — renaming to backup")
        cur.execute("ALTER TABLE discord_message RENAME TO discord_message_old_flat")
        conn.commit()
        cur.close()
        print("  [OK] Backed up to discord_message_old_flat")

    # Step 2: create new schema
    create_tables(conn)

    # Step 3: seed defaults
    print("\n[SEED] Seeding defaults...")
    seed_default(conn)

    # Step 4: verify
    print("\n[VERIFY]")
    cur = conn.cursor()
    for tbl in ['discord_account', 'discord_channel', 'discord_message', 'discord_trade_signal']:
        cur.execute(f"SELECT COUNT(*) FROM {tbl}")
        print(f"  {tbl}: {cur.fetchone()[0]} rows")
    print("\n  discord_channel:")
    cur.execute("SELECT id, channel_id, channel_name, category, is_tracking FROM discord_channel")
    for r in cur.fetchall():
        print(f"    {r}")
    cur.close()
    conn.close()
    print("\n[DONE] Schema setup complete!")


if __name__ == "__main__":
    main()
