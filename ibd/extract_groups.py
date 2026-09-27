"""
IBD Industry Group Rankings (IGR) Extractor
==========================================
Extracts Industry Group Rankings from Enhanced IBD (eIBD) PDF magazines.

PDF:       eIBD_YYYYMMDD.pdf in C:\DolphinShare\IBD\YYYY\Raw\
Page:      B11 (page index 24, 0-indexed)
Coverage:  Ranks 1-142 (of 197 total groups) per issue
            - 138 entries with full data (rating + ytd + wk3)
            - 4 entries missing rating (PDF artifacts: ranks 114, 116, 123, 124)
            - Ranks 143-197 not present in this issue's PDF

Two-pass extraction:
  Pass 1: Block-regex on full page text (~138 entries, fast)
  Pass 2: Secondary regex for entries missing the rating field (~4 entries)

Output: CSV + optional DB insert

Usage:
  python extract_groups.py [pdf_path] [output_csv]
  Defaults: pdf_path = C:\\DolphinShare\\IBD\\2026\\Raw\\eIBD_080326.pdf
            output_csv = ./igr_aug03.csv

DB Load:
  python -c "
    import psycopg2, csv
    conn = psycopg2.connect(host='127.0.0.1', port=5432, dbname='fintech', user='postgres', password='...')
    cur = conn.cursor()
    with open('igr_aug03.csv') as f:
        for row in csv.DictReader(f):
            cur.execute('''
                INSERT INTO ibd_industry_group_rankings (issue_date, rank, prev_group_rank, group_name, composite_rating, ytd_pct, wk3_pct)
                VALUES (%(issue_date)s, %(rank)s, %(prev_group_rank)s, %(group_name)s,
                        %(composite_rating)s, %(ytd_pct)s, %(wk3_pct)s)
                ON CONFLICT (issue_date, rank) DO UPDATE SET
                    prev_group_rank = EXCLUDED.prev_group_rank,
                    group_name = EXCLUDED.group_name,
                    composite_rating = EXCLUDED.composite_rating,
                    ytd_pct = EXCLUDED.ytd_pct,
                    wk3_pct = EXCLUDED.wk3_pct
            ''', {
                'issue_date': '2026-08-03',
                'rank': int(row['Rank']),
                'prev_group_rank': int(row['PrevGroup']),
                'group_name': row['GroupName'],
                'composite_rating': int(row['Rating']) if row['Rating'] else None,
                'ytd_pct': row['YTD_pct'],
                'wk3_pct': row['3Wk_pct']
            })
    conn.commit()
    cur.close(); conn.close()
  "
"""
import fitz
import re
import csv
import sys
from pathlib import Path

PAGE_INDEX = 24  # B11 = page index 24 (0-indexed)


def extract_igr(pdf_path: str, page_index: int = PAGE_INDEX) -> list[dict]:
    """
    Extract IGR entries from a single PDF page.
    Returns list of dicts with keys: rank, prev, group, rating, ytd, wk3
    """
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    text = page.get_text("text").replace('\xa0', ' ')
    doc.close()

    entries = {}

    # Pass 1: Primary pattern — full data
    # Format: rank prev group_name rating ytd% wk3%
    # Example: "1 7 Oil&gas-refin/mktg 86 +76.0 0.0"
    primary_pat = r'(\d{1,3})\s+(\d{1,3})\s+([A-Za-z&/\-.\s]{2,60}?)\s+(\d{1,3})\s+([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)'
    for m in re.finditer(primary_pat, text):
        rank = int(m.group(1))
        if 1 <= rank <= 197:
            entries[rank] = {
                'rank': rank,
                'prev': int(m.group(2)),
                'group': m.group(3).strip(),
                'rating': int(m.group(4)),
                'ytd': m.group(5),
                'wk3': m.group(6)
            }

    # Pass 2: Secondary pattern — entries missing rating
    # Format: rank prev group_name ytd% wk3%
    # These ranks have no rating in the PDF (114, 116, 123, 124 in Aug 3 issue)
    secondary_pat = r'(\d{1,3})\s+(\d{1,3})\s+([A-Za-z&/\-.\s]{2,60}?)\s+([+-]\d+\.?\d*)\s+([+-]?\d+\.?\d*)'
    for m in re.finditer(secondary_pat, text):
        rank = int(m.group(1))
        if rank not in entries and 1 <= rank <= 197:
            group = m.group(3).strip()
            # Validate: must contain letters and be a reasonable length
            if re.search(r'[A-Za-z]', group) and 3 <= len(group) <= 60:
                entries[rank] = {
                    'rank': rank,
                    'prev': int(m.group(2)),
                    'group': group,
                    'rating': None,
                    'ytd': m.group(4),
                    'wk3': m.group(5)
                }

    return sorted(entries.values(), key=lambda x: x['rank'])


def save_csv(results: list[dict], output_path: str):
    """Save extraction results to CSV."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Rank', 'PrevGroup', 'GroupName', 'Rating', 'YTD_pct', '3Wk_pct'])
        for r in results:
            writer.writerow([r['rank'], r['prev'], r['group'],
                           r['rating'] if r['rating'] is not None else '',
                           r['ytd'], r['wk3']])
    print(f"CSV saved: {output_path}")


def main():
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else r'C:\DolphinShare\IBD\2026\Raw\eIBD_080326.pdf'
    output_csv = sys.argv[2] if len(sys.argv) > 2 else r'C:\Users\shaowei_l\.openclaw\workspace\ibd\igr_aug03.csv'

    print(f"Extracting IGR from: {pdf_path}")
    results = extract_igr(pdf_path)

    with_rating = sum(1 for e in results if e['rating'] is not None)
    without_rating = [e['rank'] for e in results if e['rating'] is None]

    print(f"Total: {len(results)} | {with_rating} with rating | {len(without_rating)} without: {without_rating}")
    save_csv(results, output_csv)

    return results


if __name__ == '__main__':
    main()
