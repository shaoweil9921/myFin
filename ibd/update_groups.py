import psycopg2

conn = psycopg2.connect(host='127.0.0.1', port=5432, dbname='fintech', user='postgres', password='asdfghjk1234%')
cur = conn.cursor()

updates = {
    ('2026-08-10', 'SKWD'): 'Grp60',
    ('2026-08-10', 'ADPT'): 'Grp76',
    ('2026-08-10', 'PAY'):  'Grp68',
    ('2026-08-10', 'S'):    'Grp3',
    ('2026-08-17', 'ADPT'): 'Grp82',
    ('2026-08-17', 'SKWD'): 'Grp64',
    ('2026-08-17', 'TSM'):  'Grp42',
    ('2026-08-17', 'INSW'): 'Grp9',
}

for (date, sym), group in updates.items():
    cur.execute("UPDATE ibd_50_new SET industry = %s WHERE issue_date = %s AND symbol = %s", (group, date, sym))
    print(f"Updated {date} {sym} -> {group} ({cur.rowcount} rows)")

conn.commit()
cur.execute("SELECT issue_date, rank, symbol, industry FROM ibd_50_new WHERE issue_date IN ('2026-08-10','2026-08-17') AND symbol IN ('SKWD','ADPT','PAY','S','TSM','INSW') ORDER BY issue_date, rank")
for r in cur.fetchall(): print(f"  {r}")
conn.close()
print("Done.")
