import json, os, urllib.request, time, sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

key = os.environ.get('TAVILY_API_KEY')


def search(q, topic='news', days=2):
    body = json.dumps({
        'api_key': key,
        'query': q,
        'topic': topic,
        'days': days,
        'max_results': 6,
        'search_depth': 'basic',
        'include_answer': True,
    }).encode()
    req = urllib.request.Request('https://api.tavily.com/search', data=body,
                                 headers={'Content-Type': 'application/json'})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
    except Exception as e:
        print('ERR', q, e)
        return
    print('====', q)
    print('ANSWER:', (d.get('answer') or '')[:700])
    for r in d.get('results', []):
        print(' -', r.get('title'), '|', r.get('url'))
        print('   ', (r.get('content') or '')[:280].replace('\n', ' '))
    time.sleep(1)


for q in [
    'Alphabet GOOG stock up 5% November 4 2026 reason',
    'Nvidia Micron chip stocks lag software rally November 4 2026 AI regulation data center',
    'Dow Jones market November 4 2026 midday blue wave relief rally stocks',
]:
    search(q)
