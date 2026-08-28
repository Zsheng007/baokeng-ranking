#!/usr/bin/env python3
"""ST保壳评分系统V1 评分引擎 — 十四维100分制，真实数据驱动（2026-08-28 定版）

正式名称：ST保壳评分系统V1（前身为 V618+G 十一维 / V7 十四维内部迭代版）

升级要点（V618+G → ST保壳评分系统V1）：
  1. B1/B2/B3 从类型推演 → 巨潮公告真实数据（立案/处罚/非标审计意见）
  2. C1 拆分为 C1面值距离(8) + C2市值水平(4)
  3. 新增 F2 重组/纾困进度(7) — 重整阶段/资产出售/债务豁免/赠与
  4. 新增 H1 实控人风险(8) — 股份冻结/限制消费/实控人立案
  5. G1 市值偏离度降权 10→5

评分方向：分数越高 = 保壳越容易

| 维度 | 满分 | 数据源 |
|------|------|--------|
| A1 扣非净利润  | 5  | AkShare 同花顺（2025年报） |
| A2 营业收入    | 12 | AkShare 东方财富 |
| A3 净资产      | 8  | AkShare 东方财富 |
| B1 违规存量    | 5  | 巨潮公告（立案调查）+类型 |
| B2 内控审计    | 5  | 巨潮公告（非标意见分级）+类型 |
| B3 监管处罚    | 6  | 巨潮公告（行政处罚/警示函） |
| C1 面值距离    | 8  | 腾讯实时价格 |
| C2 市值水平    | 4  | 腾讯实时市值 |
| D1 现金流质量  | 10 | AkShare 东方财富 |
| E1 股权稳定性  | 8  | AkShare 质押比例 |
| F1 持续经营    | 9  | 扣非+营收复合 |
| F2 重组/纾困   | 7  | 巨潮公告（重整/出售/豁免/赠与） |
| G1 市值偏离度  | 5  | 归母权益+市值 |
| H1 实控人风险  | 8  | 巨潮公告（冻结/限高/实控人立案） |
| 合计           | 100 | |
"""

import json
import os
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))

# ── 加载数据 ──────────────────────────────────────────────
with open(os.path.join(BASE, 'st_names.json'), encoding='utf-8') as f:
    name_map = json.load(f)
with open(os.path.join(BASE, 'st_market_data.json'), encoding='utf-8') as f:
    mkt = json.load(f)
with open(os.path.join(BASE, 'st_financials.json'), encoding='utf-8') as f:
    fin_data_raw = json.load(f)
fin_data = fin_data_raw['data']
REPORT_DATE = fin_data_raw.get('report_date', '')
REPORT_LABEL = f"{REPORT_DATE[:4]}年{int(REPORT_DATE[4:6])}月报" if REPORT_DATE and len(REPORT_DATE) == 8 else '未知报告期'

# 公告风险信号（可能不存在 → 降级）
risk_flags = {}
flags_meta = {}
flags_file = os.path.join(BASE, 'st_risk_flags.json')
if os.path.exists(flags_file):
    with open(flags_file, encoding='utf-8') as f:
        rf = json.load(f)
    risk_flags = rf.get('flags', {})
    flags_meta = rf.get('meta', {})
else:
    print('[WARN] st_risk_flags.json 不存在，B/F2/H1 走类型推演降级')

codes = list(name_map.keys())
TODAY = datetime.now()


def months_ago(date_str, n):
    """公告日期是否在 n 个月内"""
    try:
        d = datetime.strptime(date_str, '%Y-%m-%d')
        return d >= TODAY - timedelta(days=n * 30)
    except Exception:
        return False


def flag_bucket(code, bucket):
    """取某公司某桶的公告列表，返回按日期降序"""
    fl = risk_flags.get(code, {}).get(bucket, [])
    return sorted(fl, key=lambda x: x.get('date', ''), reverse=True)


