import urllib.request, urllib.parse, re, json, time

def ddg(q):
    u = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(q)
    req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    h = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'ignore')
    out = []
    for m in re.finditer(r'result__a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', h, re.S):
        t = re.sub('<[^>]+>', '', m.group(2)).strip()
        out.append((t, m.group(1)[:160]))
    return out[:8]

for q in ['AAPL stock jumps November 4 2026', 'Amazon stock jumps 8% November 4 2026', 'Microsoft Azure record quarter stock November 2026']:
    print('====', q)
    for t, l in ddg(q):
        print(' -', t, '|', l)
    time.sleep(2)
