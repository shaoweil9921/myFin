import psycopg2
import csv

conn = psycopg2.connect(host='127.0.0.1', port=5432, dbname='fintech', user='postgres', password='***')
cur = conn.cursor()

files = [
    (r'C:\Users\shaowei_l\Downloads\IBD50_081026_v9.csv', '2026-08-10'),
    (r'C:\Users\shaowei_l\Downloads\IBD50_081726_v9.csv', '2026-08-17'),
]

for filepath, issue_date in files:
    cur.execute("DELETE FROM ibd_50_new WHERE issue_date = %s", (issue_date,))
    deleted = cur.rowcount

    rows_loaded = 0
    skipped = []
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rank = int(row['Rank'])
            symbol = row['Symbol'].strip()
            price = float(row['Price']) if row.get('Price') and row['Price'].strip() else None
            company = row.get('Company', '').strip() or None
            group = row.get('Group', '').strip() or None
            short_note = row.get('Short Note', '').strip() or None

            if not symbol:
                skipped.append(f"R{rank}({company})")
                continue

            cur.execute("""
                INSERT INTO ibd_50_new (issue_date, rank, symbol, company, price, industry, short_note)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (issue_date, rank, symbol, company, price, group, short_note))
            rows_loaded += 1

    conn.commit()
    print(f"[{issue_date}] Deleted {deleted} old rows, loaded {rows_loaded} rows, skipped {len(skipped)}: {skipped}")

cur.close()
conn.close()
print("Done.")
