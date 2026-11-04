import os, psycopg2, sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
c = psycopg2.connect(host='127.0.0.1', port=5432, dbname='fintech', user='postgres', password=os.environ.get('DB_PASSWORD', ''))
cur = c.cursor()
cur.execute("select column_name from information_schema.columns where table_name='finviz_screener' order by ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print(cols)
cur.execute("select * from finviz_screener order by id desc limit 3")
for r in cur.fetchall():
    print(dict(zip(cols, r)))
c.close()
