import psycopg2, os

DB_CONFIG = {'host': '127.0.0.1', 'port': 5432, 'user': 'postgres',
             'password': os.environ.get('DB_PASSWORD', ''), 'dbname': 'fintech'}
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Create table
cur.execute("""
    CREATE TABLE IF NOT EXISTS discord_watchlist (
        id SERIAL PRIMARY KEY,
        watch_name VARCHAR(100) NOT NULL UNIQUE,
        tickers TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
""")
conn.commit()
print('Table created / already exists')

# Insert Red Day Buys
tickers = 'DRAM,SPMO,AIPO,MU,WDC,STX,GEV,BE,LRCX,SNDK,AMD,GLW,ANET,CEG,QQQ'
cur.execute("""
    INSERT INTO discord_watchlist (watch_name, tickers)
    VALUES (%s, %s)
    ON CONFLICT DO NOTHING
""", ('TWA Red Day Buys', tickers))
conn.commit()
print(f'Inserted: {cur.rowcount} row(s)')
print(f'Tickers: {tickers}')

# Show all
cur.execute('SELECT id, watch_name, tickers, created_at FROM discord_watchlist ORDER BY id')
print('\nAll watchlists:')
for r in cur.fetchall():
    print(f'  [{r[0]}] {r[1]}')
    print(f'       {r[2]}')
    print(f'       created: {r[3]}')

cur.close()
conn.close()
