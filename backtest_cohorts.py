#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backtest_cohorts.py — 回测队列构建

组A 退市组: delist_cases_final.json 中 2023-08-30 ~ 2026-08-30 退市的案例
组B 摘帽组: 巨潮月度窗口关键词'撤销风险警示'枚举撤销公告(申请类剔除)，
            剔除现已退市/仍ST的公司，保留摘帽成功案例
快照日 T0: 事件所在年份的前一年8月30日(2022/2023/2024/2025)

输出: backtest_cohorts.json
"""
import json
import re
import time
import random
import urllib.request
import urllib.parse
from datetime import datetime

BASE = r'C:\Users\xiaot\WorkBuddy\2026-05-16-task-2'
API_URL = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'
TOPSEARCH = 'http://www.cninfo.com.cn/new/information/topSearch/query'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

EVENT_START = '2023-08-30'
EVENT_END = '2026-08-30'
SLEEP = (0.5, 1.0)


def post(url, data, retries=3):
    """POST表单，返回json"""
    for i in range(retries):
        try:
            body = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(url, data=body, headers={
                'User-Agent': UA,
                'Referer': 'https://www.cninfo.com.cn/new/fulltextSearch',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            })
            r = urllib.request.urlopen(req, timeout=25)
            return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            if i == retries - 1:
                print(f'  [FAIL] {url} {e}')
                return None
            time.sleep(3 + i * 2)


def ts_to_date(ts_ms):
    if not ts_ms:
        return ''
    return datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d')


def months(start_str, end_str):
    """逐月窗口生成 (首月从start日起)"""
    cur = datetime.strptime(start_str, '%Y-%m-%d')
    end = datetime.strptime(end_str, '%Y-%m-%d')
    while cur < end:
        nxt_y, nxt_m = (cur.year + 1, 1) if cur.month == 12 else (cur.year, cur.month + 1)
        nxt = datetime(nxt_y, nxt_m, 1)
        window_end = min(nxt - __import__('datetime').timedelta(days=1), end)
        yield f"{cur.strftime('%Y-%m-%d')}~{window_end.strftime('%Y-%m-%d')}"
        cur = nxt


def fetch_keyword_window(se_date, keyword='撤销风险警示'):
    """小窗口关键词搜索：翻5页(150条上限，月度窗口足够)"""
    all_anns, seen = [], set()
    for page in range(1, 6):
        d = post(API_URL, {
            'pageNum': str(page), 'pageSize': '30', 'column': 'szse',
            'tabName': 'fulltext', 'plate': '', 'stock': '',
            'searchkey': keyword, 'secid': '', 'category': '', 'trade': '',
            'seDate': se_date, 'sortName': '', 'sortType': '', 'isHLtitle': 'true',
        })
        if not d:
            break
        anns = d.get('announcements') or []
        new = [a for a in anns if a.get('announcementId') and a['announcementId'] not in seen]
        for a in anns:
            if a.get('announcementId'):
                seen.add(a['announcementId'])
        all_anns.extend(new)
        if not new or not anns:
            break
        time.sleep(random.uniform(*SLEEP))
    return all_anns


def top_search(code):
    d = post(TOPSEARCH, {'keyWord': code, 'maxNum': '10'})
    if isinstance(d, list):
        for x in d:
            if x.get('code') == code:
                return x
    return None


def main():
    # ── 组A: 退市组 ──
    with open(f'{BASE}\\delist_cases_final.json', encoding='utf-8') as f:
        delist_all = json.load(f)['cases']
    delist_group = []
    for code, c in delist_all.items():
        d = c['date'].replace('-', '')
        if EVENT_START.replace('-', '') <= d <= EVENT_END.replace('-', ''):
            year = int(d[:4])
            t0 = f'{year - 1}-08-30'
            delist_group.append({
                'code': code, 'name': c['name'], 'group': 'delist',
                'event_date': f'{d[:4]}-{d[4:6]}-{d[6:]}', 'cat': c['cat'],
                't0': t0, 'snapshot_year': year,
            })
    delist_group.sort(key=lambda x: x['event_date'])
    print(f'组A 退市组: {len(delist_group)} 家 ({EVENT_START} ~ {EVENT_END})')
    from collections import Counter
    print('  退市通道:', dict(Counter(x['cat'] for x in delist_group)))
    print('  快照分布:', dict(Counter(x['t0'] for x in delist_group)))

    # ── 组B: 摘帽组(枚举撤销公告) ──
    print(f'\n枚举摘帽公告: {EVENT_START} ~ {EVENT_END} 逐月关键词搜索...')
    events = []
    n_win = 0
    for se in months(EVENT_START, EVENT_END):
        anns = fetch_keyword_window(se)
        n_win += 1
        got = []
        for a in anns:
            title = (a.get('announcementTitle') or '').replace('<em>', '').replace('</em>', '')
            code = a.get('secCode') or ''
            date = ts_to_date(a.get('announcementTime'))
            secname = (a.get('secName') or '').replace('<em>', '').replace('</em>', '')
            if not code or not date:
                continue
            # 授予类撤销(剔除"申请撤销")
            if '撤销' not in title or '风险警示' not in title or '申请' in title:
                continue
            got.append({'code': code, 'sec_name': secname, 'title': title, 'date': date})
        events.extend(got)
        print(f'  {se}: 窗口公告{len(anns)}条 → 撤销事件{len(got)}条 (累计{len(events)})')
        time.sleep(random.uniform(*SLEEP))

    # 按公司聚合: 剔除"继续被实施"(部分摘帽仍ST)
    by_comp = {}
    for e in events:
        by_comp.setdefault(e['code'], []).append(e)
    print(f'\n涉及公司 {len(by_comp)} 家')

    # 逐家topSearch查当前状态(现名/是否退市)
    cap_comp = {}
    for code in sorted(by_comp.keys()):
        ts = top_search(code)
        if ts:
            cap_comp[code] = {'name': ts.get('zwjc'), 'delisted': ts.get('delisted') == 'true'}
        time.sleep(random.uniform(0.3, 0.6))
    print(f'topSearch 完成: {len(cap_comp)}/{len(by_comp)}')

    # 过滤: 现已退市→剔除(属退市终局)；现为ST/*ST→剔除(重新戴帽)；保留成功摘帽
    uncap_group, excluded = [], []
    delist_codes = {x['code'] for x in delist_group}
    for code, evs in by_comp.items():
        cur = cap_comp.get(code) or {}
        cur_name = cur.get('name') or ''
        cur_delisted = cur.get('delisted')
        # 完全摘帽事件(无"继续被实施")
        full = [e for e in evs if '继续被实施' not in e['title']]
        if not full:
            excluded.append((code, cur_name, '仅部分摘帽(仍ST)'))
            continue
        if cur_delisted or code in delist_codes:
            excluded.append((code, cur_name, '摘帽后仍退市(归退市组)'))
            continue
        if 'ST' in cur_name.upper():
            excluded.append((code, cur_name, '摘帽后重新戴帽'))
            continue
        full.sort(key=lambda x: x['date'])
        last = full[-1]
        year = int(last['date'][:4])
        t0 = f'{year - 1}-08-30'
        # 快照日在摘帽后->不合理(跨年边界保护)
        if last['date'] <= t0:
            excluded.append((code, cur_name, '摘帽日早于快照日(跨年)'))
            continue
        uncap_group.append({
            'code': code, 'name': last['sec_name'] or cur_name, 'group': 'uncap',
            'event_date': last['date'], 'title': last['title'][:60],
            't0': t0, 'snapshot_year': year,
            'cur_name': cur_name,
        })
    uncap_group.sort(key=lambda x: x['event_date'])
    print(f'组B 摘帽组(成功摘帽且现状正常): {len(uncap_group)} 家')
    print(f'剔除 {len(excluded)} 家:')
    from collections import Counter as C2
    print('  剔除原因:', dict(C2(r for _, _, r in excluded)))
    print('  快照分布:', dict(Counter(x['t0'] for x in uncap_group)))

    payload = {
        'meta': {
            'built_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'event_window': f'{EVENT_START}~{EVENT_END}',
            'snapshot_rule': '事件年-1 的 8月30日',
            'n_delist': len(delist_group), 'n_uncap': len(uncap_group),
            'n_excluded': len(excluded),
            'excluded': [{'code': c, 'name': n, 'reason': r} for c, n, r in excluded],
            'kw_windows': n_win,
        },
        'delist': delist_group, 'uncap': uncap_group,
    }
    out = f'{BASE}\\backtest_cohorts.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f'\nsaved: {out}')


if __name__ == '__main__':
    main()
