import urllib.request, re

urls = {
    'szse': 'https://www.szse.cn/disclosure/listed/warn/index.html',
    'sse': 'http://www.sse.com.cn/assortment/stock/list/riskwarning/',
    'sse2': 'http://www.sse.com.cn/assortment/stock/list/risk/',
    'sse3': 'http://www.sse.com.cn/assortment/stock/list/info/',
}
for name, url in urls.items():
    print('===', name, url)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read().decode('utf-8', errors='replace')
        # 找包含ST的代码
        codes = re.findall(r'>(\d{6})<', text)
        st_names = re.findall(r'([\*ST]+[^<]{2,20})<', text)
        print('  codes found:', len(codes), codes[:10])
        print('  st names found:', len(st_names), st_names[:10])
        # 找可能的API
        apis = re.findall(r'https?://[^\s"\']+api[^\s"\']*', text)
        print('  apis:', apis[:5])
    except Exception as e:
        print('  ERROR:', e)
    print()