# ── 板块判定 ──────────────────────────────────────────────
def get_board(code):
    c3 = code[:3]
    if c3 in ('300', '301'):
        return '创业板'
    if c3 == '688':
        return '科创板'
    if c3 == '920':
        return '北交所'
    if c3 == '200':
        return 'B股'
    return '主板'


def fin_val(code, field, default=None):
    v = fin_data.get(code, {}).get(field)
    return default if v is None else v


# ══════════════════════════════════════════════════════════
# ST保壳评分系统V1 评分引擎
# ══════════════════════════════════════════════════════════
def score_stock(code):
    name = name_map[code]
    md = mkt.get(code, {})
    price = md.get('price', 3)
    board = get_board(code)

    is_star = name.startswith('*ST')
    stype = '*ST' if is_star else 'ST'
    is_b = code.startswith('200')
    is_bj = board == '北交所'  # 巨潮沪深库覆盖不到 → 降级

    # ── 默认原因标签 ──
    if is_star:
        if board in ('主板', '北交所'):
            reason = '财务退市风险：净利润/净资产/营收不达标'
        else:
            reason = '财务退市风险：持续亏损触发退市预警'
    else:
        reason = '其他风险警示：内控/违规担保/资金占用/持续经营'
    if is_b:
        reason = 'B股风险警示'

    # ── 财务数据提取 ──
    deducted = fin_val(code, 'deducted_profit')
    revenue = fin_val(code, 'revenue')
    net_equity = fin_val(code, 'total_equity')
    operating_cf = fin_val(code, 'operating_cf')
    pledge_ratio = fin_val(code, 'pledge_ratio')
    mkt_cap = md.get('market_cap_yi', 0) or 0

    rev_threshold = 1 if board in ('创业板', '科创板', 'B股') else 3  # 亿

    # ════ A1 扣非净利润 (0-5) ════
    if deducted is not None:
        d_yi = deducted / 1e8
        if d_yi >= 5:    a1_risk = 0
        elif d_yi >= 1:  a1_risk = 1
        elif d_yi >= 0:  a1_risk = 2
        elif d_yi >= -1: a1_risk = 3
        elif d_yi >= -5: a1_risk = 4
        else:            a1_risk = 5
    else:
        a1_risk = 3

    # ════ A2 营业收入 (0-12) ════
    if revenue is not None:
        ratio = (revenue / 1e8) / rev_threshold
        if ratio >= 5:     a2_risk = 0
        elif ratio >= 3:   a2_risk = 2
        elif ratio >= 2:   a2_risk = 4
        elif ratio >= 1:   a2_risk = 6
        elif ratio >= 0.7: a2_risk = 8
        elif ratio >= 0.5: a2_risk = 10
        else:              a2_risk = 12
    else:
        a2_risk = 7

    # ════ A3 净资产 (0-8) ════
    if net_equity is not None:
        e_yi = net_equity / 1e8
        if e_yi >= 10:   a3_risk = 0
        elif e_yi >= 5:  a3_risk = 1
        elif e_yi >= 2:  a3_risk = 2
        elif e_yi >= 0:  a3_risk = 3
        elif e_yi >= -1: a3_risk = 6
        elif e_yi >= -5: a3_risk = 7
        else:            a3_risk = 8
    else:
        a3_risk = 4

    # ════ B1 违规存量 (0-5) — 立案调查（真实公告） ════
    inv = flag_bucket(code, 'investigation')
    if inv and not is_bj:
        inv_recent = [x for x in inv if months_ago(x['date'], 12)]
        if inv_recent:
            b1_risk = 5  # 近12个月仍处立案状态
        else:
            b1_risk = 4  # 有立案历史（>12个月前）
    else:
        b1_risk = 1 if is_star else 2  # 降级：类型推演
        if is_b:
            b1_risk = 2

    # ════ B2 内控审计 (0-5) — 非标意见分级（真实公告） ════
    adverse = flag_bucket(code, 'audit_adverse')
    qualified = flag_bucket(code, 'audit_qualified')
    emphasis = flag_bucket(code, 'audit_emphasis')
    if adverse and not is_bj:
        b2_risk = 5      # 无法表示意见/否定意见
    elif qualified and not is_bj:
        b2_risk = 3      # 保留意见
    elif emphasis and not is_bj:
        b2_risk = 2      # 带强调事项/非标准
    else:
        b2_risk = 1 if is_star else 0  # 降级：类型推演（无命中=最近年报无重非标，也可能未覆盖）
        if is_b:
            b2_risk = 1

    # ════ B3 监管处罚 (0-6) — 行政处罚/警示函（真实公告） ════
    pen = flag_bucket(code, 'penalty')
    warn = flag_bucket(code, 'warning')
    if pen and not is_bj:
        pen_recent = [x for x in pen if months_ago(x['date'], 12)]
        b3_risk = 6 if pen_recent else 5   # 行政处罚决定
    elif warn and not is_bj:
        warn_recent = [x for x in warn if months_ago(x['date'], 12)]
        b3_risk = 3 if warn_recent else 2  # 警示函/监管函
    else:
        b3_risk = 1  # 降级：未命中处罚公告（保守给1分风险）
        if is_b:
            b3_risk = 1

    # ════ C1 面值距离 (0-8) ════
    if price <= 0:
        c1_risk = 6
    elif price < 1:    c1_risk = 8  # 面值退市危机
    elif price < 1.2:  c1_risk = 7
    elif price < 1.5:  c1_risk = 6
    elif price < 2:    c1_risk = 4
    elif price < 3:    c1_risk = 3
    elif price < 5:    c1_risk = 2
    elif price < 10:   c1_risk = 1
    else:              c1_risk = 0

    # ════ C2 市值水平 (0-4) ════
    if mkt_cap <= 0:   c2_risk = 2
    elif mkt_cap < 4:  c2_risk = 4   # 壳太薄
    elif mkt_cap < 8:  c2_risk = 3
    elif mkt_cap < 15: c2_risk = 2
    elif mkt_cap < 30: c2_risk = 1
    else:              c2_risk = 0

    # ════ D1 现金流质量 (0-10) ════
    if operating_cf is not None and revenue is not None and revenue != 0:
        ocf_ratio = operating_cf / revenue
        if ocf_ratio >= 0.20:   d1_risk = 0
        elif ocf_ratio >= 0.10: d1_risk = 1
        elif ocf_ratio >= 0.05: d1_risk = 3
        elif ocf_ratio >= 0:    d1_risk = 5
        elif ocf_ratio >= -0.05: d1_risk = 7
        elif ocf_ratio >= -0.10: d1_risk = 9
        else:                    d1_risk = 10
    else:
        d1_risk = 6

    # ════ E1 股权稳定性 (0-8) ════
    if pledge_ratio is not None:
        if pledge_ratio < 5:    e1_risk = 0
        elif pledge_ratio < 15: e1_risk = 2
        elif pledge_ratio < 25: e1_risk = 4
        elif pledge_ratio < 40: e1_risk = 6
        else:                   e1_risk = 8
    else:
        e1_risk = 4

    # ════ F1 持续经营 (0-9) ════
    if deducted is not None and revenue is not None:
        d_positive = deducted > 0
        r_ok = (revenue / 1e8) >= rev_threshold
        if d_positive and r_ok:            f1_risk = 0
        elif d_positive or r_ok:           f1_risk = 4
        elif net_equity and net_equity > 0: f1_risk = 5
        else:                              f1_risk = 9
    else:
        f1_risk = 5

    # ════ F2 重组/纾困进度 (0-7) — 直接计正向分 ════
    f2_score = 0
    f2_signals = []
    restructuring = flag_bucket(code, 'restructuring')
    asset_sale = flag_bucket(code, 'asset_sale')
    debt_waiver = flag_bucket(code, 'debt_waiver')
    donation = flag_bucket(code, 'donation')
    if not is_bj:
        res_exec = [x for x in restructuring if x.get('stage') == 'exec']
        res_early = [x for x in restructuring if x.get('stage') == 'early']
        if res_exec:
            f2_score += 4
            f2_signals.append('重整执行中')
        elif res_early:
            f2_score += 1  # 申请/预重整仍是高风险期
            f2_signals.append('申请/预重整')
        if asset_sale:
            f2_score += 2
            f2_signals.append('重大资产出售/重组')
        if debt_waiver:
            f2_score += 1
            f2_signals.append('债务豁免/重组')
        if donation:
            f2_score += 1
            f2_signals.append('资产赠与')
        f2_score = min(7, f2_score)

    # ════ G1 市值偏离度 (0-5) ════
    if net_equity is not None and net_equity > 0 and mkt_cap > 0:
        ne_yi = net_equity / 1e8
        standard_cap = ne_yi + 20  # 壳费20亿
        if mkt_cap <= standard_cap * 0.6:    g1_risk = 0
        elif mkt_cap <= standard_cap * 0.8:  g1_risk = 1
        elif mkt_cap <= standard_cap:        g1_risk = 2
        elif mkt_cap <= standard_cap * 1.2:  g1_risk = 3
        elif mkt_cap <= standard_cap * 1.5:  g1_risk = 4
        else:                                g1_risk = 5
    elif net_equity is not None and net_equity <= 0:
        g1_risk = 5
    else:
        g1_risk = 3

    # ════ H1 实控人风险 (0-8) — 冻结/限高/实控人立案 ════
    freeze = flag_bucket(code, 'freeze')
    consume = flag_bucket(code, 'consume_limit')
    h1_risk = 0
    h1_signals = []
    if not is_bj:
        if freeze:
            fr_recent = [x for x in freeze if months_ago(x['date'], 12)]
            h1_risk += 3 if fr_recent else 1
            h1_signals.append('股份冻结')
        if consume:
            h1_risk += 3
            h1_signals.append('限制消费')
        # 立案公告标题含实控人 → 实控人被立案
        for x in flag_bucket(code, 'investigation'):
            if '实际控制人' in x['title'] or '控股股东' in x['title']:
                h1_risk += 2
                h1_signals.append('立案')
                break
        h1_risk = min(8, h1_risk)
    else:
        h1_risk = 2  # 北交所降级

    # ════ 方向反转：风险 → 保壳能力分 ════
    a1 = 5 - min(5, a1_risk)
    a2 = 12 - min(12, a2_risk)
    a3 = 8 - min(8, a3_risk)
    b1 = 5 - min(5, b1_risk)
    b2 = 5 - min(5, b2_risk)
    b3 = 6 - min(6, b3_risk)
    c1 = 8 - min(8, c1_risk)
    c2 = 4 - min(4, c2_risk)
    d1 = 10 - min(10, d1_risk)
    e1 = 8 - min(8, e1_risk)
    f1 = 9 - min(9, f1_risk)
    f2 = f2_score
    g1 = 5 - min(5, g1_risk)
    h1 = 8 - min(8, h1_risk)

    total = a1 + a2 + a3 + b1 + b2 + b3 + c1 + c2 + d1 + e1 + f1 + f2 + g1 + h1

    # ── 评级 ──
    if total > 65:
        level = 'A'
    elif total > 45:
        level = 'B'
    elif total > 25:
        level = 'C'
    else:
        level = 'D'

    # ── 备注（真实信号驱动） ──
    note_parts = []
    if inv:
        note_parts.append('立案调查中' if any(months_ago(x['date'], 12) for x in inv) else '有立案历史')
    if adverse:
        note_parts.append('无法表示/否定意见')
    elif qualified:
        note_parts.append('保留意见')
    if pen:
        note_parts.append('近一年行政处罚' if any(months_ago(x['date'], 12) for x in pen) else '有处罚历史')
    if h1_signals:
        note_parts.append('实控人' + '+'.join(h1_signals))
    if f2_signals:
        note_parts.append('纾困动作:' + '/'.join(f2_signals))
    if not note_parts:
        pool = {
            'A': ['保壳能力较强，退市概率低', '基本面有支撑，短期退市风险低'],
            'B': ['保壳有一定希望，关注重组进展', '中等风险，存在退市隐患但有缓冲'],
            'C': ['各项风险指标偏高，保壳难度较大', '经营恢复不确定性高，需重组支撑'],
            'D': ['极高退市风险，多项指标触发退市预警', '财务/治理双重压力，保壳可能性极低'],
        }
        code_num = int(code)
        note_parts.append(pool[level][(code_num * 7) % 2])
    note = '；'.join(note_parts[:4])

    if is_b:
        note += '（B股）'
    if 0 < price < 1.5:
        note += '；面值退市警戒'
    if deducted is not None and deducted > 0:
        note += '；扣非盈利'
    if net_equity is not None and net_equity <= 0:
        note += '；资不抵债'

    prev_close = md.get('prev_close', price)
    return {
        'code': code, 'name': name, 'type': stype, 'board': board,
        'reason': reason,
        'A1': a1, 'A2': a2, 'A3': a3,
        'B1': b1, 'B2': b2, 'B3': b3,
        'C1': c1, 'C2': c2, 'D1': d1, 'E1': e1,
        'F1': f1, 'F2': f2, 'G1': g1, 'H1': h1,
        'total': total, 'level': level, 'note': note,
        'price': price, 'prev_close': prev_close,
        'market_cap_yi': mkt_cap,
        'flags': {
            'investigation': bool(inv),
            'adverse_audit': bool(adverse),
            'qualified_audit': bool(qualified),
            'penalty': bool(pen),
            'warning': bool(warn),
            'freeze': bool(freeze),
            'consume_limit': bool(consume),
            'restructuring': bool(restructuring),
            'asset_sale': bool(asset_sale),
            'debt_waiver': bool(debt_waiver),
            'donation': bool(donation),
        },
        'report_date': REPORT_DATE,
        'delisted': False,
    }


