#!/usr/bin/env python3
"""ST保壳评分系统V2 评分引擎 — 十三维100分制，老Z定稿版（2026-08-28）

设计哲学：财务健康度打分 → 退市概率打分（违约模型）
  维度=退市通道，权重=近5年176家退市案例实证贡献度
  股东实力（实控人性质）=调节变量

老Z定稿六处调整（2026-08-28）：
  C1面值 10→6 | B2审计 8→12（与S1并列第一权重）| C2壳价值规则反转（市值越低于壳基准分越高）
  A2改"扣非主营业务收入"口径 | F2重组 8→6 | A3扣非 4→6；总分仍=100

| 维度 | 满分 | 数据源 |
|------|------|--------|
| C1 面值距离      | 6  | 腾讯实时价格 |
| C2 壳价值锚定    | 8  | 腾讯市值（壳基准28亿=大Deal-168壳费中位数） |
| S1 实控人性质    | 12 | 东财F10 ACTUAL_HOLDER（st_controllers.json） |
| S2 质押与控制权  | 6  | AkShare质押比例 + 巨潮冻结公告 |
| A1 净资产充裕度  | 10 | AkShare东方财富 |
| A2 扣非主营收入  | 12 | AkShare东方财富（当前口径=营业总收入，扣非主营管道待接入） |
| A3 扣非盈利      | 6  | AkShare同花顺 |
| D1 现金流质量    | 4  | AkShare东方财富 |
| B1 立案/造假信号 | 10 | 巨潮公告 |
| B2 审计意见      | 12 | 巨潮公告 |
| F2 重组/纾困进度 | 6  | 巨潮公告 |
| F1 经营改善趋势  | 4  | 扣非+营收复合 |
| H1 实控人司法    | 4  | 巨潮公告 |
| 合计             | 100 | |

联动规则：涉造假立案 → S1封顶4分（退市国化/同达教训：国资非免死金牌）
评级（分数越高=保壳越容易）：A(>65) B(46~65) C(26~45) D(≤25)
"""
import json
import os
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE, 'st_names.json'), encoding='utf-8') as f:
    name_map = json.load(f)
with open(os.path.join(BASE, 'st_market_data.json'), encoding='utf-8') as f:
    mkt = json.load(f)
with open(os.path.join(BASE, 'st_financials.json'), encoding='utf-8') as f:
    fin_raw = json.load(f)
fin_data = fin_raw['data']
REPORT_DATE = fin_raw.get('report_date', '')
REPORT_LABEL = f"{REPORT_DATE[:4]}年{int(REPORT_DATE[4:6])}月报" if REPORT_DATE and len(REPORT_DATE) == 8 else '未知报告期'

risk_flags = {}
if os.path.exists(os.path.join(BASE, 'st_risk_flags.json')):
    with open(os.path.join(BASE, 'st_risk_flags.json'), encoding='utf-8') as f:
        risk_flags = json.load(f).get('flags', {})
else:
    print('[WARN] st_risk_flags.json 不存在，B1/B2/F2/H1 走保守降级')

controllers = {}
if os.path.exists(os.path.join(BASE, 'st_controllers.json')):
    with open(os.path.join(BASE, 'st_controllers.json'), encoding='utf-8') as f:
        controllers = json.load(f).get('data', {})
else:
    print('[WARN] st_controllers.json 不存在，S1 走中性降级')

pledges = {}
if os.path.exists(os.path.join(BASE, 'st_pledges.json')):
    with open(os.path.join(BASE, 'st_pledges.json'), encoding='utf-8') as f:
        pledges = json.load(f).get('data', {})
else:
    print('[WARN] st_pledges.json 不存在，S2 走旧质押字段')

trends = {}
if os.path.exists(os.path.join(BASE, 'st_trends.json')):
    with open(os.path.join(BASE, 'st_trends.json'), encoding='utf-8') as f:
        trends = json.load(f).get('data', {})
else:
    print('[WARN] st_trends.json 不存在，F1 走复合代理')

