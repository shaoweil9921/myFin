import psycopg2

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 5432,
    'dbname': 'fintech',
    'user': 'postgres',
    'password': 'asdfghjk1234%'
}

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
cur.execute("UPDATE scan SET status='failed', scan_note='Login required - blocked' WHERE scan_id=277;")
conn.commit()
conn.close()
print("Updated scan 277 to failed")
