import psycopg2
conn = psycopg2.connect(user='postgres', host='127.0.0.1', database='fintech', password='asdfghjk1234%')
conn.autocommit = True
cur = conn.cursor()
cur.execute("UPDATE scan SET status='login_required', scan_note='Google OAuth login needed - session expired' WHERE scan_id=187")
print("Updated scan 187 to login_required")
conn.close()
