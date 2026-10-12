"""Scrape Finviz GapperMid screener - page 1 only (short-term fix).
No session cookies - Finviz paginated pages return empty data rows.
"""
import requests
from bs4 import BeautifulSoup
import json
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'identity',
}

BASE_URL = 'https://finviz.com/screener.ashx?v=111&f=cap_midover,sh_curvol_o750,sh_price_o1,sh_relvol_o3&o=-change'


def parse_page(html):
    """Extract stock rows from Finviz screener HTML page 1."""
    soup = BeautifulSoup(html, 'html.parser')

    # Find the screener table - it's a table with class 'screener_table'
    tables = soup.find_all('table')
    screener_table = None
    for t in tables:
        if 'screener_table' in t.get('class', []):
            screener_table = t
            break

    if not screener_table:
        # Try fv-container as fallback
        fv = soup.find('div', class_='fv-container')
        if fv:
            tables_in_fv = fv.find_all('table')
            for t in tables_in_fv:
                if t.find_all('tr') and len(t.find_all('tr')) > 5:
                    screener_table = t
                    break

    if not screener_table:
        print("WARNING: screener_table not found!")
        return []

    rows = []
    trs = screener_table.find_all('tr')
    for tr in trs:
        cells = tr.find_all('td')
        if not cells:
            continue
        # First cell should be row number
        first = cells[0].get_text(strip=True)
        if not first.isdigit():
            continue
        row_num = int(first)
        if row_num < 1:
            continue
        if len(cells) < 10:
            continue
        # Cells: No, Ticker, Company, Sector, Industry, Country, Market Cap, P/E, Price, Change%, Volume
        ticker = cells[1].get_text(strip=True)
        company = cells[2].get_text(strip=True)
        sector = cells[3].get_text(strip=True)
        industry = cells[4].get_text(strip=True)
        country = cells[5].get_text(strip=True)
        market_cap = cells[6].get_text(strip=True)
        pe = cells[7].get_text(strip=True)
        price = cells[8].get_text(strip=True)
        change_pct = cells[9].get_text(strip=True)
        volume = cells[10].get_text(strip=True) if len(cells) > 10 else ''

        rows.append({
            'ticker': ticker,
            'company': company,
            'sector': sector,
            'industry': industry,
            'country': country,
            'market_cap': market_cap,
            'pe': pe,
            'price': price,
            'change_pct': change_pct,
            'volume': volume,
        })

    return rows


def main():
    print(f"Fetching Finviz GapperMid screener (page 1 only)...")
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    print(f"  Status: {resp.status_code}, Length: {len(resp.text)}")

    rows = parse_page(resp.text)
    print(f"  Extracted: {len(rows)} rows")

    for r in rows[:3]:
        print(f"  {r['ticker']}: ${r['price']}, vol={r['volume']}, chg={r['change_pct']}")

    out_path = r'C:\Users\shaowei_l\.openclaw\workspace\finviz_extracted_data.json'
    with open(out_path, 'w') as f:
        json.dump(rows, f, indent=2)
    print(f"Saved {len(rows)} rows to {out_path}")

    return len(rows) > 0


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
