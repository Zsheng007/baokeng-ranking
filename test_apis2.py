import json, urllib.request

# Test multiple SSE APIs
candidates = [
    'http://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_SCSJ_CJGK_RISKSTOCKLST&productId=&isPagination=true&pageHelp.pageSize=100&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.cacheSize=1',
    'http://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_SCSJ_CJGK_ZDZRSZJBHSPLB_L',
    'http://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_SCSJ_CJGK_ZDZRSZJBHSPLB_L&productId=&isPagination=true&pageHelp.pageSize=100&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.cacheSize=1',
    'http://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_SCSJ_CJGK_ZDZRSZJBHSPLB_L&isPagination=true&pageHelp.pageSize=100&pageHelp.pageNo=1',
]

headers = {'Referer': 'http://www.sse.com.cn', 'User-Agent': 'Mozilla/5.0'}
for url in candidates:
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        print('URL:', url[:100])
        print('  result:', data.get('result'))
        print('  pageHelp data type:', type(data.get('pageHelp', {}).get('data')))
        if data.get('pageHelp', {}).get('data'):
            print('  sample:', data['pageHelp']['data'][:1])
        print()
    except Exception as e:
        print('FAIL', url[:80], e)
        print()

# Test SZSE APIs
sz_candidates = [
    'https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=SGT_TZZGXL&TABKEY=tab1&PAGENO=1',
    'https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=main_zqjsxx&TABKEY=tab1&PAGENO=1',
    'https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=SGT_TZZGXL&TABKEY=tab1',
]
for url in sz_candidates:
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        print('SZ URL:', url[:100])
        print('  data len:', len(str(data)))
        print('  keys:', data[0].keys() if isinstance(data, list) else data.keys())
        print()
    except Exception as e:
        print('SZ FAIL', url[:80], e)
        print()
