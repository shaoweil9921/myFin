
from _db_pw import get_db_pw as _db_pw
import psycopg2

DB_CONFIG = {
    'host': '127.0.0.1',
    'dbname': 'fintech',
    'user': 'postgres',
    'password': _db_pw(),
    'port': 5432
}

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = True
    cur = conn.cursor()
    
    scan_id = 215
    cur.execute(f"UPDATE scan SET status='completed', scan_note='Completed' WHERE scan_id={scan_id};")
    print("Updated scan status to completed")
    conn.close()

if __name__ == '__main__':
    main()
