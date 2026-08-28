#!/usr/bin/env python3
"""delist_history.py — 从巨潮拉取近5年退市案例全名单与退市类型分类

方法: 全市场关键词搜索
  - '终止上市决定'  → 退市名单(每家至少1条决定书公告)
  - '交易类强制退市' / '财务类强制退市' / '规范类强制退市' / '重大违法强制退市'
    → 类型分类(仅对已进入名单的公司计数)
  - '主动终止上市'  → 主动退市标记
输出: delist_cases.json
"""
import json, os, re, sys, time, random
import urllib.request, urllib.parse
import http.cookiejar
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))

API_URL = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'https://www.cninfo.com.cn',
    'Referer': 'https://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice',
}
SE_DATE = '2021-08-01~2026-08-28'
# 巨潮全文搜索对长窗口会截断, 按年分段查询
WINDOWS = [
    '2021-08-01~2022-08-01',
    '2022-08-01~2023-08-01',
    '2023-08-01~2024-08-01',
    '2024-08-01~2025-08-01',
    '2025-08-01~2026-08-28',
]
MAX_PAGES = 40
PAGE_SIZE = 100

# (关键词, 类型标记)
TYPE_KWS = [
    ('终止上市决定', None),            # 名单源
    ('交易类强制退市', 'trade'),
    ('财务类强制退市', 'financial'),
    ('规范类强制退市', 'compliance'),
    ('重大违法强制退市', 'fraud'),
    ('主动终止上市', 'voluntary'),
]


def make_opener():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = list(HEADERS.items())
    try:
        opener.open('https://www.cninfo.com.cn/new/index.jsp', timeout=10).read(200)
        time.sleep(0.5)
    except Exception:
        pass
    return opener


def strip_tags(t):
    return re.sub(r'<[^>]+>', '', t or '').strip()


def ts_to_date(ts):
    try:
        return datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
    except Exception:
        return ''


def fetch_kw(opener, kw, se_date):
    anns, page = [], 1
    while page <= MAX_PAGES:
        data = urllib.parse.urlencode({
            'pageNum': str(page), 'pageSize': str(PAGE_SIZE),
            'column': 'szse', 'tabName': 'fulltext',
            'searchkey': kw, 'seDate': se_date, 'isHLtitle': 'true',
        }).encode()
        try:
            j = json.loads(opener.open(API_URL, data, timeout=25).read().decode('utf-8'))
        except Exception:
            time.sleep(5)
            try:
                j = json.loads(opener.open(API_URL, data, timeout=25).read().decode('utf-8'))
            except Exception:
                break
        batch = j.get('announcements') or []
        anns.extend(batch)
        total = j.get('totalAnnouncement', 0)
        if page == 1:
            print(f'    总量 {total}', flush=True)
        if len(anns) >= total or not batch:
            break
        page += 1
        time.sleep(random.uniform(1.0, 1.8))
    return anns


def main():
    print(f'退市案例采集 窗口 {SE_DATE}', flush=True)
    opener = make_opener()
    delist = {}      # code -> {name, date, title}
    type_hits = {}   # code -> {trade/financial/compliance/fraud/voluntary: count}
    seen = set()

    for wi, window in enumerate(WINDOWS):
        for kw, typ in TYPE_KWS:
            print(f'[{wi+1}/{len(WINDOWS)}] {window} | {kw}', flush=True)
            anns = fetch_kw(opener, kw, window)
            for a in anns:
                code = a.get('secCode', '')
                if not code:
                    continue
                title = strip_tags(a.get('announcementTitle', ''))
                date = ts_to_date(a.get('announcementTime'))
                key = (code, title, date)
                if key in seen:
                    continue
                seen.add(key)
                if typ is None:
                    # 名单: 标题须含"终止上市"
                    if '终止上市' in title:
                        if code not in delist or date < delist[code]['date']:
                            delist[code] = {'name': a.get('secName', ''), 'date': date, 'title': title}
                else:
                    type_hits.setdefault(code, {})[typ] = type_hits.get(code, {}).get(typ, 0) + 1
            print(f'  累计: 名单 {len(delist)} 家', flush=True)
            time.sleep(random.uniform(1.5, 2.5))

    # 分类: 仅对名单内公司
    cases = {}
    for code, info in delist.items():
        hits = type_hits.get(code, {})
        types = {k: v for k, v in hits.items() if v > 0}
        if 'voluntary' in types:
            cat = 'voluntary'
        elif 'fraud' in types and 'financial' not in types:
            cat = 'fraud'
        else:
            ranked = sorted(types.items(), key=lambda x: -x[1])
            cat = ranked[0][0] if ranked else 'unknown'
        cases[code] = {**info, 'hits': types, 'category': cat}

    from collections import Counter
    print('\n分类分布:', dict(Counter(c['category'] for c in cases.values())))
    print('按年分布:', dict(Counter(c['date'][:4] for c in cases.values())))
    json.dump({'meta': {'fetched_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
                        'window': SE_DATE},
               'cases': cases},
              open(os.path.join(BASE, 'delist_cases.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'保存 delist_cases.json: {len(cases)} 家')


if __name__ == '__main__':
    main()
