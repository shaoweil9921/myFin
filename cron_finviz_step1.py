import psycopg2

conn = psycopg2.connect(host='127.0.0.1', port=5432, user='postgres', password='asdfghjk1234%', database='fintech')
cur = conn.cursor()

# Step 2: Check already extracted
cur.execute("SELECT COUNT(*) FROM finviz_screener_scan_result r JOIN scan s ON r.scan_id = s.scan_id WHERE s.scan_name = 'GapperMid' AND DATE(s.scan_time) = CURRENT_DATE")
count = cur.fetchone()[0]
print(f"Already extracted count: {count}")

if count > 0:
    cur.execute("UPDATE scan SET status='skipped', scan_note='Already extracted' WHERE scan_name = 'GapperMid' AND DATE(scan_time) = CURRENT_DATE")
    conn.commit()
    print("Already extracted today - skipping")
    conn.close()
    exit(0)

# Step 1: Insert scan record
cur.execute("INSERT INTO scan (scan_name, scan_time, status, source) VALUES ('GapperMid', NOW(), 'started', 'finviz') RETURNING scan_id")
scan_id = cur.fetchone()[0]
conn.commit()
print(f"Inserted scan_id: {scan_id}")

conn.close()
print(f"scan_id={scan_id}")