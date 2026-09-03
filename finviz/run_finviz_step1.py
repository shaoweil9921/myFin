import psycopg2, os, json

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', '127.0.0.1'),
    dbname=os.environ.get('DB_NAME', 'fintech'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)
cur = conn.cursor()

# Step 1: Insert scan record
cur.execute("""
    INSERT INTO scan (scan_name, scan_time, status, source)
    VALUES ('GapperMid', NOW(), 'started', 'finviz')
    RETURNING scan_id
""")
scan_id = cur.fetchone()[0]
conn.commit()
print('scan_id:', scan_id)

# Step 2: Check already extracted
cur.execute("""
    SELECT COUNT(*) FROM finviz_screener_scan_result r
    JOIN scan s ON r.scan_id = s.scan_id
    WHERE s.scan_name = 'GapperMid' AND DATE(s.scan_time) = CURRENT_DATE
""")
count = cur.fetchone()[0]
print('already_extracted:', count > 0, 'count:', count)

# If not extracted, update status to in_progress
if count == 0:
    cur.execute("UPDATE scan SET status='in_progress', scan_note='Loading screener' WHERE scan_id=%s", (scan_id,))
    conn.commit()
    print('status: in_progress')

cur.close()
conn.close()
print(json.dumps({'scan_id': scan_id, 'already_extracted': count > 0}))
