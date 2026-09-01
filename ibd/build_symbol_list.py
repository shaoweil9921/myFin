"""
Build ibd_symbol_list.csv from all processed IBD 50 CSVs.
Columns: symbol, company

Strategy:
- B1 (ranks 1-15): always trusted — LEFT-parsed, correct
- B3/B4 (ranks 16-50): only add if:
    a) symbol also appeared in B1 in ANY week (proven correct elsewhere), OR
    b) symbol appeared in multiple weeks with the SAME company name (consistent pair)
"""
import csv, os, re

BASE = r"C:\DolphinShare\IBD\2026\Processed"
OUT = r"C:\Users\shaowei_l\.openclaw\workspace\ibd\ibd_symbol_list.csv"

def clean_company(raw):
    # Strip trailing price+metric artifacts and unicode junk chars
    cleaned = re.sub(r'\d+\.\d+\s+\d+\s*$', '', raw).strip()
    # Remove private-use chars (e.g. \uf07d used as placeholder)
    cleaned = re.sub(r'[\uf07d\ufffd]', '', cleaned).strip()
    return cleaned

# Pass 1: collect all B1 symbols (verified correct pairs)
b1_symbols = set()  # symbols that appeared in B1
all_entries = []  # (fn, rank, sym, co)

for fn in sorted(os.listdir(BASE)):
    if not fn.endswith('.csv'):
        continue
    path = os.path.join(BASE, fn)
    with open(path, encoding='utf-8', errors='replace') as f:
        for r in csv.DictReader(f):
            rank = int(r['Rank'])
            sym = r['Symbol'].strip()
            co = clean_company(r['Company'].strip())
            all_entries.append((fn, rank, sym, co))
            if rank <= 15 and sym and '?' not in sym:
                b1_symbols.add(sym)

print(f"B1 symbols (verified): {len(b1_symbols)}")

# Pass 2: build symbol list
# Keep first-seen company for each symbol
seen = {}
# Track pairs for cross-week consistency check
pair_counts = {}  # (sym, co_lower) -> count

for fn, rank, sym, co in sorted(all_entries):
    if not sym or '?' in sym:
        continue
    key = (sym, co.lower())
    pair_counts[key] = pair_counts.get(key, 0) + 1

for fn, rank, sym, co in sorted(all_entries):
    if not sym or '?' in sym:
        continue
    if sym in seen:
        continue

    key = (sym, co.lower())
    weeks_with_pair = pair_counts[key]

    if rank <= 15:
        # Always trust B1
        seen[sym] = co
    elif sym in b1_symbols:
        # Symbol verified in B1 elsewhere — trust it
        seen[sym] = co
    elif weeks_with_pair >= 2:
        # Appeared in multiple weeks with same company — trust it
        seen[sym] = co

# Write output
fieldnames = ['symbol', 'company']
with open(OUT, 'w', encoding='utf-8', errors='replace', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for sym in sorted(seen):
        writer.writerow({'symbol': sym, 'company': seen[sym]})

print(f"Total unique symbols: {len(seen)}")
print(f"Saved -> {OUT}")
