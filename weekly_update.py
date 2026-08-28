#!/usr/bin/env python3
"""保壳风云榜 每周五自动更新脚本
1. 从东方财富ST板块API获取最新ST/*ST名单
2. 从腾讯财经API获取行情数据
3. 对比新旧名单
4. 重新评分并生成HTML
"""
import json
import os
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))

# ── Step 1: 从东方财富获取最新ST/*ST名单 ─────────────────
print("=" * 60)
print(" 保壳风云榜 · 每周五自动更新")
print(f" 日期: 2026-07-31")
print("=" * 60)
print()

print("[1/6] 从东方财富API获取最新ST/*ST名单...")

# BK0511 = ST板块
all_st = []
for page in range(1, 5):  # 最多4页，每页100只
    url = (
        f"https://push2.eastmoney.com/api/qt/clist/get?"
        f"pn={page}&pz=100&po=1&np=1"
        f"&ut=bd1d9ddb04089700cf9c27f6f7426281"
        f"&fltt=2&invt=2&fid=f12&fs=b:BK0511"
        f"&fields=f12,f14"
    )
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
            'Referer': 'https://quote.eastmoney.com/'
        })
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        items = data.get('data', {}).get('diff', [])
        if not items:
            break
        for item in items:
            code = item['f12']
            name = item['f14']
            all_st.append((code, name))
        total = data.get('data', {}).get('total', 0)
        print(f"  第{page}页: {len(items)}只 (总计{total}只)")
        if page * 100 >= total:
            break
        time.sleep(0.3)
    except Exception as e:
        print(f"  第{page}页获取失败: {e}")
        break

print(f"  共获取 {len(all_st)} 只ST/*ST股票")

# 过滤出真实ST/*ST（名称含ST）
valid_st = [(c, n) for c, n in all_st if 'ST' in n.upper()]
print(f"  有效ST/*ST: {len(valid_st)} 只")

# 读旧名单
old_names_file = os.path.join(BASE, 'st_names.json')
with open(old_names_file, encoding='utf-8') as f:
    old_names = json.load(f)

old_codes = set(old_names.keys())
new_codes = set(c for c, _ in valid_st)

# ── Step 2: 对比新旧名单 ─────────────────
print()
print("[2/6] 对比新旧名单...")
added = new_codes - old_codes
removed = old_codes - new_codes
kept = old_codes & new_codes

print(f"  维持: {len(kept)} 只")
print(f"  新增: {len(added)} 只")
print(f"  移除: {len(removed)} 只")

if added:
    print("\n  🆕 新增ST公司:")
    for c in sorted(added):
        n = dict(valid_st).get(c, '??')
        print(f"    {c} {n}")

if removed:
    print("\n  🔴 移除ST公司（摘帽/退市/合并等）:")
    for c in sorted(removed):
        n = old_names.get(c, '??')
        print(f"    {c} {n}")

# 构建新名单
new_name_map = {}
for code, name in valid_st:
    new_name_map[code] = name

# 保留B股（东方财富API不含B股，手动添加）
# 检查是否有深市B股需要保留
b_codes_map = {}
for code in sorted(new_name_map.keys()):
    if code.startswith(('000', '002')):
        # 检查是否有对应B股
        b_code = '200' + code[3:]
        if b_code in old_names:
            b_codes_map[b_code] = old_names[b_code]

if b_codes_map:
    print(f"\n  📌 保留B股对应: {len(b_codes_map)} 只")
    for bc, bn in b_codes_map.items():
        print(f"    {bc} {bn}")
        new_name_map[bc] = bn

# 保存新名单
new_names_file = os.path.join(BASE, 'st_names.json')
with open(new_names_file, 'w', encoding='utf-8') as f:
    json.dump(new_name_map, f, ensure_ascii=False, indent=1)
print(f"\n  已保存 st_names.json ({len(new_name_map)} 只)")

# ── Step 3: 获取行情数据 ─────────────────
print()
print("[3/6] 从腾讯财经API获取行情数据...")

def to_tx_code(code):
    return ('sh' if code.startswith(('6','9')) else 'sz') + code

codes_all = sorted(new_name_map.keys())
batch_size = 40
batches = [codes_all[i:i+batch_size] for i in range(0, len(codes_all), batch_size)]

