"""
Extract IBD Industry Group Rankings from eIBD PDF.

This script extracts the Industry Group Rankings table from IBD's Enhanced IBD PDF.
Each entry: rank, previous_group_rank, group_name, composite_rating, YTD%_change, 3Week%_change.

PDF: eIBD_080326.pdf (Aug 3, 2026 issue)
Page: B11 (page index 24)
Coverage: Ranks 1-142 (of 197 total groups)
  - 138 entries have full data
  - 4 entries missing rating (ranks 114, 116, 123, 124) — PDF rendering artifacts
  - Ranks 143-197 not present in this issue's PDF

Two-pass extraction:
  Pass 1: Block-regex on full page text (fast, captures ~95% of entries)
  Pass 2: Secondary regex for entries missing the rating field
"""
import fitz
import re
import csv
from pathlib import Path

PDF_PATH = r'C:\DolphinShare\IBD\2026\Raw\eIBD_080326.pdf'
OUTPUT_CSV = Path(__file__).parent / 'igr_aug03.csv'
PAGE_INDEX = 24  # 0-indexed


def extract_igr(pdf_path: str, page_index: int) -> list[tuple]:
    """Extract IGR entries from a single PDF page. Returns list of (rank, prev, group, rating, ytd, wk3)."""
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    text = page.get_text("text").replace('\xa0', ' ')
    doc.close()

    entries = {}

    # Pass 1: Primary pattern — full data (rank prev group rating ytd wk3)
    primary_pat = r'(\d{1,3})\s+(\d{1,3})\s+([A-Za-z&/\-.\s]{2,60}?)\s+(\d{1,3})\s+([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)'
    for m in re.finditer(primary_pat, text):
        rank = int(m.group(1))
        if 1 <= rank <= 197:
            entries[rank] = (
                rank,
                int(m.group(2)),
                m.group(3).strip(),
                int(m.group(4)),
                m.group(5),
                m.group(6)
            )

    # Pass 2: Secondary pattern — entries missing rating (rank prev group ytd wk3)
    # These appear when the rating digit is absorbed into the group name or missing
    secondary_pat = r'(\d{1,3})\s+(\d{1,3})\s+([A-Za-z&/\-.\s]{2,60}?)\s+([+-]\d+\.?\d*)\s+([+-]?\d+\.?\d*)'
    for m in re.finditer(secondary_pat, text):
        rank = int(m.group(1))
        if rank not in entries and 1 <= rank <= 197:
            group = m.group(3).strip()
            # Only accept valid group names (contain letters, length >= 3)
            if re.search(r'[A-Za-z]', group) and len(group) >= 3:
                entries[rank] = (rank, int(m.group(2)), group, None, m.group(4), m.group(5))

    return sorted(entries.values(), key=lambda x: x[0])


def main():
    results = extract_igr(PDF_PATH, PAGE_INDEX)

    with_rating = sum(1 for e in results if e[3] is not None)
    without_rating = [e[0] for e in results if e[3] is None]

    print(f"Extracted {len(results)} entries | {with_rating} with rating, {len(without_rating)} without: {without_rating}")

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Rank', 'PrevGroup', 'GroupName', 'Rating', 'YTD_pct', '3Wk_pct'])
        for r in results:
            writer.writerow(r)

    print(f"Saved: {OUTPUT_CSV}")
    return results


if __name__ == '__main__':
    main()