deduct_inc = {}
if os.path.exists(os.path.join(BASE, 'st_deduct_income.json')):
    with open(os.path.join(BASE, 'st_deduct_income.json'), encoding='utf-8') as f:
        deduct_inc = json.load(f).get('data', {})
else:
    print('[WARN] st_deduct_income.json 不存在，A2 用营业总收入口径')

v1_scores = {}
if os.path.exists(os.path.join(BASE, 'st_scores.json')):
    with open(os.path.join(BASE, 'st_scores.json'), encoding='utf-8') as f:
        for r in json.load(f):
            v1_scores[r['code']] = (r.get('total'), r.get('level'), r.get('rank'))

codes = list(name_map.keys())
TODAY = datetime.now()
SHELL_BASE = 28.0  # 壳价值基准（亿）= 大Deal-168 壳费中位数


def months_ago(date_str, n):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d') >= TODAY - timedelta(days=n * 30)
    except Exception:
        return False


def flag_bucket(code, bucket):
    fl = risk_flags.get(code, {}).get(bucket, [])
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


def fin_val(code, field, default=None):
    v = fin_data.get(code, {}).get(field)
    return default if v is None else v


def fraud_involved(code):
    """立案公告标题是否涉造假/欺诈"""
    for x in flag_bucket(code, 'investigation'):
        t = x.get('title', '')
        if any(k in t for k in ('造假', '欺诈', '虚假记载', '误导性陈述', '重大遗漏', '未按规定披露')):
            return True
    return False


