"""
Build ibd_symbol_list.csv — ALL symbols from IBD 50 PDFs.
Columns: symbol, company, reliable
  - reliable=1: high confidence (B1 or cross-week consistent pair)
  - reliable=0: lower confidence (B3/B4 single-week entries)

Adds symbol if not already in list. Keeps first-seen company name.
"""
import csv, os, re

BASE = r"C:\DolphinShare\IBD\2026\Processed"
OUT = r"C:\Users\shaowei_l\.openclaw\workspace\ibd\ibd_symbol_list.csv"

def clean_company(raw):
    cleaned = re.sub(r'\d+\.\d+\s+\d+\s*$', '', raw).strip()
    cleaned = re.sub(r'[\uf07d\ufffd]', '', cleaned).strip()
    return cleaned

# Pass 1: collect all entries
all_entries = []  # (fn, rank, sym, co)
b1_symbols = set()

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

print(f"B1 verified symbols: {len(b1_symbols)}")

# Pass 2: count (symbol, company_lower) pairs across weeks
pair_counts = {}
for fn, rank, sym, co in all_entries:
    if not sym or '?' in sym:
        continue
    key = (sym, co.lower())
    pair_counts[key] = pair_counts.get(key, 0) + 1

# Pass 3: build symbol list
seen = {}  # sym -> (co, reliable)
for fn, rank, sym, co in sorted(all_entries):
    if not sym or '?' in sym or sym in seen:
        continue

    key = (sym, co.lower())
    weeks_with_pair = pair_counts[key]

    if rank <= 15:
        reliable = 1
    elif sym in b1_symbols:
        reliable = 1
    elif weeks_with_pair >= 2:
        reliable = 1
    else:
        reliable = 0

    seen[sym] = (co, reliable)

# Write output
fieldnames = ['symbol', 'company', 'reliable']
with open(OUT, 'w', encoding='utf-8', errors='replace', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for sym in sorted(seen):
        co, reliable = seen[sym]
        writer.writerow({'symbol': sym, 'company': co, 'reliable': reliable})

reliable_count = sum(1 for _, (_, r) in seen.items() if r == 1)
print(f"\nTotal unique symbols: {len(seen)}")
print(f"  Reliable (reliable=1): {reliable_count}")
print(f"  Unverified (reliable=0): {len(seen) - reliable_count}")
print(f"Saved -> {OUT}")

# Show unreliable entries
print("\nUnverified entries (may need manual review):")
for sym in sorted(seen):
    co, reliable = seen[sym]
    if not reliable:
        print(f"  {sym}: {co}")
