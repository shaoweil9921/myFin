import fitz
import re
import psycopg2
import sys
import os

industry_map = {
    'NVDA': 'Semiconductors', 'ADMA': 'Biotech', 'OSCR': 'Health Insurance',
    'GRBK': 'Real Estate', 'HROW': 'Biotech', 'TGTX': 'Biotech',
    'BWIN': 'Insurance', 'ARM': 'Semiconductors', 'PLTR': 'Software',
    'IOT': 'Software', 'MMYT': 'Online Travel', 'ASPN': 'Materials',
    'WING': 'Restaurant', 'NTRA': 'Biotech', 'ALNY': 'Biotech',
    'EME': 'Construction', 'MIRM': 'Biotech', 'DOCS': 'Healthcare IT',
    'FIX': 'Construction', 'VRT': 'Technology', 'MELI': 'E-commerce',
    'YOU': 'Software', 'ANET': 'Networking', 'STRL': 'Construction',
    'AXON': 'Aerospace/Defense', 'RYTM': 'Biotech', 'POWL': 'Industrials',
    'FTAI': 'Aerospace', 'ZETA': 'Software', 'LNTH': 'Diagnostics',
    'ONON': 'Consumer', 'HWM': 'Aerospace', 'PACS': 'Healthcare',
    'RCL': 'Travel', 'AFRM': 'Fintech', 'NOW': 'Software',
    'CWAN': 'Software', 'ARGX': 'Biotech', 'TT': 'Industrials',
    'NFLX': 'Streaming', 'NMIH': 'Fintech', 'MNDY': 'Software',
    'RYAN': 'Insurance', 'RXST': 'Medical Devices', 'AGI': 'Gold Mining',
    'HEI': 'Aerospace', 'IBKR': 'Finance', 'META': 'Social Media',
    'FRPT': 'Consumer', 'DY': 'Telecom', 'TMDX': 'Medical Devices',
    'CRUS': 'Semiconductors', 'LRN': 'Education', 'PHM': 'Real Estate',
    'ACGL': 'Insurance', 'FTNT': 'Cybersecurity', 'VIST': 'Energy',
    'EXR': 'Real Estate', 'PSN': 'Aerospace', 'AJG': 'Insurance',
    'LLY': 'Pharma', 'UTHR': 'Pharma', 'TTD': 'Software', 'EVH': 'Healthcare',
    'BGNE': 'Biotech', 'LBTYA': 'Telecom', 'REYN': 'Consumer',
    'CMPR': 'Technology', 'GDDY': 'Software', 'NEM': 'Gold Mining',
    'EGO': 'Gold Mining', 'THC': 'Healthcare', 'NU': 'Fintech',
    'HG': 'Insurance', 'REVG': 'Industrials', 'ISRG': 'Medical Devices',
    'KKR': 'Finance', 'ENVA': 'Fintech', 'BRO': 'Insurance',
    'VERX': 'Software', 'FOUR': 'Fintech', 'IESC': 'Industrials',
    'ACIW': 'Software', 'AGYS': 'Software', 'KTOS': 'Aerospace/Defense',
    'PPC': 'Consumer',
}

# File to date mapping
file_dates_2024 = {
    'eIBD_090224-1.pdf': '2024-09-02', 'eIBD_090924.pdf': '2024-09-09',
    'eIBD_091624.pdf': '2024-09-16', 'eIBD_092324.pdf': '2024-09-23',
    'eIBD_093024.pdf': '2024-09-30', 'eIBD_100424-B.pdf': '2024-10-07',
    'eIBD_101414.pdf': '2024-10-14', 'eIBD_102124_v2.pdf': '2024-10-21',
    'eIBD_102824.pdf': '2024-10-28', 'eIBD_110424.pdf': '2024-11-04',
    'eIBD_111124-1.pdf': '2024-11-11', 'eIBD_111824.pdf': '2024-11-18',
    'eIBD_112524.pdf': '2024-11-25', 'eIBD_120224.pdf': '2024-12-02',
    'eIBD_120924.pdf': '2024-12-09', 'eIBD_121624.pdf': '2024-12-16',
    'eIBD_122324.pdf': '2024-12-23', 'eIBD_123024.pdf': '2024-12-30',
}

def get_date_from_filename(filename, folder_year):
    # Try to extract date from filename pattern eIBD_MMDDYY
    import re
    match = re.search(r'eIBD_(\d{1,2})(\d{2})(\d{2})', filename)
    if match:
        month, day, year = match.groups()
        full_year = '20' + year if int(year) > 50 else '202' + year
        return f'{full_year}-{int(month):02d}-{int(day):02d}'
    return None

