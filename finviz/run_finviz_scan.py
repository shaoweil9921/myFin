import psycopg2
import json
import sys

DB_PASSWORD = 'asdfghjk1234%'

def get_conn():
    return psycopg2.connect(host='127.0.0.1', database='fintech', user='postgres', password=DB_PASSWORD)

def check_holiday():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('SELECT holiday_name FROM market_holidays WHERE date = CURRENT_DATE')
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def insert_scan():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO scan (scan_name, scan_time, status, source) VALUES ('GapperMid', NOW(), 'started', 'finviz') RETURNING scan_id")
    scan_id = cur.fetchone()[0]
    conn.commit()
    conn.close()
    return scan_id

def update_scan(scan_id, status, note):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE scan SET status = %s, scan_note = %s WHERE scan_id = %s", (status, note, scan_id))
    conn.commit()
    conn.close()

def check_already_extracted(scan_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM finviz_screener_scan_result r 
        JOIN scan s ON r.scan_id = s.scan_id 
        WHERE s.scan_name = 'GapperMid' AND DATE(s.scan_time) = CURRENT_DATE
    """)
    count = cur.fetchone()[0]
    conn.close()
    return count > 0

if __name__ == '__main__':
    action = sys.argv[1]
    
    if action == 'check_holiday':
        result = check_holiday()
        print(result if result else 'NO_HOLIDAY')
    elif action == 'insert_scan':
        scan_id = insert_scan()
        print(scan_id)
    elif action == 'update_scan':
        scan_id = int(sys.argv[2])
        status = sys.argv[3]
        note = sys.argv[4]
        update_scan(scan_id, status, note)
        print('OK')
    elif action == 'check_extracted':
        scan_id = int(sys.argv[2])
        result = check_already_extracted(scan_id)
        print('YES' if result else 'NO')
