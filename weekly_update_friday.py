#!/usr/bin/env python3
"""保壳风云榜 每周五更新脚本（按用户指定数据源）
1. 访问深交所/上交所风险警示板页面确认日期
2. 从国证 ST 板块静态页面(webf10.gw.com.cn)获取最新 ST/*ST 名单
   （东方财富 ST 板块 API 当前被封禁，临时改用同花顺/国证 ST 板块成分股页面）
3. 从新浪财经API(hq.sinajs.cn)获取实时价格、昨收
4. 从腾讯财经API(qt.gtimg.cn)获取总市值（亿元）
5. 对比新旧名单，生成变更报告
6. 运行 build_baokeng.py 评分(V1数据字段)
7-10. V2数据管道: fetch_controllers/pledges/trends/deduct_income
11. 运行 build_baokeng_v2.py 评分(V2十三维唯一口径)
12. 运行 generate_html.py 生成 HTML
"""
import json
import os
import re
import sys
import time
import urllib.request
import subprocess
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
TODAY = date.today().isoformat()

GW_ST_URL = 'https://webf10.gw.com.cn/BK/B4/SH994429_B4.html'

# ── 永久剔除名单（东财/国证板块残留的已摘帽标的，腾讯行情证实已不带ST前缀）──
# 600165 宁科生物：2026-08 名单核验轮发现为板块残留，已摘帽
# 600525 长园集团：同上
# 新增残留时在此追加代码即可（每周五自动更新时过滤）
EXCLUDE_CODES = {'600165', '600525'}

# ── 工具函数 ─────────────────────────────────────────────

def log(msg=''):
    print(msg)

# ── Step 1/2: 获取ST/*ST名单 ─────────────────────────────

def fetch_page(url, timeout=20, encoding='utf-8'):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode(encoding, errors='replace')

def fetch_names_from_gwcn():
    """从国证 ST 板块静态页面解析成分股代码和简称。

    页面 https://webf10.gw.com.cn/BK/B4/SH994429_B4.html 为国证 ST 板块
    （覆盖沪深两市 ST/*ST）成分股列表，表格静态可解析。
    返回 [(code, short_name), ...]，short_name 不带 ST 前缀。
    """
    text = fetch_page(GW_ST_URL)
    # 匹配 <td class="w2">600439</td> ... <td class="w3" ...><a>瑞贝卡</a></td>
    pattern = re.compile(
        r'<td class="w2">(\d{6})</td>\s*'
        r'<td class="w3"[^>]*>.*?<a>([^<]+)</a></td>',
        re.S
    )
    items = pattern.findall(text)
    # 去重并保持顺序
    seen = set()
    result = []
    for code, name in items:
        if code not in seen:
            seen.add(code)
            result.append((code, name.strip()))
    return result

def fetch_szse_warn_date():
    """访问深交所风险警示板页面，仅确认更新日期/页面可达"""
    try:
        text = fetch_page('https://www.szse.cn/disclosure/listed/warn/index.html', timeout=10)
        m = text.find('风险警示板列表')
        snippet = text[m:m+200] if m != -1 else text[:200]
        return snippet.replace('\n', ' ').replace('\r', ' ').strip()
    except Exception as e:
        return f'访问失败: {e}'

def fetch_sse_warn_date():
    """访问上交所风险警示板页面，仅确认更新日期/页面可达"""
    try:
        text = fetch_page('https://www.sse.com.cn/assortment/stock/list/riskstock/', timeout=10)
        m = text.find('风险警示板')
        snippet = text[m:m+200] if m != -1 else text[:200]
        return snippet.replace('\n', ' ').replace('\r', ' ').strip()
    except Exception as e:
        return f'访问失败: {e}'

# ── Step 3: 行情数据 ─────────────────────────────────────

def to_sina_code(code):
    if code.startswith('920'):
        return 'bj' + code
    if code.startswith(('6', '9')):
        return 'sh' + code
    return 'sz' + code

