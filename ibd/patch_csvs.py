"""Patch missing group numbers in the CSV files based on PDF extraction."""
import csv

# Aug 10 patches (from PDF search)
aug10_patches = {
    22: ('SKWD', 'Grp60'),
    25: ('ADPT', 'Grp76'),
    38: ('PAY',  'Grp68'),
    45: ('S',    'Grp3'),
}

# Aug 17 patches (from PDF search)
aug17_patches = {
    28: ('ADPT', 'Grp82'),
    36: ('SKWD', 'Grp64'),
    49: ('TSM',  'Grp42'),
    50: ('INSW', 'Grp9'),
}

for fname, patches in [
    (r'C:\Users\shaowei_l\Downloads\IBD50_081026_v9.csv', aug10_patches),
    (r'C:\Users\shaowei_l\Downloads\IBD50_081726_v9.csv', aug17_patches),
]:
    with open(fname, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = [lines[0]]

    for line in lines[1:]:
        if not line.strip():
            continue
        row = list(csv.reader([line]))[0]
        if len(row) < 7:
            new_lines.append(line)
            continue
        try:
            rank = int(row[0])
        except:
            new_lines.append(line)
            continue
        if rank in patches:
            sym, grp = patches[rank]
            row[1] = sym
            row[4] = grp
            print(f"Patched {fname[-20:]}: R{rank} {sym} -> group={grp}")
        new_lines.append(','.join(row))

    with open(fname, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

print("Done.")