def score_stock(code):
    name = name_map[code]
    md = mkt.get(code, {})
    price = md.get('price', 3) or 3
    mkt_cap = md.get('market_cap_yi', 0) or 0
    board = get_board(code)
    is_star = name.startswith('*ST')
    is_bj = board == '北交所'  # 巨潮沪深库覆盖不到 → 降级

    deducted = fin_val(code, 'deducted_profit')
    revenue = fin_val(code, 'revenue')
    net_equity = fin_val(code, 'total_equity')
    operating_cf = fin_val(code, 'operating_cf')
    pledge_ratio = fin_val(code, 'pledge_ratio')
    rev_threshold = 1 if board in ('创业板', '科创板', 'B股') else 3  # 亿

    notes = []

    # ════ C1 面值距离 (0-6) 老Z定稿：10→6，档位重标 ════
    if price >= 5:    c1 = 6
    elif price >= 3:  c1 = 5
    elif price >= 2:  c1 = 4
    elif price >= 1.5: c1 = 2
    elif price >= 1.2: c1 = 1
    else:             c1 = 0
    if price < 1.5:
        notes.append('面值退市警戒')
    if is_bj:
        notes.append('北交所数据降级')

    # ════ C2 壳价值锚定 (0-8) 老Z定稿：规则反转 ════
    # 基准28亿：市值越低→并购成本越低→买壳注资保壳概率越高
    if mkt_cap <= 0:
        c2 = 4  # 数据缺失，中性
    elif mkt_cap <= SHELL_BASE * 0.5:    c2 = 8   # ≤14亿
    elif mkt_cap <= SHELL_BASE * 0.75:   c2 = 6   # ≤21亿
    elif mkt_cap <= SHELL_BASE:          c2 = 4   # ≤28亿
    elif mkt_cap <= SHELL_BASE * 1.5:    c2 = 2   # ≤42亿
    else:                                 c2 = 0
    if mkt_cap > 0 and c2 == 8:
        notes.append('市值≤壳基准5折(并购机会区)')
    # C1联动：已处面值危机（C1≤1）说明市场不认可壳价值 → C2降档
    # 逻辑：壳有人接盘则难跌破面值；已跌破/濒临跌破=并购方观望，便宜≠有人要
    if c1 == 0:
        c2 = min(c2, 2)
        notes.append('面值危机压制壳价值分')
    elif c1 == 1:
        c2 = min(c2, 4)

    # ════ S1 实控人性质与保壳能力 (0-12) 新增 ════
    ctrl = controllers.get(code, {})
    s1 = ctrl.get('s1_base', 3)
    ctrl_cat = ctrl.get('category', '未获取')
    if ctrl_cat in ('央企', '省级国资'):
        notes.append(f"实控人：{ctrl.get('controller','')}（{ctrl_cat}）")
    # 联动规则：涉造假立案 → 封顶4（国资"应退则退"切割避责）
    fraud = fraud_involved(code) if not is_bj else False
    if fraud:
        s1 = min(s1, 4)
        notes.append('涉造假立案→S1封顶4')
    # 注：12分制中基础档封顶10，预留2分为"国资保壳资源佐证"（增持/注资公告），
    # 当前数据管道未覆盖，暂按基础档执行

    # ════ S2 股权质押与控制权 (0-6) 数据源：中登周报 RPT_CSDC_LIST ════
    freeze = flag_bucket(code, 'freeze')
    pl = pledges.get(code)
    if pl is not None:
        pledge_ratio = pl.get('pledge_ratio')  # 无近期记录=0(质押已清零)
    if freeze and not is_bj:
        s2 = 0  # 爆仓/冻结 → 控制权真空
        notes.append('股份冻结')
    elif pledge_ratio is None:
        s2 = 3  # 数据缺失，中性偏保守
    elif pledge_ratio < 20:
        s2 = 6
        if pledge_ratio == 0 and pl is not None:
            notes.append('无质押')
    elif pledge_ratio < 50: s2 = 4
    else:                   s2 = 2
    if pledge_ratio is not None and pledge_ratio >= 50:
        notes.append(f'高质押{pledge_ratio:.0f}%')

    # ════ A1 净资产充裕度 (0-10) ════
    if net_equity is not None:
        e_yi = net_equity / 1e8
        if e_yi > 10:   a1 = 10
        elif e_yi > 5:  a1 = 8
        elif e_yi > 2:  a1 = 6
        elif e_yi > 0:  a1 = 3
        else:           a1 = 0
        if e_yi <= 0:
            notes.append('资不抵债')
    else:
        a1 = 3  # 数据缺失，保守

    # ════ A2 扣非主营业务收入 (0-12) 老Z定稿：扣非主营口径 ════
    # 口径：营业收入 × (1 - 其他/补充收入占比)，主营构成取自东财F10年报期
    # 冲量嫌疑：低毛利项(毛利率0~5%)收入占比≥30% → -3（贸易冲量凑3亿风险）
    di = deduct_inc.get(code) or {}
    if revenue is not None:
        other_ratio = di.get('other_ratio')
        if other_ratio is not None:
            rev_basis = revenue * (1 - other_ratio)  # 扣非主营收入
        else:
            rev_basis = revenue
            notes.append('扣非口径未获取,按营业总收入')
        rev_yi = rev_basis / 1e8
        gap = max(0.0, 1 - rev_yi / rev_threshold) if rev_yi < rev_threshold else 0.0
        if gap == 0:        a2 = 12
        elif gap <= 0.20:   a2 = 9
        elif gap <= 0.40:   a2 = 6
        elif gap <= 0.60:   a2 = 3
        else:               a2 = 0
        # *ST已处触线窗口第一年（扣非为负+营收低于阈值触发*ST）→ 第二年压力降一档
        if is_star and gap > 0:
            a2 = max(0, a2 - 3)
            notes.append(f'营收缺口{gap*100:.0f}%且已戴*ST')
        # 收入真实性：低毛利贸易类占比≥30% → -3
        low_margin = di.get('low_margin_ratio')
        if low_margin is not None and low_margin >= 0.30:
            a2 = max(0, a2 - 3)
            notes.append(f'低毛利收入占{low_margin*100:.0f}%(冲量嫌疑)')
    else:
        a2 = 3  # 数据缺失，保守

    # ════ A3 扣非盈利 (0-6) 老Z定稿：4→6 ════
    if deducted is not None:
        if deducted > 0:
            a3 = 6
            notes.append('扣非盈利')
        elif is_star:
            a3 = 0  # *ST+扣非亏 → 连亏3年+概率高
        else:
            a3 = 3  # 亏损，趋势未知按收窄档
    else:
        a3 = 2

    # ════ D1 现金流质量 (0-4) 降权10→4 ════
    if operating_cf is not None and revenue:
        ratio = operating_cf / revenue
        if ratio > 0.1:   d1 = 4
        elif ratio > 0:   d1 = 2
        else:             d1 = 0
    else:
        d1 = 1

    # ════ B1 立案/造假信号 (0-10) ════
    inv = flag_bucket(code, 'investigation')
    if is_bj:
        b1 = 7   # 巨潮未覆盖，中性降级
    elif fraud:
        b1 = 0
        notes.append('涉造假/欺诈立案')
    elif not inv:
        b1 = 10
    else:
        b1 = 4 if any(months_ago(x['date'], 12) for x in inv) else 7
        notes.append('立案调查中' if b1 == 4 else '有立案历史(已结)')

    # ════ B2 审计意见 (0-12) 老Z定稿：8→12 ════
    adverse = flag_bucket(code, 'audit_adverse')
    qualified = flag_bucket(code, 'audit_qualified')
    emphasis = flag_bucket(code, 'audit_emphasis')
    if is_bj:
        b2 = 6  # 未覆盖，中性降级
    elif adverse:
        b2 = 0
        notes.append('无法表示/否定意见')
    elif qualified:
        b2 = 6
        notes.append('保留意见')
    elif emphasis:
        b2 = 9
        notes.append('带强调事项')
    else:
        b2 = 12  # 巨潮无命中=最近年报无重非标

    # ════ F2 重组/纾困进度 (0-6) 老Z定稿：8→6 ════
    f2 = 0
    restructuring = flag_bucket(code, 'restructuring')
    asset_sale = flag_bucket(code, 'asset_sale')
    debt_waiver = flag_bucket(code, 'debt_waiver')
    donation = flag_bucket(code, 'donation')
    if not is_bj:
        if any(x.get('stage') == 'exec' for x in restructuring):
            f2 = 6
            notes.append('重整执行中')
        elif restructuring:
            f2 = 4
            notes.append('申请/预重整')
        elif asset_sale or debt_waiver or donation:
            f2 = 2
            notes.append('出售资产/债务豁免')

    # ════ F1 经营改善趋势 (0-4) 数据源：F10最新期vs上年同期 ════
    tr = trends.get(code) or {}
    rev_yoy, kc_yoy = tr.get('rev_yoy'), tr.get('kc_yoy')
    if rev_yoy is not None and kc_yoy is not None:
        rev_up, kc_up = rev_yoy > 0, kc_yoy > 0
        if rev_up and kc_up:   f1 = 4
        elif rev_up or kc_up:  f1 = 2
        else:                  f1 = 0
    elif deducted is not None and revenue is not None:
        # 降级：复合代理（扣非为正+营收达标）
        d_pos = deducted > 0
        r_ok = (revenue / 1e8) >= rev_threshold
        if d_pos and r_ok:   f1 = 4
        elif d_pos or r_ok:  f1 = 2
        else:                f1 = 0
    else:
        f1 = 1

    # ════ H1 实控人司法风险 (0-4) 降权8→4 ════
    consume = flag_bucket(code, 'consume_limit')
    ctrl_case = any('实际控制人' in x.get('title', '') or '控股股东' in x.get('title', '')
                    for x in inv)
    if is_bj:
        h1 = 2
    elif freeze or ctrl_case:
        h1 = 0
        if not any('股份冻结' in n for n in notes):
            notes.append('实控人冻结/立案')
    elif consume:
        h1 = 2
        notes.append('限制消费')
    else:
        h1 = 4

    total = c1 + c2 + s1 + s2 + a1 + a2 + a3 + d1 + b1 + b2 + f2 + f1 + h1
    # ── 通道封顶（一票否决）：核心退市通道已触发时，其他维度再好也不得进高评级 ──
    # C1=0 面值危机：交易类通道已实质触发（不可逆），总分封顶C档上沿50
    if c1 == 0:
        total = min(total, 50)
        if '面值退市警戒' not in notes:
            notes.append('面值退市警戒')
    # B2=0 无法表示/否定意见：规范类直接通道触发，总分封顶50
    if b2 == 0:
        total = min(total, 50)
    # B1=0 涉造假立案：重大违法零容忍通道，总分封顶D档上沿30
    if b1 == 0:
        total = min(total, 30)
    # V2评级分界（2026-08-28校准）：V2高分区间整体上移（B2=12/B1=10满分口径），
    # A/B/C分界相应抬高，保持与V1相近的评级金字塔
    if total > 70:
        level = 'A'
    elif total > 50:
        level = 'B'
    elif total > 30:
        level = 'C'
    else:
        level = 'D'

    v1 = v1_scores.get(code, (None, None, None))
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
        'report_date': REPORT_DATE, 'delisted': False,
    }


