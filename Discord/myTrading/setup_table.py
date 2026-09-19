import psycopg2

conn = psycopg2.connect(
    host='127.0.0.1', port=5432,
    user='postgres', password='asdfghjk1234%',
    dbname='fintech'
)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS discord_message (
    id SERIAL PRIMARY KEY,
    message_id VARCHAR(64) UNIQUE,
    channel_id VARCHAR(64),
    channel_name VARCHAR(255),
    author_id VARCHAR(64),
    author_username VARCHAR(255),
    content TEXT,
    embed_titles TEXT,
    embed_descriptions TEXT,
    attachments JSONB,
    raw_json JSONB,
    timestamp TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
)
""")
conn.commit()

# Check columns
cur.execute("""
SELECT column_name FROM information_schema.columns
WHERE table_name = 'discord_message'
ORDER BY ordinal_position
""")
print('Table columns:', [r[0] for r in cur.fetchall()])

# Create index
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_discord_message_channel_id ON discord_message(channel_id)
""")
cur.execute("""
CREATE INDEX IF NOT EXISTS idx_discord_message_timestamp ON discord_message(timestamp DESC)
""")
conn.commit()

cur.close()
conn.close()
print('Setup complete!')
