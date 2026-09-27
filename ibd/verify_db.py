import psycopg2
conn = psycopg2.connect(host='127.0.0.1', port=5432, dbname='fintech', user='postgres', password='asdfghjk1234%')
cur = conn.cursor()

checks = [
    ('2026-08-10', 22, 'SKWD'),
    ('2026-08-10', 25, 'ADPT'),
    ('2026-08-10', 38, 'PAY'),
    ('2026-08-10', 45, 'S'),
    ('2026-08-17', 28, 'ADPT'),
    ('2026-08-17', 36, 'SKWD'),
    ('2026-08-17', 49, 'TSM'),
    ('2026-08-17', 50, 'INSW'),
    # original user corrections
    ('2026-08-10', 26, 'ZETA'),
    ('2026-08-10', 27, 'SNOW'),
    ('2026-08-17', 26, 'DXCM'),
    ('2026-08-17', 27, 'ANET'),
    ('2026-08-17', 47, 'ERO'),
    ('2026-08-17', 48, 'IOT'),
]

all_ok = True
for date, rank, sym in checks:
    cur.execute('SELECT symbol, industry FROM ibd_50_new WHERE issue_date=%s AND rank=%s', (date, rank))
    r = cur.fetchone()
    ok = r and r[0] == sym
    if not ok:
        all_ok = False
    status = 'OK' if ok else 'FAIL'
    print(f'{status} {date} R{rank}: DB={r}, expected symbol={sym}')

print()
cur.execute('SELECT count(*) FROM ibd_50_new WHERE issue_date = %s', ('2026-08-10',))
print(f"Aug 10 count: {cur.fetchone()[0]}")
cur.execute('SELECT count(*) FROM ibd_50_new WHERE issue_date = %s', ('2026-08-17',))
print(f"Aug 17 count: {cur.fetchone()[0]}")
print(f'\nAll OK: {all_ok}')
conn.close()
