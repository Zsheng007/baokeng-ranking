#!/usr/bin/env python3
"""保壳风云榜 V618+G 生成器 — 基于真实财务数据 + V618+G 100分制七维评分
评分方向：分数越高=保壳越容易
真实数据驱动版（2026-07-03 重写，取消 code_hash 随机评分）

数据维度与真实来源：
  A1(5)   扣非净利润      → AkShare stock_financial_abstract_ths (同花顺)
  A2(12)  营业收入        → AkShare stock_yjbb_em (东方财富)
  A3(8)   净资产          → AkShare stock_zcfz_em (东方财富)
  B1(7)   违规存量        → 暂用类型推演 (*ST/ST/B股)
  B2(7)   内控审计        → 暂用类型推演
  B3(8)   监管处罚        → 暂用类型推演
  C1(13)  面值/市值       → 腾讯财经API (实时价格)
  D1(11)  现金流质量      → AkShare stock_xjll_em (经营现金流/营收比)
  E1(9)   股权稳定性      → AkShare stock_gpzy_pledge_ratio_em (质押比例)
  F1(10)  持续经营能力    → 扣非+营收双维度综合
  G1(10)  市值偏离度      → 真实归母权益 + 实时市值
"""

import json
import math

# ── 加载数据 ──────────────────────────────────────────────
with open('st_names.json', encoding='utf-8') as f:
    name_map = json.load(f)
with open('st_market_data.json', encoding='utf-8') as f:
    mkt = json.load(f)
with open('st_financials.json', encoding='utf-8') as f:
    fin_data_raw = json.load(f)
fin_data = fin_data_raw['data']

codes = list(name_map.keys())

# ── 板块判定 ──────────────────────────────────────────────
def get_board(code):
    c6 = code[:3]
    if c6 in ('300', '301'):
        return '创业板'
    if c6 == '688':
        return '科创板'
    if c6 == '920':
        return '北交所'
    if c6 == '200':
        return 'B股'
    return '主板'

# ── 辅助函数 ──────────────────────────────────────────────
def safe_fin(key, default=None):
    """安全获取财务数据"""
    v = fin_data.get(key, {})
    if v is None:
        return default
    return v

def fin_val(code, field, default=None):
    """获取某只股票的财务字段值"""
    f = fin_data.get(code, {})
    v = f.get(field)
    if v is None:
        return default
    return v

NONE = object()  # sentinel for "no data"

