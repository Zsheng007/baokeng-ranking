#!/usr/bin/env python3
"""一次性拉取188只ST股票的行情+昨收+市值数据（腾讯财经API）
输出: st_market_data.json（覆盖更新）
"""
import json, urllib.request, time, os, sys

BASE = os.path.dirname(os.path.abspath(__file__))

# 加载ST名单
with open(os.path.join(BASE, 'st_names.json'), encoding='utf-8') as f:
    name_map = json.load(f)

codes_all = list(name_map.keys())
print(f'[1/5] 加载ST名单: {len(codes_all)} 只')

# 构造腾讯API查询前缀
def to_tx_code(code):
    """600053 → sh600053, 000001 → sz000001"""
    return ('sh' if code.startswith(('6','9')) else 'sz') + code

# 分批查询（腾讯API URL长度有限制，每批50只）
batch_size = 40
batches = [codes_all[i:i+batch_size] for i in range(0, len(codes_all), batch_size)]
print(f'[2/5] 分 {len(batches)} 批查询腾讯财经API...')

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
        resp = urllib.request.urlopen(req, timeout=15)
        text = resp.read().decode('gbk', errors='replace')

        for line in text.strip().split('\n'):
            if '="' not in line:
                continue
            # 格式: v_sh600053="1~名称~代码~现价~昨收~..."
            data_str = line.split('="')[1].rstrip('";\n')
            fields = data_str.split('~')

            code = fields[2]  # 600053
            name = fields[1]  # *ST九鼎
            price = float(fields[3]) if fields[3] else 0       # 现价
            prev_close = float(fields[4]) if fields[4] else 0   # 昨收
            total_mv = float(fields[45]) if len(fields) > 45 and fields[45] else 0  # 总市值(亿)

            market_data[code] = {
                'name': name,
                'price': price,
                'prev_close': prev_close,
                'market_cap_yi': round(total_mv, 2),
            }

        print(f'  批次 {bi+1}/{len(batches)}: {len(batch)} 只完成')
        time.sleep(0.2)

    except Exception as e:
        failed_batches += 1
        print(f'  批次 {bi+1}/{len(batches)} 失败: {e}')

print(f'[3/5] 获取到 {len(market_data)} 只数据（失败批次: {failed_batches}）')

# 保存到 st_market_data.json
mkt_file = os.path.join(BASE, 'st_market_data.json')
with open(mkt_file, 'w', encoding='utf-8') as f:
    json.dump(market_data, f, ensure_ascii=False, indent=1)
print(f'[4/5] 已写入 {mkt_file}')

# 重新运行 build_baokeng.py 生成评分
print(f'[5/5] 重新评分...')
ret = os.system(f'"{sys.executable}" "{os.path.join(BASE, "build_baokeng.py")}"')
if ret == 0:
    print('  评分完成')
else:
    print('  评分失败，请手动运行 build_baokeng.py')

# 重新生成 HTML
gen = os.path.join(BASE, 'generate_html.py')
if os.path.exists(gen):
    ret2 = os.system(f'"{sys.executable}" "{gen}"')
    if ret2 == 0:
        print('  HTML 已重新生成')

# 写一份独立的市场市值JSON（给前端直接加载）
mkt_json = {}
for code, d in market_data.items():
    mkt_json[code] = d.get('market_cap_yi', 0)
with open(os.path.join(BASE, 'market_cap.json'), 'w', encoding='utf-8') as f:
    json.dump(mkt_json, f, ensure_ascii=False, indent=1)
print('  market_cap.json 已更新')

# 预览前5只
print('\n前5只预览:')
for code in list(market_data.keys())[:5]:
    d = market_data[code]
    print(f'  {code} {d["name"]}: 昨收={d["prev_close"]} 现价={d["price"]} 市值={d["market_cap_yi"]}亿')

print('\\n完成!')