# ── 执行评分 ──
scores = [score_stock(c) for c in codes]
scores.sort(key=lambda x: x['total'], reverse=True)

for i, s in enumerate(scores):
    s['rank'] = i + 1

# ── 统计 ──
stats = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
for s in scores:
    stats[s['level']] += 1

print(f'ST保壳评分系统V1 引擎 | 财务报告期: {REPORT_LABEL} | 公告信号: {flags_meta.get("fetched_at", "无")}')
print(f'Total: {len(scores)} stocks')
print(f'A(>65): {stats["A"]}  B(46-65): {stats["B"]}  C(26-45): {stats["C"]}  D(<=25): {stats["D"]}')
print(f'Score: {scores[-1]["total"]} ~ {scores[0]["total"]}')

# 信号覆盖率
n = len(scores)
for k, label in [('investigation', '立案'), ('adverse_audit', '非标(重)'), ('penalty', '处罚'),
                 ('freeze', '冻结'), ('restructuring', '重整'), ('asset_sale', '资产出售')]:
    cnt = sum(1 for s in scores if s['flags'].get(k))
    print(f'  信号[{label}]: {cnt}/{n}')

print('\nTop 10 (easiest):')
for s in scores[:10]:
    print(f'  {s["rank"]:3d}. {s["name"]:12s}({s["code"]}) {s["total"]:3d}分 '
          f'B1={s["B1"]} B2={s["B2"]} B3={s["B3"]} C1={s["C1"]} C2={s["C2"]} F2={s["F2"]} H1={s["H1"]} | {s["note"][:38]}')

print('\nBottom 10 (hardest):')
for s in scores[-10:]:
    print(f'  {s["rank"]:3d}. {s["name"]:12s}({s["code"]}) {s["total"]:3d}分 '
          f'B1={s["B1"]} B2={s["B2"]} B3={s["B3"]} C1={s["C1"]} C2={s["C2"]} F2={s["F2"]} H1={s["H1"]} | {s["note"][:38]}')

# ── 保存 ──
with open(os.path.join(BASE, 'st_scores.json'), 'w', encoding='utf-8') as f:
    json.dump(scores, f, ensure_ascii=False, indent=1)
print('\n[DONE] st_scores.json')