scores = [score_stock(c) for c in codes]
scores.sort(key=lambda x: x['total'], reverse=True)
for i, r in enumerate(scores, 1):
    r['rank'] = i

payload = {
    'meta': {
        'system': 'ST保壳评分系统V2（老Z定稿2026-08-28，十三维100分制）',
        'philosophy': '退市概率打分：维度=退市通道，权重=5年176家退市案例实证贡献度',
        'dims': 'C1面值6/C2壳价值8(规则反转,基准28亿)/S1实控人12(新增,涉造假封顶4)/'
                'S2质押6(中登周报)/A1净资产10/A2扣非主营收入12(F10主营构成口径)/A3扣非6/'
                'D1现金流4/B1立案造假10/B2审计12/F2重组6/F1趋势4(F10同比)/H1司法4',
        'levels': 'A(>70) B(51-70) C(31-50) D(≤30)，分数越高=保壳越容易；'
                  '联动规则：C1≤1时C2降档(面值危机压制壳价值)；涉造假立案S1封顶4',
        'report_date': REPORT_DATE,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'n': len(scores),
    },
    'data': scores,
}
with open(os.path.join(BASE, 'st_scores_v2.json'), 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=1)

# ── 摘要 ──
from collections import Counter
lv = Counter(r['level'] for r in scores)
print(f'[V2] 完成：{len(scores)}家 → st_scores_v2.json')
print('[V2] 评级分布：', dict(lv))
avg = sum(r['total'] for r in scores) / len(scores)
print(f'[V2] 全市场均分 {avg:.1f}')