def process_folder(folder_path):
    files = sorted([f for f in os.listdir(folder_path) if f.endswith('.pdf')])
    
    conn = psycopg2.connect(host="127.0.0.1", database="fintech", user="postgres", password="asdfghjk1234%")
    cur = conn.cursor()
    
    # Determine year from folder path
    folder_year = '2024'
    if '2025' in folder_path:
        folder_year = '2025'
    
    for filename in files:
        filepath = os.path.join(folder_path, filename)
        
        # Try to get date from filename
        issue_date = get_date_from_filename(filename, folder_year)
        
        # Fallback to file_dates_2024 if available
        if not issue_date:
            issue_date = file_dates_2024.get(filename)
        
        if not issue_date:
            print(f'Skipping: {filename} - no date')
            continue
        
        print(f'Processing: {filename} ({issue_date})')
        
        try:
            doc = fitz.open(filepath)
            companies = []
            summary = ''
            
            for page_idx in range(15, 30):
                try:
                    page = doc[page_idx]
                    text = page.get_text()
                    
                    if text.count('Grp') < 5:
                        continue
                    
                    lines = text.split('\n')
                    
                    for i, line in enumerate(lines):
                        line_stripped = line.strip()
                        if not line_stripped or len(line_stripped) < 5:
                            continue
                        
                        if any(w in line_stripped.upper() for w in ['COMPANY', 'SMARTSELECT', 'REL', 'RATING', 'GR ', 'PRICE', 'SHARE', 'EPS', 'VOL']):
                            continue
                        
                        match1 = re.match(r'^(.+?)\s{2,}([A-Z]{2,5})\s*$', line_stripped)
                        if not match1:
                            match1 = re.match(r'^(.+?)\s+([A-Z]{2,5})\s*$', line_stripped)
                        if not match1:
                            match1 = re.match(r'^(.+?)\s+([A-Z]{2,5})\s+Grp', line_stripped)
                        
                        if match1:
                            company = match1.group(1).strip()[:50]
                            ticker = match1.group(2)
                            
                            if len(company) < 2 or company[0].isdigit():
                                continue
                            if ticker in ['GR', 'COMP', 'GROUP', 'ETF', 'LLC', 'INC', 'LTD', 'THE', 'AND', 'FOR', 'NEW', 'ALL']:
                                continue
                            
                            price = None
                            for j in range(i+1, min(i+4, len(lines))):
                                next_line = lines[j].strip()
                                price_match = re.search(r'^\$([\d,]+\.?\d*)', next_line)
                                if price_match:
                                    try:
                                        price = float(price_match.group(1).replace(',', ''))
                                        break
                                    except:
                                        pass
                                price_match = re.search(r'Grp\s*\d+\s+\$([\d,]+\.?\d*)', next_line)
                                if price_match:
                                    try:
                                        price = float(price_match.group(1).replace(',', ''))
                                        break
                                    except:
                                        pass
                            
                            if price and 5 <= price <= 5000:
                                companies.append({'company': company, 'ticker': ticker, 'price': price})
                except:
                    pass
            
            # Extract summary
            for page_idx in range(15, 25):
                try:
                    page = doc[page_idx]
                    text = page.get_text()
                    if 'INSIDE THE 50' in text.upper():
                        idx = text.upper().find('INSIDE THE 50')
                        if idx >= 0:
                            summary_text = text[idx:idx+1500]
                            lines = summary_text.split('\n')
                            summary_lines = []
                            for line in lines[1:]:
                                line = line.strip()
                                if line and len(line) > 20:
                                    summary_lines.append(line[:200])
                                if len(summary_lines) >= 3:
                                    break
                            summary = ' '.join(summary_lines[:3])
                            break
                except:
                    pass
            
            # Dedupe
            seen = {}
            unique = []
            for c in companies:
                if c['ticker'] not in seen:
                    seen[c['ticker']] = c
                    unique.append(c)
            
            unique = unique[:50]
            
            print(f'  Companies: {len(unique)}, Summary: {"Yes" if summary else "No"}')
            
            cur.execute("DELETE FROM ibd_50 WHERE issue_date = %s", (issue_date,))
            
            for rank, c in enumerate(unique, 1):
                industry = industry_map.get(c['ticker'], 'Unknown')
                cur.execute("""
                    INSERT INTO ibd_50 (issue_date, rank, company, symbol, price, industry)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (issue_date, rank, c['company'], c['ticker'], c['price'], industry))
            
            if summary:
                cur.execute("""
                    INSERT INTO ibd_50_summary (issue_date, summary_text)
                    VALUES (%s, %s)
                    ON CONFLICT (issue_date) DO UPDATE SET summary_text = EXCLUDED.summary_text
                """, (issue_date, summary[:500]))
            
            conn.commit()
            doc.close()
            
        except Exception as e:
            print(f'  Error: {e}')
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    folder = sys.argv[1] if len(sys.argv) > 1 else r'D:\Magzines\IBD\2024'
    print(f'Processing folder: {folder}')
    process_folder(folder)
    print('Done!')
