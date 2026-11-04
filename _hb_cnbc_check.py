import json, urllib.request, sys
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
CNBC = ("https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"
        "?symbols={sym}&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1"
        "&output=json&events=1")
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
syms = ['SPY','QQQ','AAPL','AMZN','MSFT','GOOG','META','NVDA','MU','AMD','AVGO','TSLA','PLTR','ORCL','USO','TQQQ']
for s in syms:
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(CNBC.format(sym=s), headers=H), timeout=25).read().decode())
        q = d['FormattedQuoteResult']['FormattedQuote'][0]
        last = float(str(q.get('last')).replace(',',''))
        pc = float(str(q.get('previous_day_closing')).replace(',',''))
        print("%-6s last=%9.2f prev=%9.2f %+7.2f%%  chg=%s  time=%s status=%s" % (
            s, last, pc, (last/pc-1)*100, q.get('change'), q.get('last_time'), q.get('curmktstatus')))
    except Exception as e:
        print("%-6s ERR %s" % (s, e))
