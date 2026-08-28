#!/usr/bin/env python3
"""S2维度质押数据管道 — 东财中登周报 RPT_CSDC_LIST

数据逻辑：中登每周公布"有质押"的公司名单；股票不在近期名单 = 质押已清零。
取每家公司最新一条记录：TRADE_DATE 在90天内 → 用其 PLEDGE_RATIO；
更早或无记录 → pledge_ratio=0（无存续质押）。
输出 st_pledges.json
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
PY = "C:/Users/xiaot/.workbuddy/binaries/python/versions/3.13.12/python.exe"

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
           'Referer': 'https://data.eastmoney.com/gpzy/'}
URL = 'https://datacenter-web.eastmoney.com/api/data/v1/get'


def secu_code(code):
    c3 = code[:3]
    if c3 in ('600', '601', '603', '605', '688', '689', '900'):
        return code + '.SH'
    if c3 == '920' or code.startswith('4') or code.startswith('8'):
        return code + '.BJ'
    return code + '.SZ'


def fetch_pledge(code):
    """返回 (code, {'pledge_ratio':float, 'trade_date':str, 'source':str})"""
    for attempt in range(3):
        try:
            r = requests.get(URL, params={
                'reportName': 'RPT_CSDC_LIST',
                'columns': 'TRADE_DATE,PLEDGE_RATIO,PLEDGE_MARKET_CAP',
                'filter': f'(SECUCODE="{secu_code(code)}")',
                'pageNumber': 1, 'pageSize': 1,
                'sortColumns': 'TRADE_DATE', 'sortTypes': '-1',
            }, headers=HEADERS, timeout=15)
            res = r.json().get('result')
            if res and res.get('data'):
                d = res['data'][0]
                td = (d.get('TRADE_DATE') or '')[:10]
                ratio = d.get('PLEDGE_RATIO')
                if ratio is None:
                    return code, {'pledge_ratio': 0.0, 'trade_date': td,
                                  'source': '中登周报(质押比例空)'}
                dt = datetime.strptime(td, '%Y-%m-%d')
                if dt >= datetime.now() - timedelta(days=90):
                    return code, {'pledge_ratio': float(ratio), 'trade_date': td,
                                  'source': '中登周报(最新)'}
                # 老记录=质押已清零（不在近期周报名单）
                return code, {'pledge_ratio': 0.0, 'trade_date': td,
                              'source': '中登周报(记录停更,质押已清零)'}
            # 无任何记录 = 从未有质押
            return code, {'pledge_ratio': 0.0, 'trade_date': '',
                          'source': '中登周报(无记录=无质押)'}
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return code, None


def main():
    with open(os.path.join(BASE, 'st_names.json'), encoding='utf-8') as f:
        names = json.load(f)
    out = {}
    fails = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(fetch_pledge, c) for c in names]
        for i, fut in enumerate(as_completed(futs), 1):
            code, info = fut.result()
            if info:
                out[code] = info
            else:
                fails.append(code)
            if i % 60 == 0:
                print(f'  进度 {i}/{len(names)}')
    # 失败串行补抓
    for code in list(fails):
        code, info = fetch_pledge(code)
        if info:
            out[code] = info
            fails.remove(code)
        time.sleep(0.4)

    payload = {
        'meta': {
            'source': '东财datacenter RPT_CSDC_LIST（中登每周质押比例）',
            'note': '无近期周报记录=质押已清零；90天内记录取最新PLEDGE_RATIO',
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ok': len(out), 'fail': len(fails),
        },
        'data': out,
    }
    with open(os.path.join(BASE, 'st_pledges.json'), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    n_pledge = sum(1 for v in out.values() if v['pledge_ratio'] > 0)
    n_high = sum(1 for v in out.values() if v['pledge_ratio'] >= 50)
    print(f'[质押] 完成 {len(out)}/{len(names)}，有质押 {n_pledge} 家，高质押(≥50%) {n_high} 家')
    print(f'[质押] 莫高600543：{out.get("600543")}')
    if fails:
        print('[质押] 失败：', fails)


if __name__ == '__main__':
    main()
