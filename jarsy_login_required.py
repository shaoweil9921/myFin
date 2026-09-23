import psycopg2

conn = psycopg2.connect(user='postgres', host='127.0.0.1', database='fintech', password='asdfghjk1234%')
conn.autocommit = True
cur = conn.cursor()

scan_id = 181
cur.execute(f"UPDATE scan SET status='login_required', scan_note='Google OAuth login needed - session expired' WHERE scan_id={scan_id}")
print(f"Updated scan {scan_id} to login_required")
conn.close()
