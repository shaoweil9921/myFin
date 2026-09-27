"""Build final IGR CSV — all available data."""
import fitz, re, csv

doc = fitz.open(r'C:\DolphinShare\IBD\2026\Raw\eIBD_080326.pdf')
page = doc[24]
text = page.get_text('text').replace('\xa0', ' ')

# Primary pattern (full data: rank prev group rating ytd wk3)
pattern = r'(\d{1,3})\s+(\d{1,3})\s+([A-Za-z&/\-.\s]{2,60}?)\s+(\d{1,3})\s+([+-]?\d+\.?\d*)\s+([+-]?\d+\.?\d*)'
matches = list(re.finditer(pattern, text))

entries = {}
for m in matches:
    rank = int(m.group(1))
    if 1 <= rank <= 197:
        entries[rank] = (rank, int(m.group(2)), m.group(3).strip(), int(m.group(4)), m.group(5), m.group(6))

# Secondary pattern: entries with MISSING rating (captured as ytd, wk3 from next tokens)
# These ranks appear in text as: rank\nprev\ngroup\nytd_pct\nwk3_pct
pattern2 = r'(\d{1,3})\s+(\d{1,3})\s+([A-Za-z&/\-.\s]{2,60}?)\s+([+-]\d+\.?\d*)\s+([+-]?\d+\.?\d*)'
for m in re.finditer(pattern2, text):
    rank = int(m.group(1))
    if rank not in entries and 1 <= rank <= 197:
        group = m.group(3).strip()
        # Only accept if group looks like an industry name (has letters)
        if re.search(r'[A-Za-z]', group) and len(group) >= 3:
            entries[rank] = (rank, int(m.group(2)), group, None, m.group(4), m.group(5))

results = sorted(entries.values(), key=lambda x: x[0])

with_rating = sum(1 for e in results if e[3] is not None)
without_rating = [e[0] for e in results if e[3] is None]
print(f"Total: {len(results)} | With rating: {with_rating} | Without rating: {without_rating}")

with open(r'C:\Users\shaowei_l\.openclaw\workspace\ibd\igr_aug03.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Rank', 'PrevGroup', 'GroupName', 'Rating', 'YTD_pct', '3Wk_pct'])
    for r in results:
        writer.writerow(r)

print(f"Saved: igr_aug03.csv")
doc.close()