# ── V618+G 七维真实数据评分引擎 ────────────────────────────
def score_stock(code):
    """返回 {code, name, type, board, A1..G1, total, level, note, ...}"""
    name = name_map[code]
    md = mkt.get(code, {})
    price = md.get('price', 3)
    board = get_board(code)

    is_star = name.startswith('*ST')
    stype = '*ST' if is_star else 'ST'
    is_b = code.startswith('200')

    # ── 默认原因标签 ══════════════════════════════════════
    if is_star:
        if board in ('主板', '北交所'):
            reason = '财务退市风险：净利润/净资产/营收不达标'
        else:
            reason = '财务退市风险：持续亏损触发退市预警'
    else:
        reason = '其他风险警示：内控/违规担保/资金占用/持续经营'
    if is_b:
        reason = 'B股风险警示'

    # ── 财务数据提取 ══════════════════════════════════════
    deducted = fin_val(code, 'deducted_profit')    # 扣非净利润 (同花顺)
    revenue = fin_val(code, 'revenue')               # 营业总收入 (东方财富)
    net_equity = fin_val(code, 'total_equity')       # 归母权益 (东方财富 ZCFZ)
    debt_ratio = fin_val(code, 'debt_ratio')         # 资产负债率
    operating_cf = fin_val(code, 'operating_cf')     # 经营性现金流净额
    pledge_ratio = fin_val(code, 'pledge_ratio')     # 质押比例
    mkt_cap = md.get('market_cap_yi', 0) or 0        # 市值（亿）

    # 板块营收阈值
    rev_threshold = 1 if board in ('创业板', '科创板', 'B股') else 3  # 亿

    # ══════════════════════════════════════════════════════════
    # A1 扣非净利润 (0-5分，风险低=分数低，最后反转)
    # ══════════════════════════════════════════════════════════
    if deducted is not None:
        d_yi = deducted / 100000000  # 转亿
        if d_yi >= 5:          a1_risk = 0
        elif d_yi >= 1:        a1_risk = 1
        elif d_yi >= 0:        a1_risk = 2
        elif d_yi >= -1:       a1_risk = 3
        elif d_yi >= -5:       a1_risk = 4
        else:                  a1_risk = 5
    else:
        a1_risk = 3  # 无数据取中间

    # ══════════════════════════════════════════════════════════
    # A2 营业收入 (0-12分)
    # ══════════════════════════════════════════════════════════
    if revenue is not None:
        r_yi = revenue / 100000000
        ratio = r_yi / rev_threshold
        if ratio >= 5:         a2_risk = 0
        elif ratio >= 3:       a2_risk = 2
        elif ratio >= 2:       a2_risk = 4
        elif ratio >= 1:       a2_risk = 6
        elif ratio >= 0.7:     a2_risk = 8
        elif ratio >= 0.5:     a2_risk = 10
        else:                  a2_risk = 12
    else:
        a2_risk = 7

    # ══════════════════════════════════════════════════════════
    # A3 净资产 (0-8分)
    # ══════════════════════════════════════════════════════════
    if net_equity is not None:
        e_yi = net_equity / 100000000
        if e_yi >= 10:         a3_risk = 0
        elif e_yi >= 5:        a3_risk = 1
        elif e_yi >= 2:        a3_risk = 2
        elif e_yi >= 0:        a3_risk = 3
        elif e_yi >= -1:       a3_risk = 6
        elif e_yi >= -5:       a3_risk = 7
        else:                  a3_risk = 8
    else:
        a3_risk = 4

    # ══════════════════════════════════════════════════════════
    # B1 违规存量 (0-7分) — 暂用类型推演，无随机
    # ══════════════════════════════════════════════════════════
    if is_star:
        b1_risk = 3
    elif is_b:
        b1_risk = 2
    else:
        b1_risk = 4

    # ══════════════════════════════════════════════════════════
    # B2 内控审计 (0-7分) — 暂用类型推演，无随机
    # ══════════════════════════════════════════════════════════
    if is_star:
        b2_risk = 3
    elif is_b:
        b2_risk = 2
    else:
        b2_risk = 5

    # ══════════════════════════════════════════════════════════
    # B3 监管处罚 (0-8分) — 暂用类型推演，无随机
    # ══════════════════════════════════════════════════════════
    if is_star:
        b3_risk = 3
    elif is_b:
        b3_risk = 2
    else:
        b3_risk = 5

    # ══════════════════════════════════════════════════════════
    # C1 面值/市值 (0-13分) — 基于真实股价
    # ══════════════════════════════════════════════════════════
    if price <= 0:
        c1_risk = 9
    elif price < 1:
        c1_risk = 0   # 面值退市危机，极度危险
    elif price < 1.5:
        c1_risk = 2
    elif price < 2:
        c1_risk = 5
    elif price < 3:
        c1_risk = 7
    elif price < 5:
        c1_risk = 10
    elif price < 10:
        c1_risk = 12
    else:
        c1_risk = 13

    # ══════════════════════════════════════════════════════════
    # D1 现金流质量 (0-11分) — 经营现金流/营收 比率
    # ══════════════════════════════════════════════════════════
    if operating_cf is not None and revenue is not None and revenue != 0:
        ocf_ratio = operating_cf / revenue
        if ocf_ratio >= 0.20:    d1_risk = 0
        elif ocf_ratio >= 0.10:  d1_risk = 1
        elif ocf_ratio >= 0.05:  d1_risk = 3
        elif ocf_ratio >= 0:     d1_risk = 5
        elif ocf_ratio >= -0.05: d1_risk = 7
        elif ocf_ratio >= -0.10: d1_risk = 9
        else:                    d1_risk = 11
    else:
        d1_risk = 6  # 无数据取偏保守

    # ══════════════════════════════════════════════════════════
    # E1 股权稳定性 (0-9分) — 基于真实质押比例
    # ══════════════════════════════════════════════════════════
    if pledge_ratio is not None:
        if pledge_ratio < 5:      e1_risk = 0
        elif pledge_ratio < 15:   e1_risk = 2
        elif pledge_ratio < 25:   e1_risk = 4
        elif pledge_ratio < 40:   e1_risk = 6
        else:                     e1_risk = 9
    else:
        e1_risk = 4  # 无数据取中间

    # ══════════════════════════════════════════════════════════
    # F1 持续经营能力 (0-10分) — 扣非+营收 双维度
    # ══════════════════════════════════════════════════════════
    if deducted is not None and revenue is not None:
        d_positive = deducted > 0
        r_ok = (revenue / 100000000) >= rev_threshold
        if d_positive and r_ok:           f1_risk = 0   # 双达标
        elif d_positive or r_ok:          f1_risk = 4   # 单达标
        elif net_equity and net_equity > 0: f1_risk = 6 # 未达标但权益为正
        else:                              f1_risk = 10  # 全面恶化
    else:
        f1_risk = 5

    # ══════════════════════════════════════════════════════════
    # G1 市值偏离度 (0-10分) — 真实归母权益 + 实时市值
    # ══════════════════════════════════════════════════════════
    if net_equity is not None and net_equity > 0 and mkt_cap > 0:
        ne_yi = net_equity / 100000000
        standard_cap = ne_yi + 20  # 壳费20亿
        if mkt_cap <= standard_cap * 0.5:     g1_risk = 0   # 深度低估→风险最低
        elif mkt_cap <= standard_cap * 0.7:   g1_risk = 2
        elif mkt_cap <= standard_cap * 0.9:   g1_risk = 3
        elif mkt_cap <= standard_cap:         g1_risk = 4
        elif mkt_cap <= standard_cap * 1.2:   g1_risk = 6
        elif mkt_cap <= standard_cap * 1.4:   g1_risk = 8
        else:                                 g1_risk = 10  # 市值过高→泡沫风险
    elif net_equity is not None and net_equity <= 0:
        g1_risk = 10  # 资不抵债，市值完全虚高
    else:
        g1_risk = 5  # 无数据取中间

    # ══════════════════════════════════════════════════════════
    # 方向反转：从"风险分"转为"保壳能力分"
    # ══════════════════════════════════════════════════════════
    a1 = max(0, min(5,   5 - a1_risk))
    a2 = max(0, min(12, 12 - a2_risk))
    a3 = max(0, min(8,   8 - a3_risk))
    b1 = max(0, min(7,   7 - b1_risk))
    b2 = max(0, min(7,   7 - b2_risk))
    b3 = max(0, min(8,   8 - b3_risk))
    c1 = max(0, min(13, 13 - c1_risk))
    d1 = max(0, min(11, 11 - d1_risk))
    e1 = max(0, min(9,   9 - e1_risk))
    f1 = max(0, min(10, 10 - f1_risk))
    g1 = max(0, min(10, 10 - g1_risk))

    total = a1 + a2 + a3 + b1 + b2 + b3 + c1 + d1 + e1 + f1 + g1

    # ── 评级 ──
    if total > 65:
        level = 'A'
    elif total > 45:
        level = 'B'
    elif total > 25:
        level = 'C'
    else:
        level = 'D'

    # ── 备注 ──
    notes_pool = {
        'A': ['保壳能力较强，退市概率低', '基本面有支撑，短期退市风险低',
              '经营状况改善中，摘帽预期较好', '保壳难度较低，有望通过主业恢复达标'],
        'B': ['保壳有一定希望，关注资产重组进展', '中等风险，存在退市隐患但有一定缓冲',
              '主业恢复缓慢，依靠非经常损益维持', '风险可控，摘帽取决于经营改善进度'],
        'C': ['高风险标的，退市压力较大，密切关注', '各项风险指标偏高，保壳难度较大',
              '营收/净资产存疑，需持续跟踪季报变化', '经营恢复不确定性高，需重大重组支撑'],
        'D': ['极高退市风险，多项指标触发退市预警', '财务/治理双重压力，保壳可能性极低',
              '退市概率高，需关注退市整理期安排', '财务状况持续恶化，摘帽希望渺茫'],
    }

    # 基于代码哈希选一个备注（保留一点多样性）
    code_num = int(code)
    note_idx = ((code_num * 7 + code_num // 1000 * 13) % 100) % 4
    note = notes_pool[level][note_idx]

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
        'C1': c1, 'D1': d1, 'E1': e1, 'F1': f1, 'G1': g1,
        'total': total, 'level': level, 'note': note,
        'price': price,
        'prev_close': prev_close,
        'market_cap_yi': mkt_cap,
        'delisted': False,
    }

# ── 执行评分 ──
scores = [score_stock(c) for c in codes]
scores.sort(key=lambda x: x['total'], reverse=True)

for i, s in enumerate(scores):
    s['rank'] = i + 1

# ── 统计 ──
active = [s for s in scores if not s['delisted']]
stats = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
for s in active:
    stats[s['level']] += 1

print(f'Total: {len(scores)} stocks')
print(f'A(>65): {stats["A"]}  B(46-65): {stats["B"]}  C(26-45): {stats["C"]}  D(<=25): {stats["D"]}')
print(f'Score: {scores[-1]["total"]} ~ {scores[0]["total"]}')

print('\nTop 10 (easiest):')
for s in scores[:10]:
    detail = f'A1={s["A1"]} A2={s["A2"]} A3={s["A3"]} C1={s["C1"]} D1={s["D1"]} E1={s["E1"]} F1={s["F1"]} G1={s["G1"]}'
    print(f'  {s["rank"]:3d}. {s["name"]:12s}({s["code"]:6s}) {s["total"]:3d}分 {detail} | {s["note"][:40]}')

print('\nBottom 10 (hardest):')
for s in scores[-10:]:
    detail = f'A1={s["A1"]} A2={s["A2"]} A3={s["A3"]} C1={s["C1"]} D1={s["D1"]} E1={s["E1"]} F1={s["F1"]} G1={s["G1"]}'
    print(f'  {s["rank"]:3d}. {s["name"]:12s}({s["code"]:6s}) {s["total"]:3d}分 {detail} | {s["note"][:40]}')

# ── 保存 ──
with open('st_scores.json', 'w', encoding='utf-8') as f:
    json.dump(scores, f, ensure_ascii=False, indent=1)
print('\n[DONE] st_scores.json')
