#!/usr/bin/env python3
"""V2回测 — 用176家退市案例检验ST保壳评分系统V2的区分度（2026-08-28）

方法：对每家退市公司取「退市前最后一个年报」的财务数据（东财F10保留退市股数据），
按退市类型设定已知条件（面值退市→价格<1元、造假→B1=0等），演算V2分数。
若V2有效：退市公司均分应显著低于在市ST均分（63.8），且集中在C/D档。

假设口径（数据不可得处，偏保守/中性）：
  - 价格：交易类=0.9元（面值退市定义），其他=2.5元
  - 审计：规范类=0（非标直接通道）/ 造假类=0 / 财务类=6 / 交易类=12 / 未知=9
  - 立案：造假类=0，其他=10
  - S2/D1 未知=3/1；F2=0（未重整成功才退市）；H1=4
  - 财务类已触线 → A2在缺口档基础上-3（同在市*ST逻辑）
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
           'Referer': 'https://datacenter.eastmoney.com/'}
URL = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'
SHELL_BASE = 28.0


def secu_code(code):
    c3 = code[:3]
    if c3 in ('600', '601', '603', '605', '688', '689', '900'):
        return code + '.SH'
    if c3 == '920' or code[:1] in ('4', '8'):
        return code + '.BJ'
    return code + '.SZ'


def em_get(params, tries=3):
    for i in range(tries):
        try:
            r = requests.get(URL, params=params, headers=HEADERS, timeout=15)
            res = r.json().get('result')
            if res and res.get('data'):
                return res['data']
            return []
        except Exception:
            time.sleep(1 + i)
    return []


def fetch_case(code, delist_year):
    """取退市前最后年报的：营收/归母权益/扣非/实控人/注册资本"""
    sc = secu_code(code)
    # 主要指标（按报告期倒序，取退市前最后一个年报）
    rows = em_get({'reportName': 'RPT_F10_FINANCE_MAINFINADATA', 'columns': 'ALL',
                   'filter': f'(SECUCODE="{sc}")', 'pageNumber': 1, 'pageSize': 40})
    annuals = [x for x in rows if x.get('REPORT_TYPE') == '年报']
    target_year = int(delist_year) - 1
    annual = None
    for x in annuals:
        try:
            if int(str(x.get('REPORT_DATE'))[:4]) <= target_year:
                annual = x
                break
        except Exception:
            continue
    if annual is None and annuals:
        annual = annuals[-1]
    revenue = (annual or {}).get('TOTALOPERATEREVE')
    equity = (annual or {}).get('TOTAL_EQUITY_PK') or (annual or {}).get('TOTAL_EQUITY')
    report_name = (annual or {}).get('REPORT_DATE_NAME')
    # 扣非（利润表）
    inc = em_get({'reportName': 'RPT_F10_FINANCE_GINCOME', 'columns': 'ALL',
                  'filter': f'(SECUCODE="{sc}")', 'pageNumber': 1, 'pageSize': 40})
    inc_annuals = [x for x in inc if x.get('REPORT_TYPE') == '年报']
    deducted = None
    for x in inc_annuals:
        if report_name and x.get('REPORT_DATE_NAME') == report_name:
            deducted = x.get('DEDUCT_PARENT_NETPROFIT')
            break
    # 实控人+股本
    info = em_get({'reportName': 'RPT_F10_BASIC_ORGINFO', 'columns': 'ALL',
                   'filter': f'(SECUCODE="{sc}")', 'pageNumber': 1, 'pageSize': 1})
    holder = reg_cap = None
    if info:
        holder = (info[0].get('ACTUAL_HOLDER') or '').strip() or None
        reg_cap = info[0].get('REG_CAPITAL')  # 万元 ≈ 总股本(万股)
    return {'code': code, 'secucode': sc, 'holder': holder, 'reg_cap_wan': reg_cap,
            'revenue': revenue, 'equity': equity, 'deducted': deducted,
            'report': report_name}


# ── V2精简评分（回测假设口径） ──────────────────────────────
def classify_holder(h):
    if not h or h in ('无', '-'):
        return 1
    soe = any(k in h for k in ('国资委', '国有资产', '国有资本', '财政局', '财政厅',
                               '人民政府', '国有控股', '国有独资')) or h.endswith('管委会')
    if h == '国务院国有资产监督管理委员会':
        return 10
    if soe:
        has_local = any(m in h for m in ('市', '县', '区', '州', '自治区'))
        return 8 if has_local else 10
    if any(k in h for k in ('大学', '学院', '研究所', '科学院', '研究院')):
        return 8
    return 3  # 民企/个人


def score_v2(case, d_type):
    price = 0.9 if d_type == 'trade' else 2.5
    c1 = 0 if price < 1.2 else (5 if price >= 3 else 4)
    shares = (case.get('reg_cap_wan') or 0) / 1e4  # 亿股
    cap = price * shares  # 亿
    if cap <= 0:
        c2 = 4
    elif cap <= SHELL_BASE * 0.5:
        c2 = 8
    elif cap <= SHELL_BASE * 0.75:
        c2 = 6
    elif cap <= SHELL_BASE:
        c2 = 4
    elif cap <= SHELL_BASE * 1.5:
        c2 = 2
    else:
        c2 = 0
    if c1 == 0:
        c2 = min(c2, 2)
    elif c1 == 1:
        c2 = min(c2, 4)
    s1 = classify_holder(case.get('holder'))
    s2, d1, f2, h1 = 3, 1, 0, 4
    # 净资产
    eq = case.get('equity')
    if eq is None:
        a1 = 3
    else:
        e_yi = eq / 1e8
        a1 = 10 if e_yi > 10 else 8 if e_yi > 5 else 6 if e_yi > 2 else 3 if e_yi > 0 else 0
    # 营收（退市股多为深主板，阈值3亿；创业板1亿）
    rev = case.get('revenue')
    thr = 1 if case['code'][:3] in ('300', '301', '688') else 3
    if rev is None:
        a2 = 3
    else:
        r_yi = rev / 1e8
        gap = max(0.0, 1 - r_yi / thr)
        a2 = 12 if gap == 0 else 9 if gap <= .2 else 6 if gap <= .4 else 3 if gap <= .6 else 0
        if d_type in ('financial',) and gap > 0:
            a2 = max(0, a2 - 3)  # 财务类=组合指标触线退市，同*ST逻辑
    dp = case.get('deducted')
    a3 = 6 if (dp or 0) > 0 else 0 if d_type in ('financial', 'trade') else 3
    # 监管通道（按退市类型设定）
    if d_type == 'fraud':
        b1, b2 = 0, 0
        s1 = min(s1, 4)  # 造假联动封顶
    elif d_type == 'compliance':
        b1, b2 = 10, 0
    elif d_type == 'financial':
        b1, b2 = 10, 6
    else:  # trade / unknown / voluntary / merger
        b1, b2 = 10, 12
    f1 = 0 if d_type in ('financial', 'fraud') else 2
    total = c1 + c2 + s1 + s2 + a1 + a2 + a3 + d1 + b1 + b2 + f2 + f1 + h1
    # 通道封顶（与在市引擎一致）
    if c1 == 0:
        total = min(total, 50)
    if b2 == 0:
        total = min(total, 50)
    if b1 == 0:
        total = min(total, 30)
    level = 'A' if total > 70 else 'B' if total > 50 else 'C' if total > 30 else 'D'
    return {'total': total, 'level': level,
            'dims': dict(C1=c1, C2=c2, S1=s1, A1=a1, A2=a2, A3=a3, B1=b1, B2=b2)}


def main():
    with open(os.path.join(BASE, 'delist_cases_final.json'), encoding='utf-8') as f:
        cases = json.load(f)['cases']  # {code: {name, date, src, cat}}
    # merger/voluntary 是主动退市（非风险失败），排除；trade*=推断交易类
    rows = [{'code': code, 'name': v['name'], 'year': v['date'][:4],
             'type': 'trade' if v['cat'] == 'trade*' else v['cat']}
            for code, v in cases.items() if v['cat'] not in ('merger', 'voluntary')]
    print(f'[回测] 强制退市案例 {len(rows)} 家（排除merger/voluntary主动退市3+3家），'
          f'开始取退市前最后年报数据')
    fetched = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_case, c['code'], c.get('year', '2024')): c for c in rows}
        done = 0
        for fut in as_completed(futs):
            c = futs[fut]
            try:
                fetched[c['code']] = fut.result()
            except Exception:
                pass
            done += 1
            if done % 50 == 0:
                print(f'  进度 {done}/{len(rows)}')

    results = []
    for c in rows:
        fc = fetched.get(c['code'])
        if not fc or fc.get('revenue') is None:
            continue  # 数据不可得，跳过
        sc = score_v2(fc, c.get('type', 'unknown'))
        results.append({**c, 'holder': fc.get('holder'), 'report': fc.get('report'),
                        'v2_total': sc['total'], 'v2_level': sc['level'],
                        'v2_dims': sc['dims']})

    live = json.load(open(os.path.join(BASE, 'st_scores_v2.json'), encoding='utf-8'))['data']
    live_mean = sum(r['total'] for r in live) / len(live)

    from collections import Counter
    print(f'\n[回测] 有效演算 {len(results)}/{len(rows)} 家（其余退市股东财F10无数据）')
    print(f'[回测] 在市ST均分 {live_mean:.1f}')
    by_type = {}
    for t in ('trade', 'financial', 'compliance', 'fraud', 'unknown', 'voluntary', 'merger'):
        grp = [r for r in results if r.get('type') == t]
        if not grp:
            continue
        mean = sum(r['v2_total'] for r in grp) / len(grp)
        lv = Counter(r['v2_level'] for r in grp)
        cd = sum(1 for r in grp if r['v2_level'] in ('C', 'D'))
        by_type[t] = {'n': len(grp), 'mean': round(mean, 1),
                      'levels': dict(lv), 'cd_rate': round(cd / len(grp) * 100, 1)}
        print(f"  {t:<11} n={len(grp):<3} 均分={mean:5.1f}  C/D档占比={cd/len(grp)*100:4.1f}%  {dict(lv)}")
    all_mean = sum(r['v2_total'] for r in results) / len(results) if results else 0
    lv_all = Counter(r['v2_level'] for r in results)
    print(f"  全部退市     n={len(results):<3} 均分={all_mean:5.1f}  {dict(lv_all)}")
    a_or_b = sum(1 for r in results if r['v2_level'] in ('A', 'B'))
    print(f'[回测] 退市公司被判A/B档（漏报）比例：{a_or_b/len(results)*100:.1f}%')
    misses = sorted([r for r in results if r['v2_level'] in ('A', 'B')],
                    key=lambda x: -x['v2_total'])[:8]
    print('[回测] 漏报样本（退市却A/B档）：')
    for r in misses:
        print(f"    {r['code']} {r.get('name','')} {r['v2_total']} {r['v2_level']} "
              f"type={r.get('type')} holder={r.get('holder')} rev={r.get('report')}")

    with open(os.path.join(BASE, 'backtest_v2.json'), 'w', encoding='utf-8') as f:
        json.dump({'meta': {'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'valid_n': len(results), 'live_mean': round(live_mean, 1),
                            'all_mean': round(all_mean, 1), 'by_type': by_type,
                            'assumptions': '价格按类型设定/审计按类型设定/S2-D1-F2中性/F2=0'},
                   'data': results}, f, ensure_ascii=False, indent=1)
    print('\n[回测] 输出 backtest_v2.json')


if __name__ == '__main__':
    main()
