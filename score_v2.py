#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ST保壳评分系统V2 单股评分模块（L3评分头 · 单一实现源）

用途：榜单批量管道（build_baokeng_v2.py）与会员个股深度报告共用同一评分实现，
保证"榜单分数 = 个股报告分数"（同一数据快照 + 同一config_version + 同一代码路径）。

接口：
    from score_v2 import load_context, score_v2
    ctx = load_context()                # 组装数据上下文（读全部JSON，一次即可）
    r = score_v2('600543', ctx)          # 单股评分：返回13维分值/total/level/notes

回归约定：
    1) 单股调用结果必须与 st_scores_v2.json 中该股记录的13维+total+level 完全一致
       （数据快照未更新的前提下）
    2) 权重/档位/闸门/评级改动只改 score_config_v2.json，本文件不含任何评分常数
"""
import json
import os
import re
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))


def load_context(base=BASE, today=None, mkt_override=None, fin_override=None):
    """组装评分数据上下文。批量管道与单股调用共用。

    mkt_override / fin_override: 允许个股报告传入更新的行情/财务
    （传入后分数会与榜单快照有差异，报告中须注明"数据更新后重算"）。
    """
    ctx = {'today': today or datetime.now()}
    with open(os.path.join(base, 'score_config_v2.json'), encoding='utf-8') as f:
        cfg = json.load(f)
    ctx['cfg'] = cfg
    ctx['dims'] = cfg['dims']
    ctx['gates'] = cfg['gates']

    with open(os.path.join(base, 'st_names.json'), encoding='utf-8') as f:
        ctx['name_map'] = json.load(f)

    if mkt_override is not None:
        ctx['mkt'] = mkt_override
    else:
        with open(os.path.join(base, 'st_market_data.json'), encoding='utf-8') as f:
            ctx['mkt'] = json.load(f)

    if fin_override is not None:
        ctx['fin_data'] = fin_override.get('data', fin_override)
        ctx['report_date'] = fin_override.get('report_date', '')
    else:
        with open(os.path.join(base, 'st_financials.json'), encoding='utf-8') as f:
            fin_raw = json.load(f)
        ctx['fin_data'] = fin_raw['data']
        ctx['report_date'] = fin_raw.get('report_date', '')

    def _opt(fname, key, warn):
        p = os.path.join(base, fname)
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                return json.load(f).get(key, {})
        print(f'[WARN] {fname} 不存在，{warn}')
        return {}

    ctx['risk_flags'] = _opt('st_risk_flags.json', 'flags', 'B1/B2/F2/H1 走保守降级')
    ctx['controllers'] = _opt('st_controllers.json', 'data', 'S1 走中性降级')
    ctx['pledges'] = _opt('st_pledges.json', 'data', 'S2 走旧质押字段')
    ctx['trends'] = _opt('st_trends.json', 'data', 'F1 走复合代理')
    ctx['deduct_inc'] = _opt('st_deduct_income.json', 'data', 'A2 用营业总收入口径')

    v1 = {}
    v1p = os.path.join(base, 'st_scores.json')
    if os.path.exists(v1p):
        with open(v1p, encoding='utf-8') as f:
            for r in json.load(f):
                v1[r['code']] = (r.get('total'), r.get('level'), r.get('rank'))
    ctx['v1_scores'] = v1

    # 壳价值基准（亿）：从shell-fee-base单源库动态读取own口径
    try:
        sb = cfg['shell_base']
        with open(sb['json'], encoding='utf-8') as f:
            _cfg = json.load(f).get('benchmark_config', {})
        ctx['shell_base'] = float(_cfg.get('own_mcap_median_yi') or sb['fallback'])
    except Exception:
        ctx['shell_base'] = float(cfg['shell_base']['fallback'])
    return ctx


# ── 工具函数（与批量管道原实现逐行一致，保证零偏差） ──

def months_ago(ctx, date_str, n):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d') >= ctx['today'] - timedelta(days=n * 30)
    except Exception:
        return False


def flag_bucket(ctx, code, bucket):
    fl = ctx['risk_flags'].get(code, {}).get(bucket, [])
    return sorted(fl, key=lambda x: x.get('date', ''), reverse=True)


def get_board(code):
    c3 = code[:3]
    if c3 in ('300', '301'):
        return '创业板'
    if c3 in ('688', '689'):
        return '科创板'
    if c3 == '920':
        return '北交所'
    if c3 == '200':
        return 'B股'
    return '主板'


def fin_val(ctx, code, field, default=None):
    v = ctx['fin_data'].get(code, {}).get(field)
    return default if v is None else v


# 个人主体被立案/处罚（董监高/实控人个人案）：不触发公司B1归零，走H1/S1
PERSON_CASE = re.compile(r'董事长|实控人|实际控制人|控股股东|董秘|监事|总经理|财务总监|当事人|高级管理人员|时任|独立董事')

# 处罚主体为子公司/孙公司：非上市公司本体违法，不触发B1归零（*ST纳川案例）
SUBSIDIARY_CASE = re.compile(r'子公司|分公司|孙公司')


def is_company_case(title):
    return not PERSON_CASE.search(title or '')


def fraud_involved(ctx, code):
    """立案/处罚公告标题是否涉造假/欺诈（元道案例：处罚决定书标题不含'欺诈'，但欺诈发行已实锤）"""
    for bucket in ('investigation', 'penalty'):
        for x in flag_bucket(ctx, code, bucket):
            if not is_company_case(x.get('title', '')):
                continue
            t = x.get('title', '')
            if any(k in t for k in ('造假', '欺诈', '虚假记载', '误导性陈述', '重大遗漏', '未按规定披露')):
                return True
    return False


def score_v2(code, ctx=None):
    """V2十三维单股评分（唯一实现源）。返回与榜单st_scores_v2.json同构的记录dict。"""
    if ctx is None:
        ctx = load_context()
    DIMS = ctx['dims']
    GATES = ctx['gates']
    CFG = ctx['cfg']
    SHELL_BASE = ctx['shell_base']

    name = ctx['name_map'][code]
    md = ctx['mkt'].get(code, {})
    price = md.get('price', 3) or 3
    mkt_cap = md.get('market_cap_yi', 0) or 0
    board = get_board(code)
    is_star = name.startswith('*ST')
    is_bj = board == '北交所'  # 巨潮沪深库覆盖不到 → 降级

    deducted = fin_val(ctx, code, 'deducted_profit')
    revenue = fin_val(ctx, code, 'revenue')
    net_equity = fin_val(ctx, code, 'total_equity')
    operating_cf = fin_val(ctx, code, 'operating_cf')
    pledge_ratio = fin_val(ctx, code, 'pledge_ratio')
    rev_threshold = 1 if board in ('创业板', '科创板', 'B股') else 3  # 亿

    notes = []

    # ════ C1 面值距离（档位表config） ════
    c1 = DIMS['C1']['floor']
    for th, sc in DIMS['C1']['price_brackets']:
        if price >= th:
            c1 = sc
            break
    if price < 1.5:
        notes.append('面值退市警戒')
    if is_bj:
        notes.append('北交所数据降级')

    # ════ C2 壳价值锚定（基准SHELL_BASE，比率档位config） ════
    # 基准(自家市值中位数)：市值越低→并购成本越低→买壳注资保壳概率越高
    if mkt_cap <= 0:
        c2 = DIMS['C2']['missing']  # 数据缺失，中性
    else:
        c2 = DIMS['C2']['floor']
        for r, sc in DIMS['C2']['base_ratio_brackets']:
            if mkt_cap <= SHELL_BASE * r:
                c2 = sc
                break
    if mkt_cap > 0 and c2 == DIMS['C2']['base_ratio_brackets'][0][1]:
        notes.append('市值≤壳基准5折(并购机会区)')
    # C1联动：已处面值危机（C1≤1）说明市场不认可壳价值 → C2降档
    # 逻辑：壳有人接盘则难跌破面值；已跌破/濒临跌破=并购方观望，便宜≠有人要
    for c1_key, cap in DIMS['C2'].get('c1_linkage', {}).items():
        if c1 == int(c1_key):
            if c2 > cap:
                c2 = min(c2, cap)
                notes.append('面值危机压制壳价值分')

    # ════ S1 实控人性质与保壳能力 ════
    ctrl = ctx['controllers'].get(code, {})
    s1 = ctrl.get('s1_base', DIMS['S1']['default'])
    ctrl_cat = ctrl.get('category', '未获取')
    if ctrl_cat in ('央企', '省级国资'):
        notes.append(f"实控人：{ctrl.get('controller','')}（{ctrl_cat}）")
    # 联动规则：涉造假立案 → 封顶（国资"应退则退"切割避责）
    fraud = fraud_involved(ctx, code) if not is_bj else False
    if fraud:
        s1 = min(s1, DIMS['S1']['fraud_cap'])
        notes.append(f"涉造假立案→S1封顶{DIMS['S1']['fraud_cap']}")
    # 注：12分制中基础档封顶10，预留2分为"国资保壳资源佐证"（增持/注资公告），
    # 当前数据管道未覆盖，暂按基础档执行

    # ════ S2 股权质押与控制权 数据源：中登周报 RPT_CSDC_LIST ════
    freeze = flag_bucket(ctx, code, 'freeze')
    pl = ctx['pledges'].get(code)
    if pl is not None:
        pledge_ratio = pl.get('pledge_ratio')  # 无近期记录=0(质押已清零)
    if freeze and not is_bj:
        s2 = DIMS['S2']['freeze']  # 爆仓/冻结 → 控制权真空
        notes.append('股份冻结')
    elif pledge_ratio is None:
        s2 = DIMS['S2']['missing']  # 数据缺失，中性偏保守
    else:
        s2 = DIMS['S2']['floor']
        for th, sc in DIMS['S2']['pledge_brackets']:
            if pledge_ratio < th:
                s2 = sc
                break
        if pledge_ratio == 0 and pl is not None:
            notes.append('无质押')
    if pledge_ratio is not None and pledge_ratio >= 50:
        notes.append(f'高质押{pledge_ratio:.0f}%')

    # ════ A1 净资产充裕度 ════
    if net_equity is not None:
        e_yi = net_equity / 1e8
        a1 = DIMS['A1']['floor']
        for th, sc in DIMS['A1']['nav_yi_brackets']:
            if e_yi > th:
                a1 = sc
                break
        if e_yi <= 0:
            notes.append('资不抵债')
    else:
        a1 = DIMS['A1']['missing']  # 数据缺失，保守

    # ════ A2 扣非主营业务收入（gap档位config） ════
    # 口径：营业收入 × (1 - 其他/补充收入占比)，主营构成取自东财F10年报期
    # 冲量嫌疑：低毛利项(毛利率0~5%)收入占比≥30% → 扣分（贸易冲量凑3亿风险）
    di = ctx['deduct_inc'].get(code) or {}
    if revenue is not None:
        other_ratio = di.get('other_ratio')
        if other_ratio is not None:
            rev_basis = revenue * (1 - other_ratio)  # 扣非主营收入
        else:
            rev_basis = revenue
            notes.append('扣非口径未获取,按营业总收入')
        rev_yi = rev_basis / 1e8
        gap = max(0.0, 1 - rev_yi / rev_threshold) if rev_yi < rev_threshold else 0.0
        a2 = DIMS['A2']['floor']
        for g, sc in DIMS['A2']['gap_brackets']:
            if gap <= g:
                a2 = sc
                break
        # *ST已处触线窗口第一年（扣非为负+营收低于阈值触发*ST）→ 第二年压力降一档
        if is_star and gap > 0:
            a2 = max(0, a2 - DIMS['A2']['star_penalty'])
            notes.append(f'营收缺口{gap*100:.0f}%且已戴*ST')
        # 收入真实性：低毛利贸易类占比≥阈值 → 扣分
        low_margin = di.get('low_margin_ratio')
        if low_margin is not None and low_margin >= DIMS['A2']['low_margin_ratio']:
            a2 = max(0, a2 - DIMS['A2']['low_margin_penalty'])
            notes.append(f'低毛利收入占{low_margin*100:.0f}%（冲量嫌疑）')
    else:
        a2 = DIMS['A2']['missing']  # 数据缺失，保守

    # ════ A3 扣非盈利 ════
    if deducted is not None:
        if deducted > 0:
            a3 = DIMS['A3']['profit']
            notes.append('扣非盈利')
        elif is_star:
            a3 = DIMS['A3']['star_loss']  # *ST+扣非亏 → 连亏3年+概率高
        else:
            a3 = DIMS['A3']['loss']  # 亏损，趋势未知按收窄档
    else:
        a3 = DIMS['A3']['missing']

    # ════ D1 现金流质量 ════
    if operating_cf is not None and revenue:
        ratio = operating_cf / revenue
        d1 = DIMS['D1']['floor']
        for th, sc in DIMS['D1']['ocf_rev_ratio_brackets']:
            if ratio > th:
                d1 = sc
                break
    else:
        d1 = DIMS['D1']['missing']

    # ════ B1 立案/造假信号 ════
    inv_all = flag_bucket(ctx, code, 'investigation')
    pen_all = flag_bucket(ctx, code, 'penalty')
    inv = [x for x in inv_all if is_company_case(x.get('title', ''))]
    pen = [x for x in pen_all if is_company_case(x.get('title', ''))]
    inv_person = [x for x in inv_all if not is_company_case(x.get('title', ''))]
    if is_bj:
        b1 = DIMS['B1']['bj']  # 巨潮未覆盖，中性降级
    elif fraud:
        b1 = DIMS['B1']['fraud']
        notes.append('涉造假/欺诈立案或处罚')
    elif pen:
        # 处罚性质三档（2026-08-30元道案例复盘甄别后细化，避免一般/子公司处罚误触封顶）：
        # ①重大档(fraud=0/封顶30)：公司本体处罚+立案全链条——证监会稽查路径，重大信披违法实锤（元道/泉为/瑞贝卡）
        # ②一般档(inv_old=7)：公司本体单发处罚、无立案——地方证监局信披罚款（ST沈化/ST人福/ST绝味）
        # ③子公司档(inv_old=7)：仅子公司被罚、公司本体无处罚（*ST纳川/*ST启环）
        pen_self = [x for x in pen if not SUBSIDIARY_CASE.search(x.get('title', '') or '')]
        if pen_self and inv:
            b1 = DIMS['B1']['fraud']
            notes.append('行政处罚落地(重大:立案→处罚全链条)')
        elif pen_self:
            b1 = DIMS['B1']['inv_old']
            notes.append('行政处罚落地(一般)')
        else:
            b1 = DIMS['B1']['inv_old']
            notes.append('子公司行政处罚(公司本体无)')
    elif not inv:
        b1 = DIMS['B1']['inv_old'] if inv_person else DIMS['B1']['none']  # 仅有董监高个人立案→按有立案历史低档（莫高案例：董事长个人被罚≠公司违法）
    else:
        b1 = DIMS['B1']['inv_recent'] if any(months_ago(ctx, x['date'], 12) for x in inv) else DIMS['B1']['inv_old']
        notes.append('立案调查中' if b1 == DIMS['B1']['inv_recent'] else '有立案历史(已结)')
    if inv_person:
        notes.append('董监高个人被立案/处罚')
        inv = inv + inv_person  # H1 ctrl_case 判据需要个人案标题

    # ════ B2 审计意见 ════
    adverse = flag_bucket(ctx, code, 'audit_adverse')
    qualified = flag_bucket(ctx, code, 'audit_qualified')
    emphasis = flag_bucket(ctx, code, 'audit_emphasis')
    if is_bj:
        b2 = DIMS['B2']['bj']  # 未覆盖，中性降级
    elif adverse:
        b2 = DIMS['B2']['adverse']
        notes.append('无法表示/否定意见')
    elif qualified:
        b2 = DIMS['B2']['qualified']
        notes.append('保留意见')
    elif emphasis:
        b2 = DIMS['B2']['emphasis']
        notes.append('带强调事项')
    else:
        b2 = DIMS['B2']['clean']  # 巨潮无命中=最近年报无重非标

    # ════ F2 重组/纾困进度 ════
    f2 = DIMS['F2']['none']
    restructuring = flag_bucket(ctx, code, 'restructuring')
    asset_sale = flag_bucket(ctx, code, 'asset_sale')
    debt_waiver = flag_bucket(ctx, code, 'debt_waiver')
    donation = flag_bucket(ctx, code, 'donation')
    if not is_bj:
        if any(x.get('stage') == 'exec' for x in restructuring):
            f2 = DIMS['F2']['exec']
            notes.append('重整执行中')
        elif restructuring:
            f2 = DIMS['F2']['applied']
            notes.append('申请/预重整')
        elif asset_sale or debt_waiver or donation:
            f2 = DIMS['F2']['asset_ops']
            notes.append('出售资产/债务豁免')

    # ════ F1 经营改善趋势 数据源：F10最新期vs上年同期 ════
    tr = ctx['trends'].get(code) or {}
    rev_yoy, kc_yoy = tr.get('rev_yoy'), tr.get('kc_yoy')
    if rev_yoy is not None and kc_yoy is not None:
        rev_up, kc_up = rev_yoy > 0, kc_yoy > 0
        if rev_up and kc_up:
            f1 = DIMS['F1']['both_up']
        elif rev_up or kc_up:
            f1 = DIMS['F1']['one_up']
        else:
            f1 = DIMS['F1']['none_up']
    elif deducted is not None and revenue is not None:
        # 降级：复合代理（扣非为正+营收达标）
        d_pos = deducted > 0
        r_ok = (revenue / 1e8) >= rev_threshold
        if d_pos and r_ok:
            f1 = DIMS['F1']['proxy_both']
        elif d_pos or r_ok:
            f1 = DIMS['F1']['proxy_one']
        else:
            f1 = DIMS['F1']['proxy_none']
    else:
        f1 = DIMS['F1']['missing']

    # ════ H1 实控人司法风险 ════
    consume = flag_bucket(ctx, code, 'consume_limit')
    ctrl_case = any('实际控制人' in x.get('title', '') or '控股股东' in x.get('title', '')
                    or PERSON_CASE.search(x.get('title', '') or '') for x in inv)
    if is_bj:
        h1 = DIMS['H1']['bj']
    elif freeze or ctrl_case:
        h1 = DIMS['H1']['freeze_or_ctrl_case']
        if not any('股份冻结' in n for n in notes):
            notes.append('实控人冻结/立案')
    elif consume:
        h1 = DIMS['H1']['consume_limit']
        notes.append('限制消费')
    else:
        h1 = DIMS['H1']['clean']

    total = c1 + c2 + s1 + s2 + a1 + a2 + a3 + d1 + b1 + b2 + f2 + f1 + h1
    # ── 通道封顶（一票否决，闸门列表config驱动） ──
    dim_vals = {'C1': c1, 'B2': b2, 'B1': b1}
    for g in GATES:
        dim, val = g['when'].split('==')
        if dim_vals.get(dim) == int(val):
            total = min(total, g['cap_total'])
    # V2评级分界（2026-08-28校准，config驱动）
    level = next(r['label'] for r in CFG['rating'] if total > r['min']) if total > CFG['rating'][-1]['min'] else CFG['rating'][-1]['label']

    v1 = ctx['v1_scores'].get(code, (None, None, None))
    if is_bj and '北交所数据降级' not in notes:
        notes.append('北交所数据降级')
    if code.startswith('200'):
        notes.append('（B股）')

    return {
        'code': code, 'name': name, 'type': '*ST' if is_star else 'ST', 'board': board,
        'C1': c1, 'C2': c2, 'S1': s1, 'S2': s2,
        'A1': a1, 'A2': a2, 'A3': a3, 'D1': d1,
        'B1': b1, 'B2': b2, 'F2': f2, 'F1': f1, 'H1': h1,
        'total': total, 'level': level,
        'controller': ctrl.get('controller'),
        'controller_cat': ctrl_cat,
        'price': price, 'market_cap_yi': mkt_cap,
        'v1_total': v1[0], 'v1_level': v1[1], 'v1_rank': v1[2],
        'note': '；'.join(notes[:5]),
        'report_date': ctx['report_date'], 'delisted': False,
    }


if __name__ == '__main__':
    # 单股评分自检：与榜单 st_scores_v2.json 逐维比对，必须零偏差
    ctx = load_context()
    with open(os.path.join(BASE, 'st_scores_v2.json'), encoding='utf-8') as f:
        board_scores = {r['code']: r for r in json.load(f)['data']}
    dims = ['C1', 'C2', 'S1', 'S2', 'A1', 'A2', 'A3', 'D1', 'B1', 'B2', 'F2', 'F1', 'H1']
    import sys
    test_codes = sys.argv[1:] or ['600543', '301139', '000698', '002883', '600079', '603517']
    all_ok = True
    for code in test_codes:
        r = score_v2(code, ctx)
        b = board_scores.get(code)
        if not b:
            print(f'{code} 不在榜单中，跳过')
            continue
        diffs = [k for k in dims + ['total', 'level'] if r.get(k) != b.get(k)]
        ok = not diffs
        all_ok &= ok
        print(f"{code} {r['name']:<8} 单股={r['total']}/{r['level']}  榜单={b['total']}/{b['level']}  "
              f"{'✓ 零偏差' if ok else '✗ 差异字段: ' + ','.join(diffs)}")
    print('\n自检结论：', '全部通过 ✓' if all_ok else '存在偏差，需排查 ✗')
