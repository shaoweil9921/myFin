import os, psycopg2, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
pw = os.environ.get('DB_PASSWORD', '')
c = psycopg2.connect(host='127.0.0.1', port=5432, dbname='fintech', user='postgres', password=pw)
cur = c.cursor()
cur.execute("select column_name from information_schema.columns where table_name='discord_trade_signal' order by ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print(cols)
cur.execute('select * from discord_trade_signal order by id desc limit 4')
for r in cur.fetchall():
    print(dict(zip(cols, r)))
cur.execute('select count(*), max(date) from stock_technical')
print('technical', cur.fetchone())
cur.execute('select count(*), max(scan_date) from finviz_screener')
print('finviz', cur.fetchone())
c.close()
