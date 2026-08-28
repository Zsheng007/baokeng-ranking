import urllib.request

# 尝试腾讯板块接口
urls = [
    'https://qt.gtimg.cn/q=blk02003511',
    'https://qt.gtimg.cn/q=blk05003511',
    'https://qt.gtimg.cn/q=blk02003510',
    'https://qt.gtimg.cn/q=blkBK0511',
    'https://qt.gtimg.cn/q=blk800811',
]
for url in urls:
    print('URL:', url)
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read().decode('gbk', errors='replace')
        print('  ', text[:300])
    except Exception as e:
        print('  ERROR:', e)
    print()
