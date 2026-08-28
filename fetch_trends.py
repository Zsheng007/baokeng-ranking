#!/usr/bin/env python3
"""F1维度经营改善趋势管道 — 东财F10主要指标 RPT_F10_FINANCE_MAINFINADATA

取最新报告期与上年同期（同月日）对比：
  rev_yoy  营业总收入同比
  kc_yoy   扣非净利润同比（亏损收窄=正值）
F1规则：双改善:4 / 单改善:2 / 双恶化:0
输出 st_trends.json
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
URL = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'


def secu_code(code):
    c3 = code[:3]
    if c3 in ('600', '601', '603', '605', '688', '689', '900'):
        return code + '.SH'
    if c3 == '920' or code.startswith('4') or code.startswith('8'):
        return code + '.BJ'
    return code + '.SZ'


def fetch_trend(code):
    for attempt in range(3):
        try:
            r = requests.get(URL, params={
                'reportName': 'RPT_F10_FINANCE_MAINFINADATA',
                'columns': 'REPORT_DATE,TOTALOPERATEREVE,KCFJCXSYJLR,PARENTNETPROFIT',
                'filter': f'(SECUCODE="{secu_code(code)}")',
                'pageNumber': 1, 'pageSize': 16,
                'sortColumns': 'REPORT_DATE', 'sortTypes': '-1',
            }, headers=HEADERS, timeout=15)
            res = r.json().get('result')
            if not (res and res.get('data')):
                return code, {'report_date': '', 'rev_yoy': None, 'kc_yoy': None,
                              'note': 'F10无指标数据'}
            rows = res['data']
            cur = rows[0]
            rd = (cur.get('REPORT_DATE') or '')[:10]
            md = rd[5:]  # MM-DD
            prior = next((x for x in rows[1:]
                          if (x.get('REPORT_DATE') or '')[:10][5:] == md), None)
            rev, kc = cur.get('TOTALOPERATEREVE'), cur.get('KCFJCXSYJLR')
            if prior is None or rev is None or kc is None or \
               prior.get('TOTALOPERATEREVE') in (None, 0) or prior.get('KCFJCXSYJLR') is None:
                return code, {'report_date': rd, 'rev_yoy': None, 'kc_yoy': None,
                              'note': '上年同期缺失'}
            rev_yoy = (rev - prior['TOTALOPERATEREVE']) / abs(prior['TOTALOPERATEREVE'])
            kc_yoy = (kc - prior['KCFJCXSYJLR']) / (abs(prior['KCFJCXSYJLR']) or 1)
            return code, {
                'report_date': rd,
                'rev_yoy': round(rev_yoy, 4),
                'kc_yoy': round(kc_yoy, 4),
                'rev_cur': rev, 'kc_cur': kc,
                'rev_prior': prior['TOTALOPERATEREVE'], 'kc_prior': prior['KCFJCXSYJLR'],
            }
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return code, None


def main():
    with open(os.path.join(BASE, 'st_names.json'), encoding='utf-8') as f:
        names = json.load(f)
    out, fails = {}, []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = [ex.submit(fetch_trend, c) for c in names]
        for i, fut in enumerate(as_completed(futs), 1):
            code, info = fut.result()
            if info:
                out[code] = info
            else:
                fails.append(code)
            if i % 60 == 0:
                print(f'  进度 {i}/{len(names)}')
    for code in list(fails):
        code, info = fetch_trend(code)
        if info:
            out[code] = info
            fails.remove(code)
        time.sleep(0.4)

    payload = {
        'meta': {
            'source': '东财F10 RPT_F10_FINANCE_MAINFINADATA（最新期vs上年同期）',
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ok': len(out), 'fail': len(fails),
        },
        'data': out,
    }
    with open(os.path.join(BASE, 'st_trends.json'), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    n_both = sum(1 for v in out.values()
                 if (v.get('rev_yoy') or -1) > 0 and (v.get('kc_yoy') or -1) > 0)
    n_none = sum(1 for v in out.values()
                 if v.get('rev_yoy') is not None and v.get('kc_yoy') is not None
                 and v['rev_yoy'] <= 0 and v['kc_yoy'] <= 0)
    print(f'[趋势] 完成 {len(out)}/{len(names)}；双改善 {n_both} 家，双恶化 {n_none} 家')
    mg = out.get('600543')
    if mg and mg.get('rev_yoy') is not None:
        print(f'[趋势] 莫高600543：报告期{mg["report_date"]} 营收同比{mg["rev_yoy"]:+.1%} '
              f'扣非同比{mg["kc_yoy"]:+.1%}')
    if fails:
        print('[趋势] 失败：', fails)


if __name__ == '__main__':
    main()
