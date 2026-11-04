import os, re, sys
roots = [r'C:\Users\shaowei_l\.openclaw\workspace']
pat = re.compile(r'\.us\b|stooq|US__|US\b.*quote')
hits = []
for root in roots:
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ('.git','node_modules','.venv','venv','__pycache__','.openclaw')]
        for f in fn:
            if not f.endswith(('.py','.js','.mjs','.cjs','.ps1','.md','.txt','.json','.yaml','.yml')):
                continue
            p = os.path.join(dp, f)
            try:
                if os.path.getsize(p) > 3_000_000: continue
                s = open(p, encoding='utf-8', errors='ignore').read()
            except Exception:
                continue
            for i, line in enumerate(s.splitlines(), 1):
                if '.us' in line and re.search(r'\.us[\'"\s,)\]]', line):
                    hits.append((p, i, line.strip()[:200]))
for h in hits[:60]:
    print(h[0], h[1], h[2])
print('TOTAL', len(hits))
