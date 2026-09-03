"""
Finviz GapperMid Extraction Script - v2
Full pipeline: holiday check -> insert scan -> extract -> load to DB -> notify
"""
import json
import time
import re
import psycopg2
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Config
TELEGRAM_CHAT_ID = "7923250382"
FINVIZ_URL = "https://finviz.com/screener.ashx?v=111&f=cap_midover,sh_curvol_o750,sh_price_o1,sh_relvol_o3&o=-change"
DB_PWD = "asdfghjk1234%"

def send_telegram(msg):
    try:
        import os
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if token:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
        else:
            print(f"TELEGRAM: {msg}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_db_conn():
    return psycopg2.connect(host='127.0.0.1', dbname='fintech', user='postgres', password=DB_PWD)

def update_scan_status(scan_id, status, note):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE scan SET status=%s, scan_note=%s WHERE scan_id=%s", (status, note, scan_id))
    conn.commit()
    conn.close()

def main():
    print(f"=== Finviz GapperMid Extraction {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    
    conn = get_db_conn()
    cur = conn.cursor()
    
    # Step 0: Check holiday
    cur.execute("SELECT holiday_name FROM market_holidays WHERE date = CURRENT_DATE")
    holiday_row = cur.fetchone()
    if holiday_row:
        holiday_name = holiday_row[0]
        cur.execute("SELECT scan_id FROM scan WHERE scan_name = 'GapperMid' AND DATE(scan_time) = CURRENT_DATE")
        existing = cur.fetchone()
        if existing:
            cur.execute("UPDATE scan SET scan_time = CURRENT_TIMESTAMP WHERE scan_name = 'GapperMid' AND DATE(scan_time) = CURRENT_DATE")
        else:
            cur.execute("INSERT INTO scan (scan_name, scan_time, status, source) VALUES ('GapperMid', CURRENT_TIMESTAMP, 'holiday', 'finviz')")
        conn.commit()
        conn.close()
        msg = f"Finviz: Market holiday - {holiday_name} - skipped"
        print(msg)
        send_telegram(msg)
        return
    
    # Step 1: Insert scan record
    cur.execute("""
        INSERT INTO scan (scan_name, scan_time, status, source)
        VALUES ('GapperMid', CURRENT_TIMESTAMP, 'started', 'finviz')
        RETURNING scan_id
    """)
    scan_id = cur.fetchone()[0]
    conn.commit()
    print(f"Scan ID: {scan_id}")
    
    # Step 2: Check already extracted
    cur.execute("""
        SELECT COUNT(*) FROM finviz_screener_scan_result r
        JOIN scan s ON r.scan_id = s.scan_id
        WHERE s.scan_name = 'GapperMid' AND DATE(s.scan_time) = CURRENT_DATE
    """)
    count = cur.fetchone()[0]
    print(f"Already extracted count: {count}")
    
    if count > 0:
        cur.execute("UPDATE scan SET status='skipped', scan_note='Already extracted' WHERE scan_id=%s", (scan_id,))
        conn.commit()
        conn.close()
        msg = "Finviz: Already extracted today"
        print(msg)
        send_telegram(msg)
        return
    
    # Step 3: Update to in_progress
    cur.execute("UPDATE scan SET status='in_progress', scan_note='Loading screener' WHERE scan_id=%s", (scan_id,))
    conn.commit()
    conn.close()
    
    # Step 4: Extract data
    update_scan_status(scan_id, 'in_progress', 'Extracting data')
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    session = requests.Session()
    resp = session.get(FINVIZ_URL, headers=headers, timeout=30)
    print(f"Finviz response: {resp.status_code}, length: {len(resp.text)}")
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # Find the screener table (has class 'screener_table')
    table = soup.find('table', {'class': 'screener_table'})
    if not table:
        for t in soup.find_all('table'):
            cls = t.get('class', [])
            if any('screener' in str(c).lower() for c in cls):
                table = t
                break
    
    results = []
    if table:
        rows = table.find_all('tr')
        print(f"Screener table rows: {len(rows)}")
        
        for row in rows:
            tds = row.find_all('td')
            if len(tds) < 11:
                continue
            
            # First TD is row number, skip it
            # TD indices: 0=#, 1=ticker, 2=company, 3=sector, 4=industry, 5=country, 6=market cap, 7=PE, 8=price, 9=change, 10=volume
            # Actually looking at the data: ['1', 'FLNC', 'Fluence Energy Inc', 'Utilities', 'Utilities - Renewabl', 'USA', '5.00B', '-']
            # That's 8 cols from row 1. Let me check what's in the full row.
            # Wait, row has 11 tds per inspect_table output: ['1', 'FLNC', 'Fluence Energy Inc', 'Utilities', 'Utilities - Renewabl', 'USA', '5.00B', '-']
            # So cols are: #, ticker, company, sector, industry, country, market_cap, PE, price, change, volume
            
            # Find ticker from link in second td
            ticker_td = tds[1] if len(tds) > 1 else None
            if not ticker_td:
                continue
            
            ticker_link = ticker_td.find('a')
            if not ticker_link:
                continue
            
            ticker = ticker_link.text.strip()
            if not ticker or len(ticker) > 5:
                continue
            
            company = tds[2].text.strip() if len(tds) > 2 else ''
            sector = tds[3].text.strip() if len(tds) > 3 else ''
            industry = tds[4].text.strip() if len(tds) > 4 else ''
            country = tds[5].text.strip() if len(tds) > 5 else ''
            market_cap = tds[6].text.strip() if len(tds) > 6 else ''
            pe = tds[7].text.strip() if len(tds) > 7 else ''
            price = tds[8].text.strip() if len(tds) > 8 else ''
            change = tds[9].text.strip() if len(tds) > 9 else ''
            volume = tds[10].text.strip() if len(tds) > 10 else ''
            
            results.append({
                'ticker': ticker,
                'company': company,
                'sector': sector,
                'industry': industry,
                'country': country,
                'market_cap': market_cap,
                'pe': pe,
                'price': price,
                'change_pct': change,
                'volume': volume
            })
    
    print(f"Extracted {len(results)} rows")
    
    # Save to JSON
    with open('finviz_extracted_data.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    if not results:
        update_scan_status(scan_id, 'failed', 'No data extracted from Finviz')
        send_telegram(f"Finviz GapperMid: Extraction failed - no data found")
        return
    
    # Step 5: Load to DB
    update_scan_status(scan_id, 'in_progress', 'Loading to DB')
    
    conn = get_db_conn()
    cur = conn.cursor()
    
    loaded = 0
    for row in results:
        pe_val = None
        if row['pe'] and row['pe'] not in ['-', '', 'N/A']:
            try:
                pe_val = float(row['pe'])
            except:
                pe_val = None
        
        change_raw = row['change_pct'].replace('%', '').replace('+', '')
        volume_raw = row['volume'].replace(',', '')
        
        try:
            cur.execute("""
                INSERT INTO finviz_screener_scan_result 
                (screener_name, ticker, company, sector, industry, country, market_cap, pe_ratio, price, change_pct, volume, screener_id, scan_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (scan_id, ticker) DO NOTHING
            """, (
                'GapperMid',
                row['ticker'],
                row['company'],
                row['sector'],
                row['industry'],
                row['country'],
                row['market_cap'],
                pe_val,
                row['price'],
                change_raw,
                volume_raw,
                1,
                scan_id
            ))
            loaded += 1
        except Exception as e:
            print(f"Error inserting {row['ticker']}: {e}")
    
    conn.commit()
    conn.close()
    print(f"Loaded {loaded} rows to DB")
    
    # Step 6: Mark complete
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE scan SET status='completed', scan_note='Completed' WHERE scan_id=%s", (scan_id,))
    conn.commit()
    conn.close()
    
    # Step 7: Send Telegram
    change_top = results[0]['change_pct'] if results else 'N/A'
    top_ticker = results[0]['ticker'] if results else 'N/A'
    msg = f"Finviz GapperMid: {len(results)} stocks extracted, scan_id={scan_id}, top={top_ticker} ({change_top})"
    print(msg)
    send_telegram(msg)

if __name__ == '__main__':
    main()