import json, urllib.request, urllib.parse, time
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
WATCH = ['SPY','QQQ','AAPL','AMZN','MSFT','GOOG','META','NVDA','MU','AMD','AVGO','TSLA','PLTR','ORCL','USO','TQQQ','^VIX']
def get(u):
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=25).read().decode())
for tk in WATCH:
    try:
        d = get('https://query2.finance.yahoo.com/v8/finance/chart/'+urllib.parse.quote(tk)+'?range=7d&interval=1d')
        r = d['chart']['result'][0]; m=r['meta']
        ts=r['timestamp']; q=r['indicators']['quote'][0]
        days=[(time.strftime('%m-%d %H:%M', time.localtime(t)), c) for t,c in zip(ts, q['close']) if c is not None]
        last=m.get('regularMarketPrice')
        prev=days[-2][1] if len(days)>=2 else None
        pc=(last/prev-1)*100 if last and prev else None
        series=' | '.join('%s %s'%(d[0],round(d[1],2)) for d in days[-4:])
        print("%-6s live=%9.2f prev=%9.2f %+7.2f%%  %s"%(tk,last or 0,prev or 0,pc or 0,series))
    except Exception as e:
        print("%-6s ERR %s"%(tk,e))
