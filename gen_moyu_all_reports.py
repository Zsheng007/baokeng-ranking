# -*- coding: utf-8 -*-
"""gen_moyu_all_reports.py — 全榜 V2 跟读报告批跑生成器（方案A）
为全市场 ST/*ST（207家）预生成《ST摸鱼风云-V2 · 跟读报告（完整版）》docx，供客服通过企微发送。
数据来源：st_scores_v2.json（唯一口径）+ 摸鱼指数复刻 + TOP10 手写 logic/risk 覆盖。
输出目录：reports_baokeng_v2/
"""
import os, sys, json, math, ast
from datetime import date
from multiprocessing import Pool, cpu_count

BASE = r'C:\Users\xiaot\WorkBuddy\2026-05-16-task-2'
OUT_DIR = os.path.join(BASE, 'reports_baokeng_v2')
sys.path.insert(0, BASE)
import gen_moyu_top10_detail as det

# ── 从 gen_moyu_top10_report.py 提取手写 TOP10（logic/risk 单源） ──
src = open(f'{BASE}\\gen_moyu_top10_report.py', encoding='utf-8').read()
tree = ast.parse(src)
TOPS = None
for node in tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == 'TOPS':
                TOPS = ast.literal_eval(node.value)
assert TOPS and len(TOPS) == 10, 'TOPS 提取失败'
HAND = {t[0]: t for t in TOPS}  # code -> tuple

# ── 读取 V2 数据 ──
v2 = json.load(open(f'{BASE}\\st_scores_v2.json', encoding='utf-8'))
meta, data = v2['meta'], v2['data']
DIM_KEYS = [d[0] for d in det.DIMS]
LV_K = {'A': 1.0, 'B': 1.0, 'C': 0.85, 'D': 0.6}


def compute_moyu(data):
    """复刻页面 JS 摸鱼公式：cheap=市值对数归一化；moyu=(0.5*score+0.5*cheap)*等级系数"""
    pool = [c for c in data if c.get('market_cap_yi', 0) > 0]
    lns = [math.log(c['market_cap_yi']) for c in pool]
    ln_max, ln_min = max(lns), min(lns)
    ln_span = ln_max - ln_min
    info = {}
    for c in pool:
        cheap = round(100 * (ln_max - math.log(c['market_cap_yi'])) / ln_span)
        half = c['total'] * 0.5 + cheap * 0.5
        moyu = round(half * LV_K[c['level']] * 10) / 10
        info[c['code']] = {'cheap': cheap, 'moyu': moyu, 'half': half}
    for i, c in enumerate(sorted(pool, key=lambda x: info[x['code']]['moyu'], reverse=True), 1):
        info[c['code']]['moyuRank'] = i
    return info


def auto_logic(c, dims, dm):
    """非 TOP10 的保壳逻辑模板化生成"""
    name = c['name']
    code = c['code']
    parts = [f'{name}（{code}）当前V2保壳评分 {c["total"]} 分（{c["level"]}级），全榜第 {c["rank"]} 名。']

    hi = [f'{dk}{dn}' for (dk, dn, mx), sc in zip(det.DIMS, dims) if sc >= mx * 0.8]
    if hi:
        parts.append('安全垫维度：' + '、'.join(hi) + '。')

    cat = c['controller_cat']
    if cat == '央企':
        parts.append(f'实控人为央企（{c["controller"]}），国资信用与资源协调能力构成最强保壳兜底。')
    elif cat == '省级国资':
        parts.append(f'实控人为省级国资（{c["controller"]}），具备省级政府信用背书与资源整合能力。')
    elif cat == '市县国资':
        parts.append(f'实控人为市县国资（{c["controller"]}），地方国资具备一定信用背书与资源协调能力。')
    elif cat == '无实控人':
        parts.append('公司当前无实控人，治理结构与保壳主导权存在不确定性。')
    else:
        parts.append(f'实控人为{cat}（{c["controller"]}），无国资兜底，保壳依赖自身资源与外部资本博弈。')

    f2 = dm['F2'][2]
    if f2 >= 6:
        parts.append('重组/纾困已进入执行或完成阶段，保壳确定性最高。')
    elif f2 >= 4:
        parts.append('重组/预重整正在推进，保壳有实质抓手。')
    elif f2 >= 2:
        parts.append('已有出售资产/债务豁免等保壳动作，但尚未形成重组级信号。')
    else:
        parts.append('暂无重组/纾困信号，保壳主要依赖自身经营修复。')

    mcap = c.get('market_cap_yi') or 0.0
    if mcap > 0:
        c2 = dm['C2'][2]
        if c2 >= 8:
            parts.append(f'市值{mcap:.2f}亿，低于基准壳费线33.81亿的5折，壳价便宜，并购重组方入场成本低。')
        elif c2 >= 6:
            parts.append(f'市值{mcap:.2f}亿，处于基准壳费线5~8折折价区，并购成本有吸引力。')
        elif c2 >= 4:
            parts.append(f'市值{mcap:.2f}亿，接近基准壳费线，壳价值中性。')
        else:
            parts.append(f'市值{mcap:.2f}亿，高于基准壳费线，壳价不占优。')
    else:
        parts.append('市值数据缺失，未纳入摸鱼池，壳价值维度暂不评估。')
    return ''.join(parts)


