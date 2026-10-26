"""Scrape Finviz GapperMid screener - parse embedded JSON data.
Finviz now embeds screener data as JSON inside a <script> tag, not in HTML tables.
"""
import requests
import re
import json

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'identity',
}

BASE_URL = 'https://finviz.com/screener.ashx?v=111&f=cap_midover,sh_curvol_o750,sh_price_o1,sh_relvol_o3&o=-change'


def extract_screener_json(html):
    """Extract screener data from embedded JSON <script> tag."""
    # Finviz embeds the full screener state as JSON in a large <script> tag
    # The JSON contains 'screenerType" : "stocks"' and a 'data' key with rows
    # Match the opening brace of the JSON object - it's the only large JSON object with screenerType
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for s in scripts:
        if 'screenerType' in s and '"data"' in s:
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
    return None


def parse_stocks(data):
    """Parse stock rows from the embedded JSON data structure."""
    if not data or 'data' not in data:
        return []

    rows = []
    screener_rows = data['data'].get('rows', [])
    
    for r in screener_rows:
        text = r.get('text', {})
        numbers = r.get('numbers', {})
        
        # Finviz 'change' is ALREADY a percentage (e.g. prevClose 15.75 -> price 23.20 => change 47.33)
        # Prefer prevClose/price derivation; fall back to the raw 'change' percentage.
        price = numbers.get('price')
        change = numbers.get('change')
        prev_close = numbers.get('prevClose')
        change_pct = None
        if prev_close and price:
            change_pct = round((price - prev_close) / prev_close * 100, 2)
        elif change is not None:
            change_pct = round(change, 2)

        # PE ratio from the embedded JSON (previously always dropped as empty)
        pe_val = numbers.get('PE')
        pe = str(round(pe_val, 2)) if pe_val else ''
        
        # Format market cap
        mktcap = numbers.get('marketCap')
        if mktcap:
            if mktcap >= 1e12:
                mktcap_fmt = f"{mktcap/1e12:.2f}T"
            elif mktcap >= 1e9:
                mktcap_fmt = f"{mktcap/1e9:.2f}B"
            elif mktcap >= 1e6:
                mktcap_fmt = f"{mktcap/1e6:.2f}M"
            else:
                mktcap_fmt = str(mktcap)
        else:
            mktcap_fmt = ''
        
        rows.append({
            'ticker': text.get('ticker', ''),
            'company': text.get('company', ''),
            'sector': text.get('sector', ''),
            'industry': text.get('industry', ''),
            'country': text.get('country', ''),
            'market_cap': mktcap_fmt,
            'pe': pe,
            'price': str(round(price, 2)) if price else '',
            'change_pct': str(change_pct) if change_pct is not None else '',
            'volume': str(numbers.get('volume', '')),
        })
    
    return rows


def main():
    print(f"Fetching Finviz GapperMid screener...")
    resp = requests.get(BASE_URL, headers=HEADERS, timeout=30)
    print(f"  Status: {resp.status_code}, Length: {len(resp.text)}")

    data = extract_screener_json(resp.text)
    if not data:
        print("WARNING: Could not find screener JSON in page!")
        return False

    total = data.get('data', {}).get('totalCount', 0)
    print(f"  Total results: {total}")

    rows = parse_stocks(data)
    print(f"  Extracted: {len(rows)} rows")

    for r in rows[:3]:
        print(f"  {r['ticker']}: ${r['price']}, vol={r['volume']}, chg={r['change_pct']}%")

    out_path = r'C:\Users\shaowei_l\.openclaw\workspace\finviz_extracted_data.json'
    with open(out_path, 'w') as f:
        json.dump(rows, f, indent=2)
    print(f"Saved {len(rows)} rows to {out_path}")

    return len(rows) > 0


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
