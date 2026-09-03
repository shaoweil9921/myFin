import psycopg2

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
    
    scan_id = 215
    cur.execute(f"UPDATE scan SET status='in_progress', scan_note='Loading screener' WHERE scan_id={scan_id};")
    print("Updated scan status to in_progress")
    conn.close()

if __name__ == '__main__':
    main()
