import json, urllib.request, time

url = (
    'https://push2.eastmoney.com/api/qt/clist/get?'
    'pn=1&pz=100&po=1&np=1'
    '&ut=bd1d9ddb04089700cf9c27f6f7426281'
    '&fltt=2&invt=2&fid=f12&fs=b:BK0511'
    '&fields=f12,f14,f20'
)
for i in range(5):
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://quote.eastmoney.com/center/gridlist.html#hs_a_board',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
        })
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        items = data.get('data', {}).get('diff', [])
        print(f'attempt {i+1}: OK, {len(items)} items')
        print(items[:3])
        break
    except Exception as e:
        print(f'attempt {i+1}: FAIL {e}')
        time.sleep(5)