def fetch_prices_from_sina(codes):
    """从新浪财经API批量获取价格和昨收，并获取完整证券简称（含 ST 前缀）"""
    market = {}
    sina_codes = [to_sina_code(c) for c in codes]
    batch_size = 200
    batches = [sina_codes[i:i+batch_size] for i in range(0, len(sina_codes), batch_size)]
    for bi, batch in enumerate(batches):
        url = 'http://hq.sinajs.cn/list=' + ','.join(batch)
        try:
            req = urllib.request.Request(url, headers={
                'Referer': 'https://finance.sina.com.cn',
                'User-Agent': 'Mozilla/5.0'
            })
            resp = urllib.request.urlopen(req, timeout=20)
            text = resp.read().decode('gbk', errors='replace')
            for line in text.strip().split('\n'):
                if '="' not in line:
                    continue
                prefix, data = line.split('="', 1)
                data = data.rstrip('";').strip()
                if not data:
                    continue
                fields = data.split(',')
                full = prefix.replace('var hq_str_', '')
                code = full[2:]
                if len(fields) < 4:
                    continue
                market[code] = {
                    'name': fields[0],
                    'price': float(fields[3]) if fields[3] else 0.0,
                    'prev_close': float(fields[2]) if fields[2] else 0.0,
                }
            log(f"  新浪批次 {bi+1}/{len(batches)}: {len(batch)}只")
            time.sleep(0.2)
        except Exception as e:
            log(f"  新浪批次 {bi+1}/{len(batches)} 失败: {e}")
    return market

def fetch_market_cap_from_tencent(codes):
    """从腾讯财经API批量获取总市值（亿元）"""
    caps = {}

    def to_tx_code(code):
        if code.startswith('920'):
            return 'bj' + code
        return ('sh' if code.startswith(('6', '9')) else 'sz') + code

    batch_size = 40
    batches = [codes[i:i+batch_size] for i in range(0, len(codes), batch_size)]
    for bi, batch in enumerate(batches):
        tx_codes = [to_tx_code(c) for c in batch]
        url = 'https://qt.gtimg.cn/q=' + ','.join(tx_codes)
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://gu.qq.com'
            })
            resp = urllib.request.urlopen(req, timeout=20)
            text = resp.read().decode('gbk', errors='replace')
            count = 0
            for line in text.strip().split('\n'):
                if '="' not in line:
                    continue
                data_str = line.split('="')[1].rstrip('";\n')
                fields = data_str.split('~')
                code = fields[2]
                total_mv = float(fields[45]) if len(fields) > 45 and fields[45] else 0
                caps[code] = round(total_mv, 2)
                count += 1
            log(f"  腾讯市值批次 {bi+1}/{len(batches)}: {count}/{len(batch)} 只")
            time.sleep(0.2)
        except Exception as e:
            log(f"  腾讯市值批次 {bi+1}/{len(batches)} 失败: {e}")

    # 对缺失的逐只补抓
    missing = [c for c in codes if c not in caps]
    if missing:
        log(f"\n  逐只补抓缺失的 {len(missing)} 只市值...")
        for i, code in enumerate(missing):
            try:
                tx = to_tx_code(code)
                url = f'https://qt.gtimg.cn/q={tx}'
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Referer': 'https://gu.qq.com'
                })
                resp = urllib.request.urlopen(req, timeout=10)
                text = resp.read().decode('gbk', errors='replace')
                for line in text.strip().split('\n'):
                    if '="' not in line:
                        continue
                    data_str = line.split('="')[1].rstrip('";\n')
                    fields = data_str.split('~')
                    total_mv = float(fields[45]) if len(fields) > 45 and fields[45] else 0
                    caps[code] = round(total_mv, 2)
                if i % 20 == 0 and i > 0:
                    log(f"    市值补抓进度: {i}/{len(missing)}")
                time.sleep(0.15)
            except Exception:
                pass
    return caps

# ── 主流程 ────────────────────────────────────────────────

