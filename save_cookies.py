import pickle, json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp('http://localhost:9222', timeout=15000)
    ctx = browser.contexts[0]
    page = ctx.pages[0]

    print('URL:', page.url[:100])
    text = page.inner_text('body')[:300]
    print('Page text:', text)

    cookies = ctx.cookies()
    print('Total cookies:', len(cookies))
    jarsy = [c for c in cookies if 'jarsy' in c.get('domain','').lower()]
    print('Jarsy cookies:', len(jarsy))
    for c in jarsy:
        name = c['name']
        val = c['value'][:30]
        print(' ', name, ':', val)

    with open('jarsy_cookies.pkl', 'wb') as f:
        pickle.dump(cookies, f)
    with open('jarsy_cookies.json', 'w') as f:
        json.dump(cookies, f, indent=2)
    print('Cookies saved.')
    browser.close()
