import psycopg2
import json
import sys

DB_CONFIG = {
    'host': '127.0.0.1',
    'dbname': 'fintech',
    'user': 'postgres',
    'password': 'asdfghjk1234%',
    'port': 5432
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()

    # Step 1: Insert scan record
    cur.execute("""
        INSERT INTO scan (scan_name, scan_time, status, source) 
        VALUES ('GapperMid', NOW(), 'started', 'finviz') 
        RETURNING scan_id;
    """)
    scan_id = cur.fetchone()[0]
    print(f"SCAN_ID={scan_id}")

    # Step 2: Check already extracted
    cur.execute("""
        SELECT COUNT(*) FROM finviz_screener_scan_result r 
        JOIN scan s ON r.scan_id = s.scan_id 
        WHERE s.scan_name = %s AND DATE(s.scan_time) = CURRENT_DATE;
    """, ('GapperMid',))
    count = cur.fetchone()[0]
    print(f"Already extracted: {count}")

    if count > 0:
        cur.execute(f"UPDATE scan SET status='skipped', scan_note='Already extracted' WHERE scan_id={scan_id};")
        print("SKIPPED")
        conn.close()
        sys.exit(0)
    
    print("PROCEED")
    print(f"scan_id={scan_id}")
    conn.close()

if __name__ == '__main__':
    main()
