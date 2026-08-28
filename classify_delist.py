#!/usr/bin/env python3
"""classify_delist.py — 补充分类132家退市案例（标准措辞关键词）"""
import json, os, re, time, random, urllib.request, urllib.parse, http.cookiejar
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
API = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
     'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
     'Origin': 'https://www.cninfo.com.cn', 'Referer': 'https://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice'}
WINDOWS = ['2021-08-01~2022-08-01', '2022-08-01~2023-08-01', '2023-08-01~2024-08-01',
           '2024-08-01~2025-08-01', '2025-08-01~2026-08-28']
KWS = [
    ('面值退市', 'trade'),
    ('交易类退市', 'trade'),
    ('净利润为负值且营业收入', 'financial'),
    ('净资产为负值', 'financial'),
    ('营业收入低于3亿元', 'financial'),
    ('重大违法', 'fraud'),
    ('无法表示意见', 'compliance'),
    ('主动终止上市', 'voluntary'),
    ('吸收合并', 'merger'),
]

def make_opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = list(H.items())
    try:
        op.open('https://www.cninfo.com.cn/new/index.jsp', timeout=10).read(200)
    except Exception:
        pass
    return op

def ts_to_date(ts):
    try:
        return datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
    except Exception:
        return ''

def main():
    d = json.load(open(os.path.join(BASE, 'delist_cases.json'), encoding='utf-8'))
    cases = d['cases']
    names_in = set(cases.keys())
    print(f'名单 {len(cases)} 家', flush=True)
    op = make_opener()
    hits = {}   # code -> {type: n}
    seen = set()
    for wi, window in enumerate(WINDOWS):
        for kw, typ in KWS:
            data = urllib.parse.urlencode({'pageNum': '1', 'pageSize': '100', 'column': 'szse',
                'tabName': 'fulltext', 'searchkey': kw, 'seDate': window, 'isHLtitle': 'true'}).encode()
            try:
                j = json.loads(op.open(API, data, timeout=25).read().decode('utf-8'))
            except Exception:
                time.sleep(4)
                try:
                    j = json.loads(op.open(API, data, timeout=25).read().decode('utf-8'))
                except Exception:
                    continue
            total = j.get('totalAnnouncement', 0)
            pages = min((total + 99) // 100, 6)
            for pg in range(1, pages + 1):
                if pg > 1:
                    data = urllib.parse.urlencode({'pageNum': str(pg), 'pageSize': '100', 'column': 'szse',
                        'tabName': 'fulltext', 'searchkey': kw, 'seDate': window, 'isHLtitle': 'true'}).encode()
                    try:
                        j = json.loads(op.open(API, data, timeout=25).read().decode('utf-8'))
                    except Exception:
                        break
                for a in (j.get('announcements') or []):
                    code = a.get('secCode', '')
                    if code not in names_in:
                        continue
                    title = re.sub(r'<[^>]+>', '', a.get('announcementTitle', '') or '')
                    date = ts_to_date(a.get('announcementTime'))
                    key = (code, title, date, kw)
                    if key in seen:
                        continue
                    seen.add(key)
                    hits.setdefault(code, {})[typ] = hits.get(code, {}).get(typ, 0) + 1
            time.sleep(random.uniform(1.0, 1.6))
        print(f'[{wi+1}/5] {window} 完成, 已命中 {len(hits)} 家', flush=True)

    # 重新分类
    from collections import Counter
    newcat = Counter()
    for code, info in cases.items():
        h = hits.get(code, {})
        if h.get('merger', 0) > 0 and not h.get('trade') and not h.get('financial'):
            cat = 'merger'
        elif h.get('voluntary', 0) > 0 and not h.get('trade'):
            cat = 'voluntary'
        elif h.get('fraud', 0) > 0 and not h.get('trade') and not h.get('financial'):
            cat = 'fraud'
        elif h.get('trade', 0) > 0:
            cat = 'trade'
        elif h.get('financial', 0) > 0:
            cat = 'financial'
        elif h.get('compliance', 0) > 0:
            cat = 'compliance'
        else:
            cat = 'unknown'
        info['hits'] = h
        info['category'] = cat
        newcat[cat] += 1
    print('\n最终分类:', dict(newcat))
    json.dump(d, open(os.path.join(BASE, 'delist_cases.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('已更新 delist_cases.json')
    # unknown列表打印
    unk = [(c, i['name'], i['date']) for c, i in cases.items() if i['category'] == 'unknown']
    print(f'unknown {len(unk)} 家:', unk[:30])

if __name__ == '__main__':
    main()
