
from db_pw import get_db_pw as _db_pw
import psycopg2
conn = psycopg2.connect(user='postgres', host='127.0.0.1', database='fintech', password=_db_pw())
cur = conn.cursor()
cur.execute("UPDATE scan SET status='login_required', scan_note='Google OAuth login needed - session expired' WHERE scan_id=120")
conn.commit()
print("Updated scan 120 to login_required")
conn.close()