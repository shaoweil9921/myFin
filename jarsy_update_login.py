import psycopg2
conn = psycopg2.connect(host='127.0.0.1', dbname='fintech', user='postgres', password='asdfghjk1234%')
conn.autocommit = True
cur = conn.cursor()
cur.execute("UPDATE scan SET status='login_required', scan_note='Google OAuth session expired - manual login needed' WHERE scan_id=235")
print('Updated scan 235 to login_required')
conn.close()
