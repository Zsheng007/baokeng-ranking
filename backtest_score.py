#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backtest_score.py — 回测评分引擎

复用 score_v2.score_v2 同一代码路径（"回测分=榜单分"同源），
为每家公司在快照日T0构建合成ctx打分，按T0队列排名，关联结局：
  退市组 → 市值归0；摘帽组 → 事件日市值与前复权涨幅。

降级说明（对所有回测公司统一，保证组间可比）：
  S1=3(实控人未知default) / S2=3(质押缺失missing，冻结仍归零) /
  A2=营业总收入口径 / F1=复合代理 / C2壳基准=当前33.81亿

输出: backtest_results.json
"""
import json
import os
import re
from datetime import datetime
from collections import Counter

import score_v2

BASE = os.path.dirname(os.path.abspath(__file__))

T0_DATES = ['2022-08-30', '2023-08-30', '2024-08-30', '2025-08-30']

# 公告主体黑名单: 律所/会计师所/券商/董监高/文件类误判为简称
BAD_NAME = re.compile(r'律师|会计师|事务所|证券有限|证券股份|独立董事|董事会|监事|委员会|'
                      r'保荐|督导|评估|声明|意见|说明|提示|报告|更正|补充|澄清|公告|预警|'
                      r'重整|管理人|清算|债权人|职工代表|持股|大会')


def pick_name(r):
    """T0时点简称: title推断优先(通过黑名单+长度过滤), 否则队列名"""
    nt = r.get('name_t0') or ''
    qn = r['name'] or ''
    if nt and len(nt) <= 10 and not BAD_NAME.search(nt):
        return nt
    return qn or nt


def build_ctx(t0, codes_subset, recs):
    """按T0构建合成ctx（复用score_v2全部逻辑）"""
    ctx = {}
    with open(os.path.join(BASE, 'score_config_v2.json'), encoding='utf-8') as f:
        cfg = json.load(f)
    ctx['cfg'] = cfg
    ctx['dims'] = cfg['dims']
    ctx['gates'] = cfg['gates']
    ctx['today'] = datetime.strptime(t0, '%Y-%m-%d')

    name_map, mkt, fin_data, risk_flags = {}, {}, {}, {}
    report_dates = set()
    for code in codes_subset:
        r = recs[code]
        name_map[code] = pick_name(r) or '未知'
        price = r.get('price_t0')
        shares = (r.get('fin') or {}).get('shares')
        mkt[code] = {
            'price': price if price else 3,
            'market_cap_yi': round(price * shares / 1e8, 2) if (price and shares) else 0,
        }
        fin = r.get('fin') or {}
        fin_data[code] = {
            'revenue': fin.get('revenue'),
            'deducted_profit': fin.get('deducted_profit'),
            'total_equity': fin.get('total_equity'),
            'operating_cf': fin.get('operating_cf'),
            'pledge_ratio': None,  # 点时质押无源 → S2 missing中性
        }
        if fin.get('period'):
            report_dates.add(fin['period'])
        risk_flags[code] = r.get('flags') or {}
    ctx['name_map'] = name_map
    ctx['mkt'] = mkt
    ctx['fin_data'] = fin_data
    ctx['risk_flags'] = risk_flags
    ctx['report_date'] = sorted(report_dates)[-1] if report_dates else ''
    ctx['controllers'] = {}   # S1 default=3 统一中性
    ctx['pledges'] = {}       # S2 missing=3 统一中性(冻结仍归零)
    ctx['trends'] = {}        # F1 走复合代理
    ctx['deduct_inc'] = {}    # A2 营业总收入口径
    ctx['v1_scores'] = {}
    # 壳基准: 与生产同源
    try:
        sb = cfg['shell_base']
        with open(sb['json'], encoding='utf-8') as f:
            _c = json.load(f).get('benchmark_config', {})
        ctx['shell_base'] = float(_c.get('own_mcap_median_yi') or sb['fallback'])
    except Exception:
        ctx['shell_base'] = float(cfg['shell_base']['fallback'])
    return ctx


def main():
    with open(os.path.join(BASE, 'backtest_data.json'), encoding='utf-8') as f:
        data = json.load(f)['data']
    print(f'回测公司: {len(data)} 家')

    # 可评分判定: 有T0价格即可(市值/财务缺失走missing档)
    usable, skipped = {}, []
    for code, r in data.items():
        if r.get('price_t0'):
            usable[code] = r
        else:
            skipped.append((code, r['name'], '无T0行情'))
    print(f'可评分: {len(usable)} 家 | 跳过: {len(skipped)} 家')

    # 按T0分组构建ctx并评分
    results = []
    for t0 in T0_DATES:
        codes_t0 = [c for c, r in usable.items() if r['t0'] == t0]
        if not codes_t0:
            continue
        ctx = build_ctx(t0, codes_t0, usable)
        rows = []
        for code in codes_t0:
            r = usable[code]
            try:
                s = score_v2.score_v2(code, ctx)
            except Exception as e:
                print(f'  [ERR] {code} {e}')
                continue
            out = {
                'code': code, 'name': pick_name(r),
                'group': r['group'], 't0': t0, 'cat': r.get('cat'),
                'event_date': r['event_date'],
                'price_t0': r.get('price_t0'),
                'mktcap_t0': ctx['mkt'][code]['market_cap_yi'],
                'fin_period': (r.get('fin') or {}).get('period'),
                'n_ann': r.get('n_ann', 0),
            }
            for k in ('C1', 'C2', 'S1', 'S2', 'A1', 'A2', 'A3', 'D1', 'B1', 'B2', 'F2', 'F1', 'H1'):
                out[k] = s[k]
            out['total'] = s['total']
            out['level'] = s['level']
            out['note'] = s['note']
            # 结局
            if r['group'] == 'delist':
                out['outcome_mktcap'] = 0
                out['gain'] = None
                out['event_mktcap'] = 0
            else:
                shares_ev = (r.get('fin_event') or {}).get('shares') or (r.get('fin') or {}).get('shares')
                pe = r.get('price_event')
                out['event_mktcap'] = round(pe * shares_ev / 1e8, 2) if (pe and shares_ev) else None
                q0, qe = r.get('qfq_price_t0'), r.get('qfq_price_event')
                out['gain'] = round(qe / q0 - 1, 4) if (q0 and qe and q0 > 0) else None
                out['outcome_mktcap'] = out['event_mktcap']
            rows.append(out)
        rows.sort(key=lambda x: x['total'], reverse=True)
        for i, x in enumerate(rows, 1):
            x['rank'] = i
            x['rank_pct'] = round(i / len(rows), 3)
        results.extend(rows)
        lv = Counter(x['level'] for x in rows)
        print(f'T0={t0}: {len(rows)}家 等级{dict(sorted(lv.items()))}')

    # ── 分析摘要 ──
    dl = [x for x in results if x['group'] == 'delist']
    uc = [x for x in results if x['group'] == 'uncap']
    print(f'\n══════ 回测核心指标 ══════')
    print(f'退市组 {len(dl)} 家: 均分{sum(x["total"] for x in dl)/len(dl):.1f} '
          f'中位数{sorted(x["total"] for x in dl)[len(dl)//2]} '
          f'评级{dict(sorted(Counter(x["level"] for x in dl).items()))}')
    print(f'摘帽组 {len(uc)} 家: 均分{sum(x["total"] for x in uc)/len(uc):.1f} '
          f'中位数{sorted(x["total"] for x in uc)[len(uc)//2]} '
          f'评级{dict(sorted(Counter(x["level"] for x in uc).items()))}')
    # 命中率
    dl_cd = [x for x in dl if x['level'] in ('C', 'D')]
    dl_ab = [x for x in dl if x['level'] in ('A', 'B')]
    uc_ab = [x for x in uc if x['level'] in ('A', 'B')]
    uc_cd = [x for x in uc if x['level'] in ('C', 'D')]
    print(f'退市组落C/D(预警正确): {len(dl_cd)}/{len(dl)} = {len(dl_cd)/len(dl)*100:.1f}%')
    print(f'退市组落A/B(漏报): {len(dl_ab)}/{len(dl)} = {len(dl_ab)/len(dl)*100:.1f}%')
    print(f'摘帽组落A/B: {len(uc_ab)}/{len(uc)} = {len(uc_ab)/len(uc)*100:.1f}%')
    print(f'摘帽组落C/D(误报): {len(uc_cd)}/{len(uc)} = {len(uc_cd)/len(uc)*100:.1f}%')
    # 通道细分
    risk_cats = ('trade', 'trade*', 'financial', 'fraud', 'compliance')
    dl_risk = [x for x in dl if x['cat'] in risk_cats]
    dl_other = [x for x in dl if x['cat'] not in risk_cats]
    if dl_risk:
        print(f'退市组-风险类通道{len(dl_risk)}家: C/D占比 '
              f'{sum(1 for x in dl_risk if x["level"] in ("C","D"))/len(dl_risk)*100:.1f}%')
    if dl_other:
        print(f'退市组-并购/主动{len(dl_other)}家: C/D占比 '
              f'{sum(1 for x in dl_other if x["level"] in ("C","D"))/len(dl_other)*100:.1f}% (此类非风险事件,不计准确率)')
    # 闸门
    for dim, name in (('B1', '重大违法封顶'), ('B2', '非标意见封顶'), ('C1', '面值危机封顶')):
        dl_g = sum(1 for x in dl if x[dim] == 0)
        uc_g = sum(1 for x in uc if x[dim] == 0)
        print(f'{name}({dim}=0): 退市组{dl_g}/{len(dl)} 摘帽组{uc_g}/{len(uc)}')
    # 摘帽组涨幅关联
    pairs = [(x['total'], x['gain']) for x in uc if x['gain'] is not None]
    if len(pairs) >= 5:
        import statistics
        med_g = statistics.median(p[1] for p in pairs)
        hi = [g for s, g in pairs if s >= 50]
        lo = [g for s, g in pairs if s < 50]
        print(f'摘帽组涨幅: 中位数{med_g*100:+.1f}% | 高分组(≥50)均值'
              f'{(sum(hi)/len(hi)*100 if hi else float("nan")):+.1f}%({len(hi)}家) | '
              f'低分组(<50)均值{(sum(lo)/len(lo)*100 if lo else float("nan")):+.1f}%({len(lo)}家)')
    # 漏报/误报清单
    print('\n退市组漏报(A/B级)清单:')
    for x in sorted(dl_ab, key=lambda x: -x['total']):
        print(f"  {x['code']} {x['name']:<10} {x['total']:>3} {x['level']} rank={x['rank']} cat={x['cat']} {x['note'][:40]}")
    print('\n摘帽组误报(C/D级)清单:')
    for x in sorted(uc_cd, key=lambda x: x['total']):
        print(f"  {x['code']} {x['name']:<10} {x['total']:>3} {x['level']} rank={x['rank']} {x['note'][:40]}")

    payload = {
        'meta': {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'engine': 'score_v2.py 同源复用（合成ctx）',
            'snapshot_rule': '事件年-1的8月30日; 排名=同T0回测队列内',
            'degradations': 'S1=3/S2=3(除冻结)/A2营业总收入口径/F1复合代理/C2壳基准33.81亿当前值',
            'n_delist': len(dl), 'n_uncap': len(uc), 'n_skipped': skipped,
        },
        'results': results,
    }
    out = os.path.join(BASE, 'backtest_results.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print(f'\nsaved: {out}')


if __name__ == '__main__':
    main()
