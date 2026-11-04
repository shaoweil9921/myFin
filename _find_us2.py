import os, re, sys
roots = ['C:/Users/shaowei_l/.openclaw', 'C:/Users/shaowei_l/.claude', 'D:/']
pat = re.compile(r"\.us['\"\)\]\s,]|'\.us'|\"\.us\"|\.us\+|US_SUFFIX|to_us|as_us")
hits = []
exts = ('.py', '.js', '.mjs', '.cjs', '.ts', '.ps1', '.md', '.txt', '.json', '.yaml', '.yml', '.toml')
for root in roots:
    if not os.path.exists(root):
        continue
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ('.git', 'node_modules', '__pycache__', 'Cache', 'cache')]
        for f in fn:
            if not f.endswith(exts):
                continue
            p = os.path.join(dp, f)
            try:
                if os.path.getsize(p) > 3_000_000: continue
                s = open(p, encoding='utf-8', errors='ignore').read()
            except Exception:
                continue
            for i, line in enumerate(s.splitlines(), 1):
                if pat.search(line):
                    hits.append((p, i, line.strip()[:200]))
for h in hits[:80]:
    print(h[0], '|', h[1], '|', h[2])
print('TOTAL', len(hits))
