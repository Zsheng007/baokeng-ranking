import json, urllib.request, re

# 百度股市通 ST概念003511 成分股API可能路径
urls = [
    'https://finance.pae.baidu.com/vapi/v1/getquotation?srcid=5353&all=1&pointType=string&group=quotation_fivedata_index&query=ST%E6%A6%82%E5%BF%B5&code=BK003511&market=ab&new_Format=1&group=quotation_index_minute&finClientType=pc',
    'https://finance.pae.baidu.com/vapi/v1/getrank?srcid=5353&all=1&pointType=string&group=quotation_index_top&query=ST%E6%A6%82%E5%BF%B5&code=BK003511&market=ab&new_Format=1&finClientType=pc',
    'https://finance.pae.baidu.com/selfselect/getstockquotation?all=1&code=BK003511&skipCount=0&group=quotation_fivedata_index&finClientType=pc',
    'https://finance.pae.baidu.com/vapi/v1/getblockrank?srcid=5353&all=1&pointType=string&group=quotation_index_minute&query=ST%E6%A6%82%E5%BF%B5&code=BK003511&market=ab&new_Format=1&finClientType=pc',
]
for url in urls:
    print('URL:', url[:120])
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gushitong.baidu.com/'})
        resp = urllib.request.urlopen(req, timeout=10)
        text = resp.read().decode('utf-8', errors='replace')
        print('  len:', len(text))
        print('  sample:', text[:300])
    except Exception as e:
        print('  ERROR:', e)
    print()
