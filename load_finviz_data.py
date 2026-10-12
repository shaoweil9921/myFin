import psycopg2
import json
import sys
import os
import winreg


def get_db_pw():
    """Read DB_PW from Windows registry (HKCU\Environment)."""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment")
        db_pw, _ = winreg.QueryValueEx(key, "DB_PW")
        winreg.CloseKey(key)
        return db_pw
    except Exception:
        return None


db_pw = get_db_pw()
if not db_pw:
    db_pw = os.environ.get('DB_PASSWORD', 'asdfghjk1234%')

print(f"DB_PW: {'from registry' if get_db_pw() else 'from env'}")

try:
    conn = psycopg2.connect(host='127.0.0.1', dbname='fintech', user='postgres', port=5432, password=db_pw)
    conn.autocommit = True
    cur = conn.cursor()

    # Check holiday
    cur.execute("SELECT holiday_name FROM market_holidays WHERE date = CURRENT_DATE")
    holiday = cur.fetchone()
    print("Holiday:", holiday)

    # Insert scan
    cur.execute("INSERT INTO scan (scan_name, scan_time, status, source) VALUES ('GapperMid', NOW(), 'started', 'finviz') RETURNING scan_id")
    scan_id = cur.fetchone()[0]
    print("Scan ID:", scan_id)

    # Check already extracted
    cur.execute("SELECT COUNT(*) FROM finviz_screener_scan_result r JOIN scan s ON r.scan_id = s.scan_id WHERE s.scan_name = 'GapperMid' AND DATE(s.scan_time) = CURRENT_DATE")
    cnt = cur.fetchone()[0]
    print("Already extracted count:", cnt)

    if cnt > 0:
        cur.execute("UPDATE scan SET status='skipped', scan_note='Already extracted' WHERE scan_id=%s", (scan_id,))
        print("SKIPPED - already extracted")
    else:
        # Load data
        with open(r'C:\Users\shaowei_l\.openclaw\workspace\finviz_extracted_data.json') as f:
            stocks = json.load(f)

        # Insert results (no screener_id lookup - table doesn't have that column)
        for s in stocks:
            # Strip commas from numeric strings that Finviz formats with commas (e.g., '47,955,104')
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

        # Complete
        cur.execute("UPDATE scan SET status='completed', scan_note='Completed' WHERE scan_id=%s", (scan_id,))
        print("COMPLETED")

    cur.close()
    conn.close()
except Exception as e:
    print("ERROR:", e)
    sys.exit(1)
