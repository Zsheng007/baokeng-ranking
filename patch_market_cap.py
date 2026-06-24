#!/usr/bin/env python3
"""给 baokeng-rank.html 加市值(前日)列：
   - COS映射加 market_cap_yi 和 market_cap_str
   - renderList() 表格加市值td
   - showReport() info-row 加市值芯片
   - TOP10条目加市值显示
"""
import re

with open('baokeng-rank.html', encoding='utf-8') as f:
    html = f.read()

# 1. COS映射：加 market_cap_yi: r[17], market_cap_str: r[18]
old_cos = '''    A1:r[5], A2:r[6], A3:r[7], B1:r[8], B2:r[9], B3:r[10],
    C1:r[11], D1:r[12], E1:r[13], F1:r[14], delisted:r[15], note:r[16],
    score:s, level:calcLevel(s) }]'''
new_cos = '''    A1:r[5], A2:r[6], A3:r[7], B1:r[8], B2:r[9], B3:r[10],
    C1:r[11], D1:r[12], E1:r[13], F1:r[14], delisted:r[15], note:r[16],
    market_cap_yi:r[17], market_cap_str:r[18],
    score:s, level:calcLevel(s) }]'''
html = html.replace(old_cos, new_cos)
print('COS映射更新:', 'OK' if old_cos not in html else 'FAIL')

# 2. renderList()：在"详情"td前加市值td
old_row = '''      <td><span class="rtag rtag-${{c.level}}">${{c.level}}</span></td>
      <td class="link-style">查看 →</td>'''
new_row = '''      <td><span class="rtag rtag-${{c.level}}">${{c.level}}</span></td>
      <td style="font-weight:500;color:#1a3d2b">${{c.market_cap_str}}</td>
      <td class="link-style">查看 →</td>'''
html = html.replace(old_row, new_row)
print('renderList表格更新:', 'OK' if old_row not in html else 'FAIL')

# 3. showReport() info-row：加市值芯片（备注芯片后加）
old_info = '''        <div class="info-chip"><div class="info-chip-label">备注</div><div class="info-chip-val" style="font-size:11px">${{c.note}}</div></div>
      </div>'''
new_info = '''        <div class="info-chip"><div class="info-chip-label">备注</div><div class="info-chip-val" style="font-size:11px">${{c.note}}</div></div>
        <div class="info-chip"><div class="info-chip-label">总市值(亿)</div><div class="info-chip-val" style="font-weight:600;color:#1a3d2b">${{c.market_cap_str}}</div></div>
      </div>'''
html = html.replace(old_info, new_info)
print('showReport市值芯片更新:', 'OK' if old_info not in html else 'FAIL')

# 4. TOP10条目：在rank-code行加市值显示
# rankItemEasy/Hard 中的 rank-code div 后加市值
old_code = '''      <div class="rank-code">${{c.code}} · ${{c.board}} · ${{c.reason.length>20?c.reason.slice(0,20)+'…':c.reason}}</div>'''
new_code = '''      <div class="rank-code">${{c.code}} · ${{c.board}} · ${{c.reason.length>20?c.reason.slice(0,20)+'…':c.reason}} · 市值:${{c.market_cap_str}}亿</div>'''
if old_code in html:
    html = html.replace(old_code, new_code)
    print('TOP10市值更新: OK')
else:
    print('TOP10市值更新: SKIP (格式可能不同)')

# 5. 全名单表头：已在上一步generate_html.py更新，检查确认
if '市值(亿)' in html:
    print('表头含市值列: OK')
else:
    print('表头含市值列: MISSING')

with open('baokeng-rank.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('Done → baokeng-rank.html')
print('文件大小:', len(html), 'bytes')
