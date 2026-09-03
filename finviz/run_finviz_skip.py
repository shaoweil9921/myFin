import psycopg2, os

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', '127.0.0.1'),
    dbname=os.environ.get('DB_NAME', 'fintech'),
    user=os.environ.get('DB_USER'),
    password=os.environ.get('DB_PASSWORD')
)
cur = conn.cursor()
cur.execute("UPDATE scan SET status='skipped', scan_note='Already extracted' WHERE scan_id=284")
conn.commit()
cur.close()
conn.close()
print("Updated scan 284 to skipped")