soe = [r for r in scores if r['controller_cat'] in ('央企', '省级国资', '市县国资', '国资(未分层)')]
poa = [r for r in scores if r['controller_cat'].startswith('民企')]
if soe:
    print(f'[V2] 国资壳({len(soe)}家)均分 {sum(r["total"] for r in soe)/len(soe):.1f}')
if poa:
    print(f'[V2] 民企壳({len(poa)}家)均分 {sum(r["total"] for r in poa)/len(poa):.1f}')

print('\n[V2] Top 10：')
for r in scores[:10]:
    print(f"  {r['rank']:>3} {r['code']} {r['name']:<10} {r['total']:>3} {r['level']} "
          f"[V1:{r['v1_total']}/{r['v1_level']}] {r['controller_cat']}")
print('\n[V2] Bottom 10：')
for r in scores[-10:]:
    print(f"  {r['rank']:>3} {r['code']} {r['name']:<10} {r['total']:>3} {r['level']} "
          f"[V1:{r['v1_total']}/{r['v1_level']}] {r['note'][:30]}")

mg = next((r for r in scores if r['code'] == '600543'), None)
if mg:
    print(f"\n[V2] 莫高验算：{mg['total']}分/{mg['level']}（V1 {mg['v1_total']}/{mg['v1_level']}）")
    for k in ('C1', 'C2', 'S1', 'S2', 'A1', 'A2', 'A3', 'D1', 'B1', 'B2', 'F2', 'F1', 'H1'):
        print(f'    {k}={mg[k]}', end='')
    print()

# 升降榜
deltas = [(r, (r['total'] - (r['v1_total'] or 0))) for r in scores]
up = sorted(deltas, key=lambda x: -x[1])[:5]
print('\n[V2] 相对V1升幅Top5：')
for r, d in up:
    print(f'  {r["code"]} {r["name"]:<10} {r["v1_total"]}→{r["total"]} (+{d}) {r["controller_cat"]}')
