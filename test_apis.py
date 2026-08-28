import json, urllib.request, re

# Test 新浪API
url = 'http://hq.sinajs.cn/list=sh600053,sz000010'
try:
    req = urllib.request.Request(url, headers={'Referer': 'https://finance.sina.com.cn'})
    resp = urllib.request.urlopen(req, timeout=10)
    text = resp.read().decode('gbk', errors='replace')
    print('新浪API:', text[:300])
except Exception as e:
    print('新浪API失败:', e)

# Test 深交所API
url2 = 'https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=SGT_TZZGXL&TABKEY=tab1&PAGENO=1&RANDOM=0.1234'
try:
    req = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0'})
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    print('深交所API:', type(data), len(str(data)))
    if isinstance(data, list) and data:
        print(data[0].keys())
        print(str(data[0])[:500])
except Exception as e:
    print('深交所API失败:', e)

# Test 上交所API
url3 = 'http://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_SCSJ_CJGK_ZDZRSZJBHSPLB_L&productId=&isPagination=true&pageHelp.pageSize=100&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.cacheSize=1'
try:
    req = urllib.request.Request(url3, headers={'Referer': 'http://www.sse.com.cn'})
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read())
    print('上交所API:', type(data), data.keys() if isinstance(data, dict) else '')
    if isinstance(data, dict):
        print('result:', list(data.keys())[:5])
        if 'pageHelp' in data:
            print('pageHelp keys:', data['pageHelp'].keys())
            print('data count:', len(data['pageHelp'].get('data', [])))
except Exception as e:
    print('上交所API失败:', e)
