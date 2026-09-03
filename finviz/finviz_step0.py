import psycopg2

conn = psycopg2.connect(host='127.0.0.1', dbname='fintech', user='postgres', port=5432)
conn.autocommit = True
cur = conn.cursor()

# Step 0: Check holiday
cur.execute("SELECT holiday_name FROM market_holidays WHERE date = CURRENT_DATE;")
holiday = cur.fetchone()
print(f"Holiday check: {holiday}")

if holiday:
    # Check if scan exists
    cur.execute("SELECT scan_id FROM scan WHERE scan_name = 'GapperMid' AND DATE(scan_time) = CURRENT_DATE;")
    existing = cur.fetchone()
    if existing:
        cur.execute("UPDATE scan SET scan_time = NOW() WHERE scan_name = 'GapperMid' AND DATE(scan_time) = CURRENT_DATE;")
        print("Updated existing scan for holiday")
    else:
        cur.execute("INSERT INTO scan (scan_name, scan_time, status, source) VALUES ('GapperMid', NOW(), 'holiday', 'finviz');")
        print("Inserted holiday scan")
    print("MARKET HOLIDAY - SKIPPING")
    conn.close()
    exit(0)

print("No holiday - proceeding")

# Step 1: Insert scan record
cur.execute("INSERT INTO scan (scan_name, scan_time, status, source) VALUES ('GapperMid', NOW(), 'started', 'finviz') RETURNING scan_id;")
scan_id = cur.fetchone()[0]
print(f"Inserted scan_id: {scan_id}")

# Step 2: Check already extracted
cur.execute("""
    SELECT COUNT(*) FROM finviz_screener_scan_result r 
    JOIN scan s ON r.scan_id = s.scan_id 
    WHERE s.scan_name = 'GapperMid' AND DATE(s.scan_time) = CURRENT_DATE;
""")
count = cur.fetchone()[0]
print(f"Already extracted count: {count}")

if count > 0:
    cur.execute(f"UPDATE scan SET status='skipped', scan_note='Already extracted' WHERE scan_id={scan_id};")
    print("Already extracted - skipping")
    conn.close()
    exit(0)

print("Proceeding with extraction")
print(f"SCAN_ID={scan_id}")
conn.close()