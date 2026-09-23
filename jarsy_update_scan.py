import psycopg2

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'dbname': 'fintech',
    'user': 'postgres',
    'password': 'asdfghjk1234%'
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def update_scan(scan_id, status, note):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE scan SET status=%s, scan_note=%s WHERE scan_id=%s;", (status, note, scan_id))
    conn.commit()
    conn.close()

# update_scan(277, 'in_progress', 'Extracting Presale')
if __name__ == '__main__':
    import sys
    scan_id = int(sys.argv[1])
    status = sys.argv[2]
    note = sys.argv[3]
    update_scan(scan_id, status, note)
    print("Updated")
