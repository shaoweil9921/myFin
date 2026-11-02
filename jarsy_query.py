
from db_pw import get_db_pw as _db_pw
import psycopg2
conn = psycopg2.connect(host='127.0.0.1', dbname='fintech', user='postgres', password=_db_pw(), port=5432)
cur = conn.cursor()
cur.execute("SELECT holiday_name FROM market_holidays WHERE date = CURRENT_DATE;")
row = cur.fetchone()
print(row[0] if row else 'NO_HOLIDAY')
conn.close()