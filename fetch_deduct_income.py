#!/usr/bin/env python3
"""A2维度扣非主营收入口径管道 — 东财F10经营分析(主营构成) zygcfx

口径：扣非主营业务收入 = 营业收入 × (1 - 其他/补充收入占比)
配套风险标记：低毛利项(毛利率<5%)收入占比 → 贸易冲量嫌疑（A2规则-3）
输出 st_deduct_income.json
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
           'Referer': 'https://emweb.securities.eastmoney.com/'}
URL = 'https://emweb.securities.eastmoney.com/PC_HSF10/BusinessAnalysis/PageAjax'


def market_code(code):
    c3 = code[:3]
    if c3 in ('600', '601', '603', '605', '688', '689', '900'):
        return 'SH' + code
    if c3 == '920' or code.startswith('4') or code.startswith('8'):
        return 'BJ' + code
    return 'SZ' + code


def fetch_deduct(code):
    for attempt in range(3):
        try:
            r = requests.get(URL, params={'code': market_code(code)},
                             headers=HEADERS, timeout=15)
            d = r.json()
            zy = d.get('zygcfx') or []
            if not zy:
                return code, {'report_date': '', 'other_ratio': None,
                              'low_margin_ratio': None, 'note': 'F10无主营构成'}
            # 取最新年报期（12-31）优先，否则最新期
            annual = [x for x in zy
                      if (x.get('REPORT_DATE') or '0000-00-00 00:00:00')[:10].endswith('12-31')]
            period = annual[0]['REPORT_DATE'][:10] if annual else zy[0]['REPORT_DATE'][:10]
            rows = [x for x in zy if (x.get('REPORT_DATE') or '')[:10] == period]
            # 优先产品口径(MAINOP_TYPE=2)，否则行业口径(1)
            for t in ('2', '1'):
                items = [x for x in rows if str(x.get('MAINOP_TYPE')) == t
                         and x.get('MBI_RATIO') is not None]
                if items:
                    other_ratio = sum(x['MBI_RATIO'] for x in items
                                      if '其他' in (x.get('ITEM_NAME') or '')
                                      or '补充' in (x.get('ITEM_NAME') or ''))
                    low_margin_ratio = sum(
                        x['MBI_RATIO'] for x in items
                        if ('其他' not in (x.get('ITEM_NAME') or '')
                            and '补充' not in (x.get('ITEM_NAME') or '')
                            and (x.get('GROSS_RPOFIT_RATIO') is not None
                                 and 0 <= x['GROSS_RPOFIT_RATIO'] < 0.05)))
                    top = max(items, key=lambda x: x['MBI_RATIO'])
                    return code, {
                        'report_date': period,
                        'other_ratio': round(other_ratio, 4),
                        'low_margin_ratio': round(low_margin_ratio, 4),
                        'top_item': top.get('ITEM_NAME'),
                        'top_ratio': round(top['MBI_RATIO'], 4),
                        'top_gross': (round(top['GROSS_RPOFIT_RATIO'], 4)
                                      if top.get('GROSS_RPOFIT_RATIO') is not None else None),
                        'n_items': len(items),
                    }
            return code, {'report_date': period, 'other_ratio': None,
                          'low_margin_ratio': None, 'note': '该期无产品/行业构成'}
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return code, None


def main():
    with open(os.path.join(BASE, 'st_names.json'), encoding='utf-8') as f:
        names = json.load(f)
    out, fails = {}, []
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(fetch_deduct, c) for c in names]
        for i, fut in enumerate(as_completed(futs), 1):
            code, info = fut.result()
            if info:
                out[code] = info
            else:
                fails.append(code)
            if i % 60 == 0:
                print(f'  进度 {i}/{len(names)}')
    for code in list(fails):
        code, info = fetch_deduct(code)
        if info:
            out[code] = info
            fails.remove(code)
        time.sleep(0.5)

    payload = {
        'meta': {
            'source': '东财F10经营分析zygcfx（主营构成，年报期优先）',
            'note': 'other_ratio=其他/补充收入占比(扣非主营口径折减)；'
                    'low_margin_ratio=毛利率0~5%项占比(贸易冲量嫌疑，负毛利不计)',
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ok': len(out), 'fail': len(fails),
        },
        'data': out,
    }
    with open(os.path.join(BASE, 'st_deduct_income.json'), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    n_ok = sum(1 for v in out.values() if v.get('other_ratio') is not None)
    n_water = sum(1 for v in out.values()
                  if (v.get('low_margin_ratio') or 0) >= 0.30)
    print(f'[扣非主营] 完成 {len(out)}/{len(names)}，有效口径 {n_ok} 家，'
          f'低毛利占比≥30%（贸易冲量嫌疑）{n_water} 家')
    mg = out.get('600543')
    if mg:
        print(f'[扣非主营] 莫高600543：{mg["report_date"]} 其他占比{mg["other_ratio"]} '
              f'低毛利占比{mg["low_margin_ratio"]} 第一大项{mg.get("top_item")}'
              f'({mg.get("top_ratio")})')
    if fails:
        print('[扣非主营] 失败：', fails)


if __name__ == '__main__':
    main()
