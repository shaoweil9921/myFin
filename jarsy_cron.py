import psycopg2
import sys

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'dbname': 'fintech',
    'user': 'postgres',
    'password': 'asdfghjk1234%'
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

# Step 0: Check market holiday
conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT holiday_name FROM market_holidays WHERE date = CURRENT_DATE;")
holiday = cur.fetchone()
conn.close()

if holiday:
    print(f"HOLIDAY: {holiday[0]}")
    # Check if scan exists
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT scan_id FROM scan WHERE scan_name = 'Jarsy Presale' AND DATE(scan_time) = CURRENT_DATE;")
    existing = cur.fetchone()
    if existing:
        cur.execute("UPDATE scan SET scan_time = NOW() WHERE scan_name = 'Jarsy Presale' AND DATE(scan_time) = CURRENT_DATE;")
    else:
        cur.execute("INSERT INTO scan (scan_name, scan_time, status, source) VALUES ('Jarsy Presale', NOW(), 'holiday', 'jarsy');")
    conn.commit()
    conn.close()
    print("Market holiday - scan marked as holiday, exiting.")
    sys.exit(0)

print("NO_HOLIDAY")