def load_old_names():
    old_names_file = os.path.join(BASE, 'st_names.json')
    if os.path.exists(old_names_file):
        try:
            with open(old_names_file, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                return data
        except Exception:
            pass
    # 若 st_names.json 已损坏，从当前 baokeng-rank.html 兜底读取
    html_file = os.path.join(BASE, 'baokeng-rank.html')
    if os.path.exists(html_file):
        try:
            import re
            with open(html_file, encoding='utf-8') as f:
                text = f.read()
            m = re.search(r'const RAW = (\[[^;]*\]);', text, re.S)
            if m:
                raw = json.loads(m.group(1))
                return {r[0]: r[1] for r in raw}
        except Exception:
            pass
    return {}

def main():
    log("=" * 60)
    log(" 保壳风云榜 · 每周五自动更新")
    log(f" 日期: {TODAY}")
    log("=" * 60)
    log()

    log("[1/13] 访问深交所/上交所风险警示板页面确认可达性...")
    log(f"  深交所页面片段: {fetch_szse_warn_date()[:120]}")
    log(f"  上交所页面片段: {fetch_sse_warn_date()[:120]}")
    log()

    log("[2/13] 从国证 ST 板块成分股页面获取最新 ST/*ST 名单...")
    log(f"  数据源: {GW_ST_URL}")
    valid_st = fetch_names_from_gwcn()
    log(f"  页面解析: {len(valid_st)} 只成分股")

    # 永久剔除已摘帽的板块残留标的
    dropped = sorted({c for c, _ in valid_st} & EXCLUDE_CODES)
    valid_st = [(c, n) for c, n in valid_st if c not in EXCLUDE_CODES]
    if dropped:
        log(f"  🗑️ 剔除摘帽残留 {len(dropped)} 只: {', '.join(dropped)}")
        log(f"  剔除后: {len(valid_st)} 只")

    if not valid_st:
        log("  ❌ 名单获取为空，终止更新，避免覆盖旧数据!")
        sys.exit(1)

    # 读旧名单（用于对比和继承 B 股）
    old_names = load_old_names()
    old_codes = set(old_names.keys())
    new_codes = set(c for c, _ in valid_st)

    # 保留 B 股（国证 ST 板块页面不含 B 股，手动从旧名单继承）
    b_codes = [c for c in old_codes if c.startswith('200')]
    if b_codes:
        log(f"\n  📌 保留 B 股: {len(b_codes)} 只 ({', '.join(sorted(b_codes))})")
        for c in b_codes:
            if c not in new_codes:
                valid_st.append((c, old_names[c]))
                new_codes.add(c)

    added = new_codes - old_codes
    removed = old_codes - new_codes
    kept = old_codes & new_codes

    log()
    log("[3/13] 对比新旧名单...")
    log(f"  维持: {len(kept)} 只 | 新增: {len(added)} 只 | 移除: {len(removed)} 只")

    if added:
        log("\n  🆕 新增ST公司:")
        for c in sorted(added):
            n = dict(valid_st).get(c, '??')
            log(f"    {c} {n}")
    if removed:
        log("\n  🔴 移除ST公司（摘帽/退市/合并等）:")
        for c in sorted(removed):
            n = old_names.get(c, '??')
            log(f"    {c} {n}")

    # 用新浪返回的完整简称替换页面简称（页面简称不含 ST 前缀）
    codes_all = sorted(new_codes)
    log()
    log("[4/13] 从新浪财经API获取实时价格与完整简称...")
    prices = fetch_prices_from_sina(codes_all)
    log(f"  新浪价格数据: {len(prices)}/{len(codes_all)} 只")

    # 构建代码->名称映射：优先新浪名称，缺失用页面名称/旧名称
    name_map = {}
    for code, page_name in valid_st:
        name_map[code] = prices.get(code, {}).get('name') or old_names.get(code) or page_name

    log()
    log("[5/13] 从腾讯财经API获取总市值（亿元）...")
    caps = fetch_market_cap_from_tencent(codes_all)
    log(f"  市值数据: {len(caps)}/{len(codes_all)} 只")

    # 合并行情数据
    market_data = {}
    for code in codes_all:
        p = prices.get(code, {})
        mv = caps.get(code, 0.0)
        price = p.get('price', 0.0)
        prev_close = p.get('prev_close', 0.0)
        # 如果当前价缺失，用昨收兜底（避免停牌/数据异常导致评分失真）
        if price <= 0 and prev_close > 0:
            price = prev_close
        market_data[code] = {
            'name': name_map.get(code, p.get('name', '')),
            'price': price,
            'prev_close': prev_close,
            'market_cap_yi': mv,
        }

    # 保存新名单
    with open(os.path.join(BASE, 'st_names.json'), 'w', encoding='utf-8') as f:
        json.dump(name_map, f, ensure_ascii=False, indent=1)
    log(f"\n  已保存 st_names.json ({len(name_map)} 只)")

    # 保存行情数据
    with open(os.path.join(BASE, 'st_market_data.json'), 'w', encoding='utf-8') as f:
        json.dump(market_data, f, ensure_ascii=False, indent=1)
    log(f"  已保存 st_market_data.json")

    # 单独保存市值
    mkt_json = {code: d.get('market_cap_yi', 0) for code, d in market_data.items()}
    with open(os.path.join(BASE, 'market_cap.json'), 'w', encoding='utf-8') as f:
        json.dump(mkt_json, f, ensure_ascii=False, indent=1)

    # 运行评分
    log()
    log("[6/13] 运行 build_baokeng.py 评分(V1数据字段)...")
    ret = subprocess.run([sys.executable, os.path.join(BASE, "build_baokeng.py")], cwd=BASE)
    if ret.returncode != 0:
        log("  ❌ 评分失败!")
        sys.exit(1)

    # V2 数据管道（2026-08-28 V2正式版切换后接入：S1实控人/S2质押/F1趋势/A2扣非主营 → V2评分）
    for i, (step_name, script) in enumerate([
        ("S1实控人采集", "fetch_controllers.py"),
        ("S2股权质押采集", "fetch_pledges.py"),
        ("F1财务趋势采集", "fetch_trends.py"),
        ("A2扣非主营口径采集", "fetch_deduct_income.py"),
    ], start=7):
        log()
        log(f"[{i}/13] 运行 {script} {step_name}...")
        r = subprocess.run([sys.executable, os.path.join(BASE, script)], cwd=BASE)
        if r.returncode != 0:
            log(f"  ⚠️ {script} 失败(returncode={r.returncode}), V2相应维度将走降级逻辑")

    log()
    log("[11/13] 运行 build_baokeng_v2.py 评分(V2十三维唯一口径)...")
    retv2 = subprocess.run([sys.executable, os.path.join(BASE, "build_baokeng_v2.py")], cwd=BASE)
    if retv2.returncode != 0:
        log("  ❌ V2评分失败! 页面为V2单口径, 必须修复后再生成HTML")
        sys.exit(1)

    # 生成HTML
    log()
    log("[12/13] 运行 generate_html.py 生成HTML...")
    ret2 = subprocess.run([sys.executable, os.path.join(BASE, "generate_html.py")], cwd=BASE)
    if ret2.returncode != 0:
        log("  ❌ HTML生成失败!")
        sys.exit(1)

    # 读取评分统计（V2口径）
    with open(os.path.join(BASE, 'st_scores_v2.json'), encoding='utf-8') as f:
        v2doc = json.load(f)
    scores = v2doc.get('data') or []

    active = [s for s in scores if not s.get('delisted')]
    stats = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
    for s in active:
        stats[s['level']] += 1

    # 总结
    log()
    log("=" * 60)
    log(" ✅ 更新完成!")
    log(f"   覆盖公司: {len(scores)} 家")
    log(f"   行情数据: {len(market_data)}/{len(codes_all)} 只")
    log(f"   新浪价格: {len(prices)}/{len(codes_all)} 只")
    log(f"   市值数据: {len(caps)}/{len(codes_all)} 只")
    log(f"   V2评级 A级(>70): {stats['A']}  B级(51-70): {stats['B']}  C级(31-50): {stats['C']}  D级(≤30): {stats['D']}")
    log(f"   新增: {len(added)} 只 | 移除: {len(removed)} 只")
    log(f"   HTML: {os.path.join(BASE, 'baokeng-rank.html')} (同步index.html)")
    log("=" * 60)

    # 生成变更报告
    changes = {
        'date': TODAY,
        'total': len(scores),
        'stats': stats,
        'added': sorted(list(added)),
        'removed': sorted(list(removed)),
        'added_names': {c: name_map.get(c, '??') for c in added},
        'removed_names': {c: old_names.get(c, '??') for c in removed},
        'kept': sorted(list(kept)),
        'sources': {
            'list': '国证 ST 板块成分股页面 (webf10.gw.com.cn，覆盖沪深两市 ST/*ST)',
            'price': '新浪财经API (hq.sinajs.cn)',
            'market_cap': '腾讯财经API (qt.gtimg.cn)',
            'note': '东方财富 ST 板块 API 当前被封禁，本次改用国证 ST 板块静态页面解析名单'
        }
    }
    with open(os.path.join(BASE, 'weekly_changes.json'), 'w', encoding='utf-8') as f:
        json.dump(changes, f, ensure_ascii=False, indent=2)
    log(f"\n  变更报告: weekly_changes.json")

if __name__ == '__main__':
    main()
