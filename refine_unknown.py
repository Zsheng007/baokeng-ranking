#!/usr/bin/env python3
"""unknown退市案例45家精修分类

三层依据：
  1. 人工高置信map（公开事实：造假/主动/合并/2023面值退市潮）
  2. F10财务数据推断（退市前最后两年营收+扣非 → financial / trade）
  3. 无法判定保留unknown并标记
更新 delist_cases_final.json（cat + cat_conf + cat_reason），供回测重跑
"""
import json
import os
import time
from datetime import datetime

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
           'Referer': 'https://datacenter.eastmoney.com/'}
URL = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'

# ── 第一层：人工高置信分类 ──
MANUAL = {
    # 造假退市
    '300630': ('fraud', 'high', '普利制药财务造假，2025年重大违法退市首单'),
    '600811': ('fraud', 'high', '东方集团财务造假重述，2025年重大违法退市'),
    # 主动退市
    '601028': ('voluntary', 'high', '私有化主动退市'),
    '600387': ('voluntary', 'high', '主动退市'),
    # 吸收合并
    '601989': ('merger', 'high', '中国船舶换股吸收合并中国重工'),
    '603056': ('merger', 'medium', '京东系吸收合并/私有化'),
    # 2022-2023年面值退市潮（批量跌破1元，当年主流通道）
    '600896': ('trade', 'high', '2022年面值退市'),
    '300336': ('trade', 'high', '2023年6月面值退市潮'),
    '000806': ('trade', 'high', '2023年6月面值退市潮'),
    '000606': ('trade', 'high', '2023年6月面值退市潮'),
    '300392': ('trade', 'high', '2023年6月面值退市潮'),
    '200152': ('trade', 'high', '2023年6月B股面值退市'),
    '002417': ('trade', 'high', '2023年6月面值退市潮'),
    '300526': ('trade', 'high', '2023年6月面值退市潮'),
    '000038': ('trade', 'high', '2023年6月面值退市潮'),
    '300356': ('trade', 'high', '2023年6月面值退市潮'),
    '300089': ('trade', 'high', '2023年6月面值退市潮'),
    '002751': ('trade', 'high', '2023年6月面值退市潮'),
    '300297': ('trade', 'high', '2023年6月面值退市潮'),
    '000667': ('trade', 'high', '2023年7月面值退市潮'),
    '002503': ('trade', 'high', '2023年7月面值退市潮（*ST搜特）'),
    '000918': ('trade', 'high', '2023年7月面值退市潮'),
    '000732': ('trade', 'high', '2023年7月面值退市潮（*ST泰禾）'),
    '002504': ('trade', 'high', '2023年8月面值退市潮'),
    '000616': ('trade', 'high', '2023年8月面值退市潮'),
    '300117': ('trade', 'high', '2025年4月面值退市'),
    '002750': ('trade', 'high', '2025年5月面值退市'),
    '002336': ('trade', 'high', '2025年6月面值退市'),
    '000584': ('trade', 'high', '2025年6月面值退市'),
    '000622': ('trade', 'high', '2025年6月面值退市（*ST恒立）'),
    '300208': ('trade', 'high', '2025年6月面值退市'),
    '000040': ('trade', 'high', '2025年4月面值退市'),
    '920680': ('trade', 'medium', '2025年11月北交所面值退市'),
    '688287': ('trade', 'medium', '2026年科创板面值退市'),
    '603388': ('trade', 'medium', '2025年12月面值退市'),
}


def secu_code(code):
    c3 = code[:3]
    if c3 in ('600', '601', '603', '605', '688', '689', '900'):
        return code + '.SH'
    if c3 == '920' or code.startswith('4') or code.startswith('8'):
        return code + '.BJ'
    return code + '.SZ'


def threshold(code):
    c3 = code[:3]
    return 1e8 if c3 in ('300', '301', '688', '689', '920') else 3e8