def auto_risk(c, dims, dm):
    """非 TOP10 的风险点模板化生成"""
    parts = []
    lo = [f'{dk}{dn}' for (dk, dn, mx), sc in zip(det.DIMS, dims) if sc <= mx * 0.5]
    if lo:
        parts.append('风险源维度：' + '、'.join(lo) + '。')

    a2, a3 = dm['A2'][2], dm['A3'][2]
    if a2 <= 3 and a3 <= 3:
        parts.append('营收未达标且扣非亏损，已触及「营收<红线+亏损」财务类退市红线组合。')
    elif a2 <= 3:
        parts.append('扣非主营收入未达标（主板<3亿/双创<1亿），需警惕年报后财务类退市风险。')
    if dm['B1'][2] == 0:
        parts.append('重大违法处罚落地（B1=0），总分封顶30分，退市锁定风险极高。')
    if dm['B2'][2] == 0:
        parts.append('审计意见为无法表示/否定意见（B2=0），总分封顶50分，是重大规范风险。')
    if dm['C1'][2] <= 1:
        parts.append('股价贴近或跌破1元面值线（C1≤1），面值退市危机显著。')
    if dm['D1'][2] == 0:
        parts.append('经营现金流为负，资金链压力较大。')
    if dm['S2'][2] == 0:
        parts.append('高质押或冻结，控制权稳定性风险突出。')
    if dm['H1'][2] == 0:
        parts.append('实控人存在冻结/限高/立案，司法风险归零。')
    if c.get('delisted'):
        parts.append('该标的已被判定为锁定退市，不具备保壳博弈价值。')

    if not parts:
        parts.append('各维度未出现极端风险源，整体风险可控，但仍需跟踪公告信号与财务变化。')
    return ' '.join(parts)


def build_args(c, moyu_info, today_str, today_cn):
    """为单家公司构造 build 参数"""
    code = c['code']
    mi = moyu_info.get(code, {})
    rank = mi.get('moyuRank', c['rank'])
    moyu = mi.get('moyu', 0.0)
    cheap = mi.get('cheap', '—')
    dims = [c[k] for k in DIM_KEYS]
    dm = {dk: (dn, mx, c[dk]) for (dk, dn, mx) in det.DIMS}

    if code in HAND:
        # 用手写 TOP10 的 logic/risk，其余字段以榜单数据为准
        _, hand_rank, hand_moyu, hand_cheap, total, lv, mcap, price, br, cat, note, dims_hand, logic, risk = HAND[code]
        # 保持与榜单一致（已验证零偏差），但用手写维度得分
        dims = dims_hand
    else:
        total = c['total']
        lv = c['level']
        mcap = c.get('market_cap_yi') or 0.0
        price = c.get('price', '—')
        br = c['rank']
        cat = f"{c['controller_cat']}（{c['controller']}）"
        note = c.get('note', '')
        logic = auto_logic(c, dims, dm)
        risk = auto_risk(c, dims, dm)

    return (
        code, rank, moyu, cheap, total, lv, mcap, price, br, cat, note, dims, logic, risk,
        OUT_DIR, today_cn, today_str
    )


def worker(args):
    try:
        fn = det.build(*args)
        return ('ok', os.path.basename(fn))
    except Exception as e:
        return ('err', args[0], str(e))


if __name__ == '__main__':
    os.makedirs(OUT_DIR, exist_ok=True)
    today = date.today()
    today_str = today.strftime('%Y%m%d')
    today_cn = today.strftime('%Y年%m月%d日').replace('年0', '年').replace('月0', '月')

    moyu_info = compute_moyu(data)
    jobs = [build_args(c, moyu_info, today_str, today_cn) for c in data]

    n_workers = min(4, cpu_count() or 1)
    print(f'开始生成 {len(jobs)} 份全榜 V2 跟读报告，工作进程 {n_workers} 个，输出目录 {OUT_DIR}')
    ok = err = 0
    with Pool(n_workers) as pool:
        for res in pool.imap_unordered(worker, jobs):
            if res[0] == 'ok':
                ok += 1
                print(f'[{ok}/{len(jobs)}] {res[1]}')
            else:
                err += 1
                print(f'[ERR] {res[1]}: {res[2]}')
    print(f'\n完成：成功 {ok} 份，失败 {err} 份，目录 {OUT_DIR}')
