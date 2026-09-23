import psycopg2
conn = psycopg2.connect(host='127.0.0.1', database='fintech', user='postgres', password='asdfghjk1234%', port=5432)
cur = conn.cursor()
cur.execute("SELECT holiday_name FROM market_holidays WHERE date = CURRENT_DATE;")
row = cur.fetchone()
if row:
    print(f"HOLIDAY: {row[0]}")
else:
    print("NO_HOLIDAY")
conn.close()
