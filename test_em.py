import json, urllib.request

codes = ['600053', '000010', '300125', '688022', '920023', '200016']
for code in codes:
    if code.startswith(('6', '9')):
        secid = f'0.{code}'
    elif code.startswith('200'):
        secid = f'1.{code}'
    else:
        secid = f'1.{code}'
    url = f'https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f12,f117&ut=bd1d9ddb04089700cf9c27f6f7426281'
    print(code, '->', secid)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        d = data.get('data', {})
        print('  ', d.get('f12'), d.get('f117'))
    except Exception as e:
        print('  ERROR:', e)
