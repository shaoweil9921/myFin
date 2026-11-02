
from db_pw import get_db_pw as _db_pw
import psycopg2
DB_CONFIG = {'host': '127.0.0.1', 'port': 5432, 'dbname': 'fintech', 'user': 'postgres', 'password': _db_pw()}
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()
cur.execute("UPDATE scan SET status='failed' WHERE scan_id=298")
conn.commit()
print('Scan 298 marked failed')
cur.close()
conn.close()
