import json, urllib.request

url = (
    'https://push2.eastmoney.com/api/qt/clist/get?'
    'pn=1&pz=20&po=1&np=1'
    '&ut=bd1d9ddb04089700cf9c27f6f7426281'
    '&fltt=2&invt=2&fid=f12&fs=b:BK0511'
    '&fields=f12,f14'
)
try:
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://quote.eastmoney.com/'
    })
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    items = data.get('data', {}).get('diff', [])
    print('OK', len(items))
except Exception as e:
    print('FAIL', e)