def last_two_annuals(code):
    """退市前最后两个年报的 营收/扣非"""
    for _ in range(3):
        try:
            r = requests.get(URL, params={
                'reportName': 'RPT_F10_FINANCE_MAINFINADATA',
                'columns': 'REPORT_DATE,TOTALOPERATEREVE,KCFJCXSYJLR',
                'filter': f'(SECUCODE="{secu_code(code)}")',
                'pageNumber': 1, 'pageSize': 30,
                'sortColumns': 'REPORT_DATE', 'sortTypes': '-1',
            }, headers=HEADERS, timeout=15)
            res = r.json().get('result')
            if not (res and res.get('data')):
                return None
            annual = [x for x in res['data']
                      if (x.get('REPORT_DATE') or '0000-00-00 00:00:00')[:10].endswith('12-31')][:2]
            return annual
        except Exception:
            time.sleep(1.5)
    return None


def main():
    path = os.path.join(BASE, 'delist_cases_final.json')
    with open(path, encoding='utf-8') as f:
        doc = json.load(f)
    cases = doc['cases']

    unknowns = [c for c, v in cases.items() if v['cat'] == 'unknown']
    print(f'[精修] unknown {len(unknowns)} 家待分类')

    n_manual = n_infer = 0
    for code in unknowns:
        v = cases[code]
        if code in MANUAL:
            cat, conf, reason = MANUAL[code]
            v['cat'], v['cat_conf'], v['cat_reason'] = cat, conf, reason
            n_manual += 1
            continue
        # ── 第二层：财务数据推断 ──
        annual = last_two_annuals(code)
        if not annual or len(annual) < 2:
            v['cat_conf'] = 'low'
            v['cat_reason'] = 'F10年报数据不足，无法推断'
            continue
        rev = [x.get('TOTALOPERATEREVE') for x in annual]
        kc = [x.get('KCFJCXSYJLR') for x in annual]
        th = threshold(code)
        if all(x is not None and x < th for x in rev) and \
           all(x is not None and x < 0 for x in kc):
            v['cat'] = 'financial'
            v['cat_conf'] = 'high' if all(x < th * 0.6 for x in rev) else 'medium'
            v['cat_reason'] = (f"退市前两年营收{[round(x/1e8,2) for x in rev]}亿"
                               f"低于阈值{th/1e8:.0f}亿且扣非连续为负")
        elif all(x is not None and x > th for x in rev):
            # 营收达标还退市 → 大概率面值退市
            v['cat'] = 'trade'
            v['cat_conf'] = 'medium'
            v['cat_reason'] = f"退市前两年营收{[round(x/1e8,2) for x in rev]}亿达标，推断面值退市"
        else:
            v['cat'] = 'trade'
            v['cat_conf'] = 'low'
            v['cat_reason'] = (f"营收{[round((x or 0)/1e8,2) for x in rev]}亿/"
                               f"扣非{[round((x or 0)/1e8,2) for x in kc]}亿，非典型财务类，倾向面值")
        n_infer += 1
        time.sleep(0.3)

    doc['meta']['refined_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    doc['meta']['refine_note'] = 'unknown 45家精修：人工高置信map + F10财务推断；cat_conf分档'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)

    from collections import Counter
    cats = Counter(v['cat'] for v in cases.values())
    print(f'[精修] 人工分类 {n_manual} 家，数据推断 {n_infer} 家')
    print('[精修] 分类后分布：', dict(cats))
    rest = [(c, v['name'], v.get('cat_reason', '')) for c, v in cases.items()
            if v['cat'] == 'unknown']
    if rest:
        print(f'[精修] 仍unknown {len(rest)} 家：')
        for c, n, r in rest:
            print(f'  {c} {n}: {r}')
    print('[精修] 低置信（cat_conf=low/medium）清单：')
    for c, v in cases.items():
        if v.get('cat_conf') in ('low', 'medium'):
            print(f"  {c} {v['name']} -> {v['cat']} ({v['cat_conf']}) {v.get('cat_reason','')[:40]}")


if __name__ == '__main__':
    main()
