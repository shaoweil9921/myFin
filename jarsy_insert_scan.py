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

conn = get_conn()
cur = conn.cursor()
cur.execute("INSERT INTO scan (scan_name, scan_time, status, source) VALUES ('Jarsy Presale', NOW(), 'started', 'jarsy') RETURNING scan_id;")
scan_id = cur.fetchone()[0]
conn.commit()
conn.close()
print(f"scan_id={scan_id}")
