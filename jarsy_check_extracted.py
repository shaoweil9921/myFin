"""
Check if today's Jarsy extraction already completed.
Scans the scan table for a completed scan today.
"""
import psycopg2, sys

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'dbname': 'fintech',
    'user': 'postgres',
    'password': 'asdfghjk1234%'
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

conn = get_conn()
cur = conn.cursor()
cur.execute("""
    SELECT scan_id, status FROM scan
    WHERE scan_name = 'Jarsy Presale'
      AND DATE(scan_time) = CURRENT_DATE
      AND status = 'completed';
""")
row = cur.fetchone()
conn.close()

if row:
    print(f"ALREADY_DONE: scan_id={row[0]}, status={row[1]}")
    sys.exit(0)
else:
    print("NOT_YET_DONE")
    sys.exit(1)