market_data = {}
failed_batches = 0

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
            name = fields[1]
            price = float(fields[3]) if fields[3] else 0
            prev_close = float(fields[4]) if fields[4] else 0
            total_mv = float(fields[45]) if len(fields) > 45 and fields[45] else 0

            market_data[code] = {
                'name': name,
                'price': round(price, 2),
                'prev_close': round(prev_close, 2),
                'market_cap_yi': round(total_mv, 2),
            }
            count += 1

        print(f"  批次 {bi+1}/{len(batches)}: {count}/{len(batch)} 只")
        time.sleep(0.2)

    except Exception as e:
        failed_batches += 1
        print(f"  批次 {bi+1}/{len(batches)} 失败: {e}")

# 对获取失败的，尝试逐只获取
all_codes_set = set(codes_all)
got_codes = set(market_data.keys())
missing = sorted(all_codes_set - got_codes)

if missing:
    print(f"\n  逐只获取缺失的 {len(missing)} 只...")
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
                price = float(fields[3]) if fields[3] else 0
                prev_close = float(fields[4]) if fields[4] else 0
                total_mv = float(fields[45]) if len(fields) > 45 and fields[45] else 0
                market_data[code] = {
                    'name': fields[1],
                    'price': round(price, 2),
                    'prev_close': round(prev_close, 2),
                    'market_cap_yi': round(total_mv, 2),
                }
            if i % 20 == 0 and i > 0:
                print(f"    进度: {i}/{len(missing)}")
            time.sleep(0.15)
        except Exception as e:
            pass

got_codes = set(market_data.keys())
still_missing = sorted(all_codes_set - got_codes)
if still_missing:
    print(f"  ⚠️ 仍缺失 {len(still_missing)} 只: {still_missing[:10]}...")

print(f"\n  共获取 {len(market_data)}/{len(codes_all)} 只行情数据")

# 保存行情数据
mkt_file = os.path.join(BASE, 'st_market_data.json')
with open(mkt_file, 'w', encoding='utf-8') as f:
    json.dump(market_data, f, ensure_ascii=False, indent=1)
print(f"  已保存 st_market_data.json")

# ── Step 4: 运行评分 ─────────────────
print()
print("[4/6] 运行 build_baokeng.py 评分...")
ret = os.system(f'"{sys.executable}" "{os.path.join(BASE, "build_baokeng.py")}"')
if ret != 0:
    print("  ❌ 评分失败!")
    sys.exit(1)

# ── Step 5: 生成HTML ─────────────────
print()
print("[5/6] 运行 generate_html.py 生成HTML...")
gen = os.path.join(BASE, 'generate_html.py')
ret2 = os.system(f'"{sys.executable}" "{gen}"')
if ret2 != 0:
    print("  ❌ HTML生成失败!")
    sys.exit(1)

# ── Step 6: 更新 market_cap.json ─────────────────
print()
print("[6/6] 更新 market_cap.json...")
mkt_json = {}
for code, d in market_data.items():
    mkt_json[code] = d.get('market_cap_yi', 0)
with open(os.path.join(BASE, 'market_cap.json'), 'w', encoding='utf-8') as f:
    json.dump(mkt_json, f, ensure_ascii=False, indent=1)

# ── 读取评分统计 ──
scores_file = os.path.join(BASE, 'st_scores.json')
with open(scores_file, encoding='utf-8') as f:
    scores = json.load(f)

active = [s for s in scores if not s['delisted']]
stats = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
for s in active:
    stats[s['level']] += 1

# ── 总结 ──
print()
print("=" * 60)
print(" ✅ 更新完成!")
print(f"   覆盖公司: {len(scores)} 家")
print(f"   行情数据: {len(market_data)}/{len(codes_all)} 成功")
print(f"   A级(>65): {stats['A']}  B级(46-65): {stats['B']}  C级(26-45): {stats['C']}  D级(≤25): {stats['D']}")
print(f"   新增: {len(added)} 只 | 移除: {len(removed)} 只")
print(f"   HTML: {os.path.join(BASE, 'baokeng-rank.html')}")
print("=" * 60)

# ── 生成变更报告 ──
changes = {
    'date': '2026-07-31',
    'total': len(scores),
    'stats': stats,
    'added': sorted(list(added)),
    'removed': sorted(list(removed)),
    'added_names': {c: new_name_map.get(c, '??') for c in added},
    'removed_names': {c: old_names.get(c, '??') for c in removed},
}
with open(os.path.join(BASE, 'weekly_changes.json'), 'w', encoding='utf-8') as f:
    json.dump(changes, f, ensure_ascii=False, indent=2)
print(f"\n  变更报告: weekly_changes.json")
