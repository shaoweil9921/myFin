"""Force-load Finviz GapperMid snapshot bypassing the same-day dedup guard.
Used when an earlier same-day scan landed only a partial row set.
"""
import psycopg2
import json
import os
import winreg

def get_db_pw():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        db_pw, _ = winreg.QueryValueEx(key, "DB_PW")
        winreg.CloseKey(key)
        return db_pw
    except Exception:
        return None

db_pw = get_db_pw() or os.environ.get('DB_PASSWORD', '')
print("DB_PW:", 'from registry' if get_db_pw() else 'from env')

conn = psycopg2.connect(host='127.0.0.1', dbname='fintech', user='postgres', port=5432, password=db_pw)
conn.autocommit = True
cur = conn.cursor()

cur.execute("INSERT INTO scan (scan_name, scan_time, status, source) VALUES ('GapperMid', NOW(), 'started', 'finviz') RETURNING scan_id")
scan_id = cur.fetchone()[0]
print("Scan ID:", scan_id)

with open(r'C:\Users\shaowei_l\.openclaw\workspace\finviz_extracted_data.json') as f:
    stocks = json.load(f)

for s in stocks:
    vol = s['volume'].replace(',', '')
    pe_raw = s['pe']
    pe = pe_raw.replace(',', '').replace('-', '') if pe_raw and pe_raw != '-' else None
    change = s['change_pct'].replace('%', '').replace(',', '') if s['change_pct'] else None
    cur.execute("""INSERT INTO finviz_screener_scan_result
        (scan_id, screener_name, ticker, company, sector, industry, country, market_cap, pe_ratio, price, change_pct, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (scan_id, 'GapperMid', s['ticker'], s['company'], s['sector'], s['industry'],
         s['country'], s['market_cap'], pe, float(s['price']), change, int(vol)))

print("Inserted", len(stocks), "rows")
cur.execute("UPDATE scan SET status='completed', scan_note='Completed (forced full load)' WHERE scan_id=%s", (scan_id,))
print("COMPLETED")
cur.close()
conn.close()
