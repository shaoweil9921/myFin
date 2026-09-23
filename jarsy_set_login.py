import psycopg2

conn = psycopg2.connect(user='postgres', host='127.0.0.1', database='fintech', password='asdfghjk1234%')
cur = conn.cursor()

# Mark scan as login_required
cur.execute("UPDATE scan SET status='login_required', scan_note='Google OAuth login needed - session expired' WHERE scan_id=102")
conn.commit()
print("Updated scan 102 to login_required")
conn.close()