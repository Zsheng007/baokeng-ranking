#!/usr/bin/env python3
"""Generate baokeng-rank.html from ST保壳评分系统V2 scores (分数越高=保壳越容易)
V2十三维100分制（唯一口径，2026-08-28正式版，灰度对照已取消）
RAW(V1承载数据字段): [code,name,type,board,reason, delisted, note, mkt_cap, mkt_str, prev_close, flags]
V2 RAW: [code,name,type,board, C1,C2,S1,S2,A1,A2,A3,D1,B1,B2,F2,F1,H1(13维), delisted, note, controller, controller_cat, total]
"""

import json
from datetime import date

with open('st_scores.json', encoding='utf-8') as f:
    scores = json.load(f)

with open('st_scores_v2.json', encoding='utf-8') as f:
    v2doc = json.load(f)
v2scores = v2doc.get('data') or []
if not v2scores:
    raise SystemExit('st_scores_v2.json 无数据: V2为唯一口径, 请先运行 build_baokeng_v2.py')
v2map = {s['code']: s for s in v2scores}


def esc(t):
    return (str(t or '')).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ')


# 统计按V2口径
active = [s for s in v2scores if not s.get('delisted')]
stats = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
for s in active:
    stats[s['level']] += 1

# 报告期
rd = (v2map.get(scores[0]['code'], {}).get('report_date') or scores[0].get('report_date', '')) if scores else ''
if len(rd) == 8:
    report_label = f"{rd[:4]}年年报" if rd[4:6] == '12' else f"{rd[:4]}年{int(rd[4:6])}月报"
else:
    report_label = '未知报告期'

today = date.today().isoformat()

# 壳价值基准（亿）：与 build_baokeng_v2.py 同源，读 shell-fee-base 单源库 own_stats 口径
try:
    with open(r'C:\Users\xiaot\.workbuddy\skills\shell-fee-base\shell_transactions.json', encoding='utf-8') as _f:
        _cfg = json.load(_f).get('benchmark_config', {})
    SHELL_BASE_YI = float(_cfg.get('own_mcap_median_yi') or 33.81)
except Exception:
    SHELL_BASE_YI = 33.81
SHELL_BASE_LABEL = f'{SHELL_BASE_YI:.1f}'  # 展示口径

# 信号中文名映射
FLAG_CN = {
    'investigation': '立案调查', 'adverse_audit': '无法表示/否定意见',
    'qualified_audit': '保留意见', 'penalty': '行政处罚',
    'warning': '警示函/监管函', 'freeze': '股份冻结',
    'consume_limit': '限制消费', 'restructuring': '重整',
    'asset_sale': '资产出售', 'debt_waiver': '债务豁免', 'donation': '资产赠与',
}

# RAW 数据字段（V1评分维度已移除，仅承载 reason/flags/市值/昨收等展示数据）
raw_lines = []
for s in scores:
    if s['code'] not in v2map:
        continue
    mkt_cap = s.get('market_cap_yi', 0) or 0
    mkt_str = f'{mkt_cap:.1f}' if mkt_cap else '—'
    prev_close = s.get('prev_close', s.get('price', 0)) or 0
    flags = s.get('flags', {})
    flag_str = ','.join(k for k in FLAG_CN if flags.get(k))
    raw_lines.append(
        f'  ["{esc(s["code"])}","{esc(s["name"])}","{esc(s["type"])}","{esc(s["board"])}","{esc(s["reason"])}",'
        f'{str(s["delisted"]).lower()},'
        f'"{esc(s["note"])}",{mkt_cap},"{mkt_str}",{prev_close},"{esc(flag_str)}"]'
    )
raw_str = '[\n' + ',\n'.join(raw_lines) + '\n]'

# V2 十三维数据（主口径）
v2_lines = []
for s in v2scores:
    v2_lines.append(
        f'  ["{esc(s["code"])}","{esc(s["name"])}","{esc(s["type"])}","{esc(s["board"])}",'
        f'{s["C1"]},{s["C2"]},{s["S1"]},{s["S2"]},{s["A1"]},{s["A2"]},{s["A3"]},'
        f'{s["D1"]},{s["B1"]},{s["B2"]},{s["F2"]},{s["F1"]},{s["H1"]},'
        f'{str(bool(s.get("delisted"))).lower()},'
        f'"{esc(s.get("note", ""))}",'
        f'"{esc(s.get("controller", ""))}",'
        f'"{esc(s.get("controller_cat", ""))}",'
        f'{s.get("total", 0)}]'
    )
v2_str = '[\n' + ',\n'.join(v2_lines) + '\n]' if v2_lines else '[]'

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>保壳风云榜 · A股退市风险评估 · ST保壳评分系统V2</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #f0f7f2; color: #1a2b1f; font-size: 14px; }}

.header {{ background: linear-gradient(135deg, #1a3d2b 0%, #0f2519 100%); color: #fff; padding: 22px 24px 16px; border-bottom: 2px solid #2d6e47; }}
.header-inner {{ max-width: 1200px; margin: 0 auto; }}
.header h1 {{ font-size: 24px; font-weight: 600; letter-spacing: 2px; display: flex; align-items: center; gap: 10px; }}
.header p {{ font-size: 13px; color: #7dbf96; margin-top: 4px; }}
.header-meta {{ display: flex; gap: 12px; margin-top: 12px; flex-wrap: wrap; }}
.header-meta span {{ font-size: 12px; background: rgba(255,255,255,0.1); padding: 3px 10px; border-radius: 20px; color: #a8d8b8; border: 0.5px solid rgba(255,255,255,0.15); }}

.container {{ max-width: 1200px; margin: 0 auto; padding: 20px 16px; }}

.score-legend {{ background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; padding: 16px 20px; margin-bottom: 20px; }}
.score-legend h3 {{ font-size: 14px; font-weight: 600; color: #1a3d2b; margin-bottom: 8px; }}
.score-legend-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }}
.slg-item {{ font-size: 11px; padding: 8px; background: #f4fbf6; border-radius: 8px; text-align: center; }}
.slg-dim {{ font-weight: 600; color: #1a5e35; }}
.slg-weight {{ color: #999; font-size: 10px; }}
.slg-real {{ color: #1a6b3a; }}

.stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
.stat-card {{ background: #fff; border-radius: 12px; padding: 16px 12px; border: 0.5px solid #c8e6d0; text-align: center; }}
.stat-num {{ font-size: 32px; font-weight: 700; margin-bottom: 4px; }}
.stat-label {{ font-size: 11px; color: #6b8a75; }}
.stat-card.lv-D .stat-num {{ color: #c0392b; }}
.stat-card.lv-C .stat-num {{ color: #d35400; }}
.stat-card.lv-B .stat-num {{ color: #1a6b3a; }}
.stat-card.lv-A .stat-num {{ color: #27ae60; }}

.tabs {{ display: flex; background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; margin-bottom: 20px; overflow: hidden; }}
.tab {{ flex: 1; padding: 12px 8px; text-align: center; font-size: 13px; cursor: pointer; border: none; background: transparent; color: #5a7a64; font-weight: 500; border-bottom: 2px solid transparent; transition: all 0.2s; }}
.tab.active {{ color: #1a5e35; border-bottom-color: #27ae60; background: #edf7f1; }}
.tab:hover:not(.active) {{ background: #f4fbf6; }}

.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

.rank-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }}
.rank-panel {{ background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; overflow: hidden; }}
.rank-header-easy {{ padding: 14px 16px; border-bottom: 0.5px solid #c8e6d0; background: #edf7f1; }}
.rank-header-hard {{ padding: 14px 16px; border-bottom: 0.5px solid #fad5d0; background: #fdf3f1; }}
.rank-header-moyu {{ padding: 14px 16px; border-bottom: 0.5px solid #f5dcb0; background: #fdf6e9; }}
.rank-panel-title {{ font-size: 14px; font-weight: 600; }}
.rank-panel-sub {{ font-size: 12px; color: #888; margin-top: 2px; }}

.rank-item {{ display: flex; align-items: center; padding: 9px 14px; border-bottom: 0.5px solid #f2f9f4; cursor: pointer; transition: background 0.15s; }}
.rank-item:last-child {{ border-bottom: none; }}
.rank-item:hover {{ background: #f4fbf6; }}
.rank-num {{ width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700; margin-right: 10px; flex-shrink: 0; }}
.rank-num.gold {{ background: #1a5e35; color: #fff; }}
.rank-num.silver {{ background: #2e7d52; color: #fff; }}
.rank-num.bronze {{ background: #3e9468; color: #fff; }}
.rank-num.other {{ background: #e8f5ec; color: #4a7a60; }}
.rank-info {{ flex: 1; min-width: 0; }}
.rank-name {{ font-weight: 500; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.rank-code {{ font-size: 11px; color: #999; margin-top: 1px; }}
.rank-score-col {{ display: flex; flex-direction: column; align-items: flex-end; gap: 3px; }}
.mini-bar-wrap {{ width: 60px; height: 5px; background: #eee; border-radius: 3px; }}
.mini-bar {{ height: 5px; border-radius: 3px; }}
.score-val {{ font-size: 13px; font-weight: 700; }}

.rtag {{ font-size: 10px; padding: 1px 6px; border-radius: 8px; margin-left: 5px; flex-shrink: 0; }}
.rtag-A {{ background: #d5f5e3; color: #1a6b3a; }}
.rtag-B {{ background: #d6eaf8; color: #1a5276; }}
.rtag-C {{ background: #fde8d8; color: #a04000; }}
.rtag-D {{ background: #fadbd8; color: #922b21; }}

/* 首页 TOP10 四列表格：名称/代码/市值/评分 */
.top-table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
.top-table th {{ text-align: left; padding: 7px 10px; font-size: 11px; color: #8aa396; background: #fafcfb; border-bottom: 1px solid #e3f0e8; font-weight: 600; }}
.top-table td {{ padding: 8px 10px; border-bottom: 0.5px solid #f2f9f4; }}
.top-table tbody tr:last-child td {{ border-bottom: none; }}
.top-table tbody tr {{ cursor: pointer; transition: background 0.15s; }}
.top-table tbody tr:hover {{ background: #f4fbf6; }}
.t-rank {{ width: 36px; color: #7aa088; font-weight: 700; }}
.t-name {{ font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 110px; }}
.t-code {{ color: #999; font-size: 11.5px; }}
.t-cap {{ font-weight: 500; color: #1a3d2b; }}
.t-score {{ font-weight: 700; text-align: right; }}

/* 会员专享弹窗 + 专家报告 */
.modal-mask {{ position: fixed; inset: 0; background: rgba(12,26,16,0.55); display: none; align-items: center; justify-content: center; z-index: 999; padding: 20px; }}
.modal-mask.show {{ display: flex; }}
.modal {{ background: #fff; border-radius: 14px; max-width: 640px; width: 100%; max-height: 86vh; overflow-y: auto; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }}
.modal-head {{ padding: 15px 20px; border-bottom: 0.5px solid #e3f0e8; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; background: #fff; z-index: 2; }}
.modal-title {{ font-size: 15px; font-weight: 700; }}
.modal-close {{ border: none; background: #eef7f1; color: #1a5e35; width: 28px; height: 28px; border-radius: 50%; cursor: pointer; font-size: 13px; }}
.modal-close:hover {{ background: #d5edde; }}
.modal-body {{ padding: 18px 20px; }}
.expert-btn {{ display: block; width: 100%; margin-top: 14px; padding: 12px; border: none; border-radius: 10px; background: linear-gradient(135deg,#1a5e35,#2e7d52); color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; letter-spacing: 0.5px; }}
.expert-btn:hover {{ filter: brightness(1.1); }}
.moyu-btn {{ display: block; width: 100%; margin-top: 10px; padding: 12px; border: none; border-radius: 10px; background: linear-gradient(135deg,#8e6a1f,#b9770e); color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; letter-spacing: 0.5px; }}
.moyu-btn:hover {{ filter: brightness(1.12); }}
.mr-calc {{ width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 12.5px; }}
.mr-calc td {{ padding: 7px 10px; border: 0.5px solid #f0dfb8; }}
.mr-calc td:first-child {{ color: #666; width: 38%; background: #fdf9ef; }}
.mr-calc td:last-child {{ font-weight: 700; color: #6b4e00; }}
.mem-input {{ width: 100%; box-sizing: border-box; padding: 10px 12px; border: 1px solid #c8e6d0; border-radius: 8px; font-size: 13px; margin: 6px 0; outline: none; }}
.mem-input:focus {{ border-color: #1a5e35; }}
.mem-btn {{ width: 100%; padding: 11px; border: none; border-radius: 8px; background: #1a5e35; color: #fff; font-weight: 600; cursor: pointer; margin-top: 10px; font-size: 13.5px; }}
.mem-btn:hover {{ background: #2e7d52; }}
.mem-locked {{ text-align: center; padding: 22px 8px; }}
.er-sec {{ margin-top: 14px; }}
.er-sec-t {{ font-size: 13px; font-weight: 700; color: #1a5e35; margin-bottom: 5px; }}
.er-sec-b {{ font-size: 12.8px; line-height: 1.75; color: #33473b; }}
.er-member-tip {{ margin-top: 16px; padding: 9px 12px; background: #edf7f1; border-radius: 8px; font-size: 11.5px; color: #1a6b3a; }}
.er-disclaim {{ margin-top: 12px; font-size: 11px; color: #aaa; line-height: 1.6; border-top: 0.5px dashed #dceee3; padding-top: 10px; }}
.pdf-btn {{ display: block; width: 100%; margin-top: 14px; padding: 12px; border: none; border-radius: 10px; background: linear-gradient(135deg,#8e6a1f,#b9770e); color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; letter-spacing: 0.5px; }}
.pdf-btn:hover {{ filter: brightness(1.12); }}
.pdf-btn:disabled {{ filter: grayscale(0.5); cursor: wait; }}

/* ===== 正式版PDF报告（A4 794px，html2pdf导出） ===== */
.fr {{ width: 794px; background: #fff; color: #1f2d26; font-family: 'Noto Sans SC','Microsoft YaHei','PingFang SC',sans-serif; }}
.fr-pad {{ padding: 0 48px; }}
.fr-band {{ height: 64px; background: linear-gradient(135deg,#1a5e35,#2e7d52); color: #fff; display: flex; justify-content: space-between; align-items: center; padding: 0 48px; }}
.fr-band-l {{ font-size: 17px; font-weight: 800; letter-spacing: 1px; }}
.fr-band-r {{ font-size: 11px; opacity: 0.92; text-align: right; line-height: 1.5; }}
.fr-title {{ margin-top: 30px; font-size: 24px; font-weight: 800; color: #14331f; text-align: center; line-height: 1.4; }}
.fr-subtitle {{ margin-top: 8px; text-align: center; font-size: 12px; color: #6b7f74; letter-spacing: 2px; }}
.fr-meta {{ margin-top: 22px; border: 1px solid #c8e6d0; border-radius: 8px; overflow: hidden; }}
.fr-meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; }}
.fr-mcell {{ display: flex; border-bottom: 1px solid #e3f2e8; border-right: 1px solid #e3f2e8; }}
.fr-mcell:nth-child(2n) {{ border-right: none; }}
.fr-mcell:nth-last-child(1), .fr-mcell:nth-last-child(2):nth-child(2n-1) {{ border-bottom: none; }}
.fr-mk {{ width: 108px; flex-shrink: 0; background: #edf7f1; color: #1a6b3a; font-size: 11.5px; font-weight: 600; padding: 8px 10px; }}
.fr-mv {{ font-size: 11.5px; color: #26352c; padding: 8px 10px; line-height: 1.5; }}
.fr-sec {{ margin-top: 22px; page-break-inside: avoid; break-inside: avoid; }}
.fr-sec-t {{ font-size: 14.5px; font-weight: 800; color: #1a5e35; padding-left: 10px; border-left: 4px solid #2e7d52; margin-bottom: 9px; }}
.fr-sec-b {{ font-size: 12px; line-height: 1.9; color: #33473b; text-align: justify; }}
.fr-table {{ width: 100%; border-collapse: collapse; margin-top: 4px; }}
.fr-table th {{ background: #1a5e35; color: #fff; font-size: 11.5px; padding: 7px 9px; text-align: left; font-weight: 600; }}
.fr-table td {{ font-size: 11.5px; padding: 6.5px 9px; border-bottom: 1px solid #e3f2e8; color: #26352c; }}
.fr-table tr {{ page-break-inside: avoid; break-inside: avoid; }}
.fr-table tr:nth-child(2n) td {{ background: #f6fbf8; }}
.fr-chip {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10.5px; font-weight: 600; margin-right: 5px; }}
.fr-foot {{ margin-top: 30px; margin-bottom: 26px; padding-top: 12px; border-top: 1px solid #c8e6d0; font-size: 10px; color: #8aa294; line-height: 1.7; text-align: center; }}
.fr-disclaim {{ margin-top: 18px; background: #f6fbf8; border: 1px dashed #c8e6d0; border-radius: 8px; padding: 12px 14px; font-size: 10.5px; color: #6b7f74; line-height: 1.8; }}

.search-box {{ background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; padding: 20px; }}
.search-row {{ display: flex; gap: 10px; margin-bottom: 16px; }}
.search-input {{ flex: 1; padding: 10px 14px; border: 0.5px solid #a8d8b8; border-radius: 8px; font-size: 14px; outline: none; background: #f8fcf9; }}
.search-input:focus {{ border-color: #27ae60; box-shadow: 0 0 0 2px rgba(39,174,96,0.15); }}
.search-btn {{ padding: 10px 22px; background: #1a5e35; color: #fff; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; }}
.search-btn:hover {{ background: #1e7a44; }}

.report-card {{ border: 0.5px solid #c8e6d0; border-radius: 12px; padding: 20px; }}
.report-top {{ display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 16px; padding-bottom: 16px; border-bottom: 0.5px solid #e8f5ec; }}
.report-name {{ font-size: 20px; font-weight: 700; }}
.report-sub {{ font-size: 13px; color: #888; margin-top: 3px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }}
.score-big {{ font-size: 38px; font-weight: 700; line-height: 1; }}
.score-label {{ font-size: 11px; color: #888; text-align: right; margin-top: 4px; }}

.info-row {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 16px; }}
.info-chip {{ background: #f4fbf6; border-radius: 8px; padding: 10px 12px; border: 0.5px solid #c8e6d0; }}
.info-chip-label {{ font-size: 11px; color: #7a9a82; margin-bottom: 3px; }}
.info-chip-val {{ font-size: 13px; font-weight: 500; }}

.signal-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
.sig-tag {{ font-size: 11px; padding: 4px 10px; border-radius: 12px; font-weight: 500; }}
.sig-risk {{ background: #fadbd8; color: #922b21; border: 0.5px solid #e6b0aa; }}
.sig-audit {{ background: #fde8d8; color: #a04000; border: 0.5px solid #f5c6a0; }}
.sig-owner {{ background: #e8daef; color: #6c3483; border: 0.5px solid #d2b4de; }}
.sig-rescue {{ background: #d5f5e3; color: #1a6b3a; border: 0.5px solid #a9dfbf; }}
.sig-none {{ background: #f4f4f4; color: #999; border: 0.5px solid #ddd; }}

.factors-section {{ margin-bottom: 14px; }}
.factors-title {{ font-size: 12px; color: #5a7a64; font-weight: 500; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 0.5px solid #e8f5ec; }}
.factor-row {{ display: flex; align-items: center; gap: 10px; padding: 5px 0; }}
.factor-label {{ width: 150px; font-size: 12px; color: #555; flex-shrink: 0; }}
.factor-bar-wrap {{ flex: 1; height: 6px; background: #e8f5ec; border-radius: 3px; }}
.factor-bar {{ height: 6px; border-radius: 3px; transition: width 0.4s; }}
.factor-score {{ width: 36px; text-align: right; font-size: 12px; font-weight: 600; }}

.conclusion-box {{ padding: 12px 14px; border-radius: 8px; margin-top: 12px; }}
.conclusion-box.A {{ background: #d5f5e3; border-left: 3px solid #27ae60; }}
.conclusion-box.B {{ background: #d6eaf8; border-left: 3px solid #2980b9; }}
.conclusion-box.C {{ background: #fde8d8; border-left: 3px solid #e67e22; }}
.conclusion-box.D {{ background: #fadbd8; border-left: 3px solid #c0392b; }}
.conclusion-title {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
.conclusion-text {{ font-size: 12px; line-height: 1.7; color: #444; }}

.table-wrap {{ overflow-x: auto; background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; }}
table {{ width: 100%; border-collapse: collapse; }}
thead th {{ background: #1a5e35; color: #fff; padding: 10px 12px; font-size: 12px; font-weight: 500; text-align: left; white-space: nowrap; }}
thead th[data-key] {{ cursor: pointer; user-select: none; transition: background 0.15s; }}
thead th[data-key]:hover {{ background: #1e7a44; }}
thead th.sorted-asc::after {{ content: ' ▲'; font-size: 10px; }}
thead th.sorted-desc::after {{ content: ' ▼'; font-size: 10px; }}
tbody tr {{ border-bottom: 0.5px solid #f0f9f3; cursor: pointer; transition: background 0.15s; }}
tbody tr:last-child {{ border-bottom: none; }}
tbody tr:hover {{ background: #f4fbf6; }}
tbody td {{ padding: 9px 12px; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.link-style {{ color: #1a5e35; cursor: pointer; }}
.sig-dot {{ display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 3px; vertical-align: middle; }}
.sig-dot.risk {{ background: #c0392b; }}
.sig-dot.rescue {{ background: #27ae60; }}

.filter-row {{ display: flex; gap: 8px; padding: 12px 16px; background: #edf7f1; border-bottom: 0.5px solid #c8e6d0; flex-wrap: wrap; }}
.filter-chip {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; cursor: pointer; border: 1px solid #c8e6d0; background: #fff; color: #5a7a64; transition: all 0.15s; }}
.filter-chip.active {{ background: #1a5e35; color: #fff; border-color: #1a5e35; }}
.filter-chip:hover:not(.active) {{ border-color: #27ae60; }}

.vote-box {{ background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; padding: 20px; }}
.vote-box h3 {{ font-size: 15px; font-weight: 600; color: #1a3d2b; margin-bottom: 6px; }}
.vote-desc {{ font-size: 12px; color: #7a9a82; margin-bottom: 14px; }}
.vote-options {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 14px; }}
.vopt {{ border: 1.5px solid #c8e6d0; border-radius: 10px; padding: 12px 8px; cursor: pointer; transition: all 0.2s; text-align: center; }}
.vopt:hover {{ border-color: #27ae60; background: #f0fbf4; }}
.vopt.selected {{ border-color: #1a5e35; background: #e8f7ee; }}
.vopt-letter {{ font-size: 20px; font-weight: 700; margin-bottom: 2px; }}
.vopt-label {{ font-size: 11px; font-weight: 500; }}
.vopt.A .vopt-letter {{ color: #27ae60; }}
.vopt.B .vopt-letter {{ color: #2980b9; }}
.vopt.C .vopt-letter {{ color: #e67e22; }}
.vopt.D .vopt-letter {{ color: #c0392b; }}

.vote-btn {{ padding: 10px 24px; background: #1a5e35; color: #fff; border: none; border-radius: 8px; font-size: 13px; cursor: pointer; font-weight: 500; }}
.vote-btn:hover {{ background: #1e7a44; }}
.vote-btn:disabled {{ background: #a8c8b0; cursor: not-allowed; }}

.vresult-inline {{ margin-top: 14px; }}
.vbar-row {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }}
.vbar-letter {{ width: 18px; font-size: 13px; font-weight: 700; }}
.vbar-outer {{ flex: 1; height: 18px; background: #e8f5ec; border-radius: 4px; overflow: hidden; }}
.vbar-inner {{ height: 18px; border-radius: 4px; display: flex; align-items: center; padding-left: 6px; font-size: 10px; color: #fff; font-weight: 600; transition: width 0.6s ease; }}
.vbar-count {{ width: 48px; text-align: right; font-size: 11px; color: #666; }}
.vbar-A {{ background: #27ae60; }}
.vbar-B {{ background: #2980b9; }}
.vbar-C {{ background: #e67e22; }}
.vbar-D {{ background: #c0392b; }}
.voted-tip {{ font-size: 11px; color: #999; text-align: center; margin-top: 8px; }}

.vote-rank-intro {{ font-size: 13px; color: #5a7a64; margin-bottom: 16px; text-align: center; }}
.vote-rank-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.vote-rank-card {{ background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; padding: 16px; }}
.vote-rank-card h4 {{ font-size: 13px; font-weight: 600; color: #1a3d2b; margin-bottom: 10px; }}
.vrc-item {{ display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 0.5px solid #f0f9f3; }}
.vrc-item:last-child {{ border-bottom: none; }}
.vrc-rank {{ width: 22px; font-size: 12px; font-weight: 700; color: #5a7a64; flex-shrink: 0; }}
.vrc-name {{ flex: 1; font-size: 12px; cursor: pointer; color: #1a5e35; }}
.vrc-name:hover {{ text-decoration: underline; }}
.vrc-bar {{ width: 80px; height: 14px; background: #e8f5ec; border-radius: 3px; overflow: hidden; }}
.vrc-bar-inner {{ height: 14px; border-radius: 3px; }}
.vrc-count {{ width: 40px; text-align: right; font-size: 11px; color: #888; }}
.vote-empty {{ text-align: center; padding: 40px 20px; color: #aaa; font-size: 13px; }}

.empty-state {{ text-align: center; padding: 40px 20px; color: #aaa; }}

.source-tip {{ font-size: 11px; color: #999; padding: 8px 16px; background: #fafafa; border-radius: 8px; margin-bottom: 16px; text-align: center; }}

.disclaimer {{ background: #fff; border-radius: 12px; border: 1px solid #d5d5d5; padding: 16px 20px; margin-top: 24px; }}
.disclaimer h4 {{ font-size: 13px; font-weight: 600; color: #888; margin-bottom: 8px; }}
.disclaimer p {{ font-size: 11px; color: #aaa; line-height: 1.8; }}

@media(max-width:700px){{
  .rank-grid {{ grid-template-columns: 1fr; }}
  .stats-grid, .score-legend-grid {{ grid-template-columns: repeat(2,1fr); }}
  .info-row {{ grid-template-columns: repeat(2,1fr); }}
  .vote-options {{ grid-template-columns: repeat(2, 1fr); }}
  .vote-rank-grid {{ grid-template-columns: 1fr; }}
  .tabs .tab {{ font-size: 12px; padding: 10px 4px; }}
}}
</style>
</head>
<body>

<div class="header">
<div class="header-inner">
  <h1>🌿 保壳风云榜 <span style="font-size:13px;font-weight:400;opacity:0.7">ST保壳评分系统V2 · 正式版</span></h1>
  <p>A股 ST / *ST 上市公司保壳能力评估 · 十三维退市概率打分 · 实时排名</p>
  <div class="header-meta">
    <span>更新时间：{today}</span>
    <span>覆盖公司：{len(v2scores)} 家</span>
    <span>财务报告期：{report_label}</span>
    <span>评分口径：V2十三维100分制（A&gt;70 / B51-70 / C31-50 / D≤30）</span>
    <span>每周五更新</span>
  </div>
</div>
</div>

<div class="container">

  <div class="score-legend">
    <h3>📐 ST保壳评分系统V2 · 十三维退市概率打分（分数越高=保壳越容易 · ★=真实公告数据 · ◆=外部数据接口）</h3>
    <div class="score-legend-grid">
      <div class="slg-item"><div class="slg-dim">C1 面值距离</div><div class="slg-weight">6分</div></div>
      <div class="slg-item"><div class="slg-dim">C2 壳价值(反转)</div><div class="slg-weight">8分</div></div>
      <div class="slg-item"><div class="slg-dim slg-real">S1 实控人性质◆</div><div class="slg-weight">12分</div></div>
      <div class="slg-item"><div class="slg-dim slg-real">S2 股权质押◆</div><div class="slg-weight">6分</div></div>
      <div class="slg-item"><div class="slg-dim">A1 净资产</div><div class="slg-weight">10分</div></div>
      <div class="slg-item"><div class="slg-dim slg-real">A2 扣非主营收入◆</div><div class="slg-weight">12分</div></div>
      <div class="slg-item"><div class="slg-dim">A3 扣非净利润</div><div class="slg-weight">6分</div></div>
      <div class="slg-item"><div class="slg-dim">D1 现金流质量</div><div class="slg-weight">4分</div></div>
      <div class="slg-item"><div class="slg-dim slg-real">B1 立案/造假★</div><div class="slg-weight">10分</div></div>
      <div class="slg-item"><div class="slg-dim slg-real">B2 审计意见★</div><div class="slg-weight">12分</div></div>
      <div class="slg-item"><div class="slg-dim slg-real">F2 重组/纾困★</div><div class="slg-weight">6分</div></div>
      <div class="slg-item"><div class="slg-dim slg-real">F1 财务趋势◆</div><div class="slg-weight">4分</div></div>
      <div class="slg-item"><div class="slg-dim slg-real">H1 司法风险★</div><div class="slg-weight">4分</div></div>
    </div>
    <p style="font-size:11px;color:#888;margin-top:8px">维度=退市通道，权重=近5年176家退市案例实证贡献度（交易类55%/财务类32%/规范类8%/违法类5-9%）· 联动规则：面值危机(C1≤1)压制壳价值；涉造假立案实控人维度封顶4分 · 通道封顶一票否决：C1=0/B2=0总分封顶50、B1=0封顶30</p>
  </div>

  <div class="stats-grid">
    <div class="stat-card lv-A"><div class="stat-num">{stats["A"]}</div><div class="stat-label">A级 · 保壳能力强（&gt;70分）</div></div>
    <div class="stat-card lv-B"><div class="stat-num">{stats["B"]}</div><div class="stat-label">B级 · 保壳有希望（51-70分）</div></div>
    <div class="stat-card lv-C"><div class="stat-num">{stats["C"]}</div><div class="stat-label">C级 · 保壳难度大（31-50分）</div></div>
    <div class="stat-card lv-D"><div class="stat-num">{stats["D"]}</div><div class="stat-label">D级 · 退市警钟（≤30分）</div></div>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('rank')">📊 风云榜</button>
    <button class="tab" onclick="switchTab('moyu')">🎣 摸鱼榜</button>
    <button class="tab" onclick="switchTab('query')">🔍 查询详情</button>
    <button class="tab" onclick="switchTab('list')">📋 全名单（{len(v2scores)}家）</button>
    <button class="tab" onclick="switchTab('vote')">🗳️ 投票排行</button>
  </div>

  <div id="tab-rank" class="tab-content active">
    <div class="source-tip">📊 数据覆盖 <b>{len(v2scores)}</b> 家 ST/*ST 公司 · V2十三维退市概率打分 · 财务报告期 <b>{report_label}</b> · 公告信号来自巨潮资讯网（近24个月） · 分数越高保壳越容易</div>
    <div class="rank-grid">
      <div class="rank-panel">
        <div class="rank-header-easy">
          <div class="rank-panel-title">🟢 保壳最容易 TOP 10</div>
          <div class="rank-panel-sub">保壳能力分最高 · 退市概率最低</div>
        </div>
        <div id="easyList"></div>
      </div>
      <div class="rank-panel">
        <div class="rank-header-hard">
          <div class="rank-panel-title">🔴 保壳最困难 TOP 10</div>
          <div class="rank-panel-sub">保壳能力分最低 · 退市风险最大</div>
        </div>
        <div id="hardList"></div>
      </div>
      <div class="rank-panel">
        <div class="rank-header-moyu">
        <div class="rank-panel-title">🎣 ST摸鱼榜 TOP 10</div>
        <div class="rank-panel-sub">市值越低 + 保壳分越高 = 综合机会越好 · 点击行查看摸鱼分析报告</div>
        </div>
        <div id="moyuTopList"></div>
      </div>
    </div>
  </div>

  <div id="tab-moyu" class="tab-content">
    <div class="source-tip">🎣 摸鱼指数 = 50%×V2保壳分 + 50%×壳便宜分（市值对数归一化，越便宜分越高）× 等级系数（A/B 1.0 · C 0.85 · D 0.6）· 已剔除锁定退市标的 · 指数越高 = 壳便宜 + 保壳稳 = 摸鱼综合机会越好</div>
    <div class="rank-panel">
      <div class="rank-header-easy" style="background:#fdf6e9;border-bottom:0.5px solid #f5dcb0">
        <div class="rank-panel-title">🎣 ST摸鱼榜 TOP 20</div>
        <div class="rank-panel-sub">摸鱼池全部 ${{MOYU_POOL.length}} 家可出报告 · 点击行查看摸鱼分析报告 · 链接直达 #moyu-代码</div>
      </div>
      <div id="moyuList"></div>
    </div>
    <div class="source-tip" style="margin-top:12px">💡 摸鱼逻辑：壳越便宜，买方并购/借壳成本越低（对标{SHELL_BASE_LABEL}亿基准壳费）；保壳分越高，退市擦肩而过的概率越低。两者兼得 = 低位潜伏的综合机会。D级折扣防止"超便宜但快退市"的飞刀陷阱。</div>
  </div>

  <div id="tab-query" class="tab-content">
    <div class="search-box">
      <div class="search-row">
        <input class="search-input" id="qInput" placeholder="输入证券代码（600053）或公司简称（ST九鼎）…" />
        <button class="search-btn" onclick="doQuery()">查询</button>
      </div>
      <div id="qResult">
        <div class="empty-state">🔍 输入代码或简称开始查询</div>
      </div>
    </div>
  </div>

  <div id="tab-list" class="tab-content">
    <div class="source-tip"><b id="listTotal">{len(v2scores)}</b> 家 · 排序：按保壳能力分（分数越高保壳越容易）· ●红=风险信号 ●绿=纾困信号</div>
    <div class="filter-row">
      <span class="filter-chip active" onclick="setFilter('all',this)">全部</span>
      <span class="filter-chip" onclick="setFilter('ST',this)">ST</span>
      <span class="filter-chip" onclick="setFilter('*ST',this)">*ST</span>
      <span class="filter-chip" onclick="setFilter('A',this)">A级 &gt;70</span>
      <span class="filter-chip" onclick="setFilter('B',this)">B级 51-70</span>
      <span class="filter-chip" onclick="setFilter('C',this)">C级 31-50</span>
      <span class="filter-chip" onclick="setFilter('D',this)">D级 ≤30</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead id="listHead">
          <tr>
            <th style="width:46px" data-key="rank" onclick="sortBy('rank')" title="点击排序">排名</th>
            <th style="width:80px" data-key="code" onclick="sortBy('code')" title="点击排序">代码</th>
            <th style="width:100px" data-key="name" onclick="sortBy('name')" title="点击排序">简称</th>
            <th style="width:55px" data-key="type" onclick="sortBy('type')" title="点击排序">类型</th>
            <th data-key="reason" onclick="sortBy('reason')" title="点击排序">风险原因</th>
            <th style="width:58px" data-key="signal" onclick="sortBy('signal')" title="公告信号数">信号</th>
            <th style="width:60px" data-key="score" onclick="sortBy('score')" title="点击排序">保壳分</th>
            <th style="width:50px" data-key="level" onclick="sortBy('level')" title="点击排序">等级</th>
            <th style="width:75px" data-key="market_cap_yi" onclick="sortBy('market_cap_yi')" title="点击排序">市值(亿)</th>
            <th style="width:55px">详情</th>
          </tr>
        </thead>
        <tbody id="listBody"></tbody>
      </table>
    </div>
  </div>

  <div id="tab-vote" class="tab-content">
    <div class="vote-rank-intro">🗳️ 对每家ST公司的保壳难度投票 · 查看大家怎么看<br><span style="font-size:11px;color:#aaa">在查询页查看公司详情时即可参与投票</span></div>
    <div class="vote-rank-grid">
      <div class="vote-rank-card">
        <h4>🔴 「最难保壳」投票最多的公司</h4>
        <div id="voteHardList"></div>
      </div>
      <div class="vote-rank-card">
        <h4>🟢 「最容易保壳」投票最多的公司</h4>
        <div id="voteEasyList"></div>
      </div>
    </div>
  </div>

  <div class="disclaimer">
    <h4>⚠️ 免责声明</h4>
    <p>1. 本工具仅供学习研究参考，<b>不构成任何投资建议</b>。评分模型基于公开数据和算法推断，可能存在偏差与滞后。</p>
    <p>2. 投资者应自行判断风险，<b>据此操作风险自负</b>。退市涉及复杂的财务、法律及监管因素，本工具无法全面覆盖。</p>
    <p>3. 数据来源：沪深交易所风险警示板公开名单、腾讯财经行情、巨潮资讯网公告、中登周报质押数据、东财F10主营构成/财务趋势/实控人信息。财务维度基于 <b>{report_label}</b>，公告信号窗口为近24个月。评分模型「ST保壳评分系统V2」为独立研究框架，<b>不代表任何机构观点</b>。</p>
    <p>4. 历史评分不代表未来结果，保壳能力评分仅反映基于公开信息的综合评估，不保证准确性。北交所股票公告信号暂未覆盖（走规则推演）。</p>
  </div>

</div>

<script>
// ===================== ST保壳评分系统V2 正式版数据 =====================
// RAW（数据字段）: [代码,简称,类型,板块,风险原因,
//  已锁定退市, 备注, 市值_亿, 市值_显示, 昨收, 信号串]
// V2RAW（唯一评分口径）: [代码,简称,类型,板块,
//  C1,C2,S1,S2, A1,A2,A3, D1, B1,B2, F2,F1, H1 (13个),
//  已锁定退市, 备注, 实控人, 实控人分类, total]
// 分数越高 = 保壳能力越强
const REPORT_LABEL = "{report_label}";
const SHELL_BASE_YI = {SHELL_BASE_YI};  // 壳基准（亿），与build_baokeng_v2.py同源
const SHELL_BASE_LABEL = "{SHELL_BASE_LABEL}";
const RAW = {raw_str};

// V2 保壳能力总分 = 13维之和（100分制）+ 通道封顶（与build_baokeng_v2.py一致）
const V2RAW = {v2_str};
function calcScore2(r) {{
  let s = r[4]+r[5]+r[6]+r[7]+r[8]+r[9]+r[10]+r[11]+r[12]+r[13]+r[14]+r[15]+r[16];
  if (r[4] === 0) s = Math.min(s, 50);   // C1=0 面值危机：交易类通道触发，封顶50
  if (r[13] === 0) s = Math.min(s, 50);  // B2=0 无法表示/否定意见：规范类通道触发，封顶50
  if (r[12] === 0) s = Math.min(s, 30);  // B1=0 涉造假立案：重大违法通道，封顶30
  return s;
}}
function calcLevel2(s) {{ return s>70?'A': s>50?'B': s>30?'C': 'D'; }}

const V2MAP = new Map();
V2RAW.forEach(r => {{
  const s2 = calcScore2(r);
  V2MAP.set(r[0], {{
    C1:r[4], C2:r[5], S1:r[6], S2:r[7], A1:r[8], A2:r[9], A3:r[10],
    D1:r[11], B1:r[12], B2:r[13], F2:r[14], F1:r[15], H1:r[16],
    delisted:r[17], note2:r[18], controller:r[19], controller_cat:r[20],
    total2:r[21], score2:s2, level2:calcLevel2(s2)
  }});
}});

const FLAG_CN = {{
  investigation:'立案调查', adverse_audit:'无法表示/否定意见', qualified_audit:'保留意见',
  penalty:'行政处罚', warning:'警示函/监管函', freeze:'股份冻结', consume_limit:'限制消费',
  restructuring:'重整', asset_sale:'资产出售', debt_waiver:'债务豁免', donation:'资产赠与'
}};
const SIG_CLASS = {{
  investigation:'sig-risk', penalty:'sig-risk', freeze:'sig-owner', consume_limit:'sig-owner',
  adverse_audit:'sig-audit', qualified_audit:'sig-audit', warning:'sig-audit',
  restructuring:'sig-rescue', asset_sale:'sig-rescue', debt_waiver:'sig-rescue', donation:'sig-rescue'
}};
const RESCUE_SET = new Set(['restructuring','asset_sale','debt_waiver','donation']);

const COS = RAW.map(r => {{
  const v2 = V2MAP.get(r[0]) || null;
  const flags = (r[10]||'').split(',').filter(Boolean);
  const rescueN = flags.filter(f=>RESCUE_SET.has(f)).length;
  const riskN = flags.length - rescueN;
  return {{ code:r[0], name:r[1], type:r[2], board:r[3], reason:r[4],
    delisted:r[5], note:r[6],
    market_cap_yi:r[7], market_cap_str:r[8], prev_close:r[9],
    flags:flags, riskN:riskN, rescueN:rescueN,
    v2: v2,
    score: v2 ? v2.score2 : 0,
    level: v2 ? v2.level2 : 'D' }};
}});

const CODE_MAP = new Map();
COS.forEach(c => {{ if(!CODE_MAP.has(c.code)) CODE_MAP.set(c.code, c); }});
const UNIQUE = Array.from(CODE_MAP.values());

const BY_SCORE = [...UNIQUE].sort((a,b)=>b.score-a.score);
BY_SCORE.forEach((c,i)=>c.rank=i+1);

// ===================== 摸鱼榜：市值越低 + 保壳分越高 = 综合机会越好 =====================
// 壳便宜分：市值对数归一化（最便宜=100, 最贵=0, 仅非退市且市值>0）
// 摸鱼指数 = (50%×保壳分 + 50%×壳便宜分) × 等级系数（A/B 1.0 · C 0.85 · D 0.6）
const MOYU_LV_K = {{'A':1.0,'B':1.0,'C':0.85,'D':0.6}};
const MOYU_POOL = UNIQUE.filter(c=>!c.delisted && c.market_cap_yi>0);
{{
  const lns = MOYU_POOL.map(c=>Math.log(c.market_cap_yi));
  const lnMin = Math.min(...lns), lnMax = Math.max(...lns), lnSpan = (lnMax-lnMin) || 1;
  MOYU_POOL.forEach(c=>{{
    c.cheap = Math.round(100*(lnMax-Math.log(c.market_cap_yi))/lnSpan);
    c.moyu = Math.round((c.score*0.5 + c.cheap*0.5) * MOYU_LV_K[c.level] * 10) / 10;
  }});
}}
const BY_MOYU = [...MOYU_POOL].sort((a,b)=>b.moyu-a.moyu);
BY_MOYU.forEach((c,i)=>c.moyuRank=i+1);

const LC = {{'A':'#27ae60','B':'#2980b9','C':'#e67e22','D':'#c0392b'}};
const LT = {{'A':'低风险·退市概率低','B':'中风险·保壳有希望','C':'高风险·保壳难度大','D':'极高风险·退市警钟'}};
const LE = {{'A':'✅ 综合评估：保壳能力较强','B':'🔵 综合评估：中等退市风险','C':'🟠 综合评估：较高退市风险','D':'🔴 综合评估：退市风险极高'}};

let currentFilter = 'all';

let sortKey = 'score';
let sortDir = -1;

function sortBy(key){{
  if(sortKey===key) {{ sortDir = -sortDir; }}
  else {{
    sortKey = key;
    sortDir = (key==='code'||key==='name'||key==='type'||key==='reason'||key==='level') ? 1 : -1;
  }}
  renderList();
}}

function updateSortIndicators(){{
  document.querySelectorAll('#listHead th[data-key]').forEach(th=>{{
    const k = th.getAttribute('data-key');
    th.classList.remove('sorted-asc','sorted-desc');
    if(k===sortKey) th.classList.add(sortDir===1?'sorted-asc':'sorted-desc');
  }});
}}

function initStats(){{
  try {{
    const active = UNIQUE.filter(c=>!c.delisted);
    ['A','B','C','D'].forEach(l=>{{
      const el = document.getElementById('s'+l);
      if(el) el.textContent=active.filter(c=>c.level===l).length;
    }});
  }} catch(e){{ }}
}}

function signalDots(c){{
  if(c.riskN===0 && c.rescueN===0) return '<span style="color:#ccc">—</span>';
  let out = '';
  if(c.riskN>0) out += `<span class="sig-dot risk" title="风险信号 ${{c.riskN}} 项"></span><span style="font-size:11px;color:#c0392b">${{c.riskN}}</span> `;
  if(c.rescueN>0) out += `<span class="sig-dot rescue" title="纾困信号 ${{c.rescueN}} 项"></span><span style="font-size:11px;color:#1a6b3a">${{c.rescueN}}</span>`;
  return out;
}}

// 首页三张 TOP10 表：名称 / 代码 / 市值 / 评分 四项
function topTableHTML(list, getVal, getCol, label, onClickFn){{
  const click = onClickFn || (c=>`gotoDetail('${{c.code}}')`);
  return `<table class="top-table">
    <thead><tr><th>名次</th><th>名称</th><th>代码</th><th>市值(亿)</th><th style="text-align:right">${{label}}</th></tr></thead>
    <tbody>${{list.map((c,i)=>`
      <tr onclick="${{click(c)}}">
        <td class="t-rank">${{i+1}}</td>
        <td class="t-name" title="${{c.name}}">${{c.name}}</td>
        <td class="t-code">${{c.code}}</td>
        <td class="t-cap">${{c.market_cap_str}}</td>
        <td class="t-score" style="color:${{getCol(c)}}">${{getVal(c)}}</td>
      </tr>`).join('')}}</tbody></table>`;
}}

function renderRank(){{
  const easy = BY_SCORE.slice(0,10);
  const hard = BY_SCORE.slice(-10).reverse();
  const moyu = BY_MOYU.slice(0,10);
  document.getElementById('easyList').innerHTML = topTableHTML(easy, c=>c.score, c=>LC[c.level], '保壳分');
  document.getElementById('hardList').innerHTML = topTableHTML(hard, c=>c.score, c=>LC[c.level], '保壳分');
  document.getElementById('moyuTopList').innerHTML = topTableHTML(moyu, c=>c.moyu, ()=> '#b9770e', '摸鱼指数', c=>`openMoyuReport('${{c.code}}')`);
}}

function renderMoyu(){{
  const MC = '#b9770e';
  document.getElementById('moyuList').innerHTML = BY_MOYU.slice(0,20).map((c,i)=>`
  <div class="rank-item" onclick="openMoyuReport('${{c.code}}')">
    <div class="rank-num ${{numClass(i)}}">${{i+1}}</div>
    <div class="rank-info">
      <div class="rank-name">${{c.name}}<span class="rtag rtag-${{c.level}}">${{c.level}}</span></div>
      <div class="rank-code">${{c.code}} · ${{c.board}} · 市值${{c.market_cap_str}}亿 · 保壳分${{c.score}} · 壳便宜分${{c.cheap}}</div>
    </div>
    <div class="rank-score-col">
      <div class="mini-bar-wrap"><div class="mini-bar" style="width:${{Math.min(100,Math.round(c.moyu))}}%;background:${{MC}}"></div></div>
      <div class="score-val" style="color:${{MC}}" title="摸鱼指数">${{c.moyu}}</div>
    </div>
  </div>`).join('');
}}

function numClass(i){{ return i===0?'gold':i===1?'silver':i===2?'bronze':'other'; }}

function getFiltered(){{
  let data;
  if(currentFilter==='all') data = [...BY_SCORE];
  else if(currentFilter==='ST') data = BY_SCORE.filter(c=>c.type==='ST');
  else if(currentFilter==='*ST') data = BY_SCORE.filter(c=>c.type==='*ST');
  else data = BY_SCORE.filter(c=>c.level===currentFilter);
  const k = sortKey, d = sortDir;
  data.sort((a,b)=>{{
    let va = a[k], vb = b[k];
    if(k==='signal'){{ va=a.riskN-a.rescueN; vb=b.riskN-b.rescueN; }}
    if(typeof va==='string' || typeof vb==='string') return String(va).localeCompare(String(vb),'zh')*d;
    return (va-vb)*d;
  }});
  return data;
}}

function setFilter(f, el){{
  currentFilter = f;
  document.querySelectorAll('.filter-chip').forEach(c=>c.classList.remove('active'));
  if(el) el.classList.add('active');
  renderList();
}}

function renderList(){{
  const data = getFiltered();
  document.getElementById('listBody').innerHTML = data.map((c,i)=>`
    <tr onclick="gotoDetail('${{c.code}}')">
      <td>${{c.rank}}</td><td>${{c.code}}</td><td>${{c.name}}</td><td>${{c.type}}</td>
      <td title="${{c.reason}}">${{c.reason.length>18?c.reason.slice(0,18)+'…':c.reason}}</td>
      <td title="${{c.flags.map(f=>FLAG_CN[f]).join('、')||'无'}}">${{signalDots(c)}}</td>
      <td style="font-weight:700;color:${{LC[c.level]}}">${{c.score}}</td>
      <td><span class="rtag rtag-${{c.level}}">${{c.level}}</span></td>
      <td style="font-weight:500;color:#1a3d2b">${{c.market_cap_str}}</td>
      <td class="link-style">查看 →</td>
    </tr>`).join('');
  updateSortIndicators();
}}

function switchTab(n){{
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',['rank','moyu','query','list','vote'][i]===n));
  document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+n).classList.add('active');
  if(n==='vote') renderVoteRank();
}}

function norm(s){{
  return (s||'').replace(/[\\uFF01-\\uFF5E]/g, ch=>String.fromCharCode(ch.charCodeAt(0)-0xFEE0))
    .replace(/\\u3000/g,' ').replace(/\\s+/g,'').toUpperCase();
}}

function doQuery(){{
  const raw = document.getElementById('qInput').value.trim();
  if(!raw) return;
  const q = norm(raw);
  let c = UNIQUE.find(x=>x.code===q);
  if(!c) c = UNIQUE.find(x=>norm(x.name)===q);
  if(!c) c = UNIQUE.find(x=>norm(x.name).replace(/[*＊]?ST/,'').includes(q.replace(/[*＊]?ST/,'')));
  if(!c) c = UNIQUE.find(x=>q.includes(norm(x.name).replace(/[*＊]?ST/,'')));
  if(!c){{
    const kw = q.replace(/[*＊]?ST/gi,'').trim();
    if(kw.length>=1) c = UNIQUE.find(x=>norm(x.name).replace(/[*＊]?ST/gi,'').includes(kw));
  }}
  if(!c){{
    document.getElementById('qResult').innerHTML=`
      <div class="empty-state">
        <div style="font-size:40px;margin-bottom:10px">😕</div>
        <div style="margin-bottom:8px">未找到「<b>${{raw}}</b>」</div>
        <div style="font-size:12px;color:#aaa">当前数据覆盖 ${{UNIQUE.length}} 家ST公司。提示：输入完整代码或完整简称试试。</div>
      </div>`;
    return;
  }}
  showReport(c);
}}
document.getElementById('qInput').addEventListener('keydown',e=>{{ if(e.key==='Enter') doQuery(); }});

function gotoDetail(code){{
  switchTab('query');
  document.getElementById('qInput').value = code;
  const c = UNIQUE.find(x=>x.code===code);
  if(c) showReport(c);
}}

function showReport(c){{
  const col = LC[c.level];
  const v2 = c.v2;
  const v2f = v2 ? [
    {{label:'C1 面值距离(6)',v:v2.C1,max:6,col:'#117a65'}},
    {{label:'C2 壳价值·反转(8)',v:v2.C2,max:8,col:'#148f77'}},
    {{label:'S1 实控人性质(12)',v:v2.S1,max:12,col:'#8e44ad'}},
    {{label:'S2 股权质押(6)',v:v2.S2,max:6,col:'#6c3483'}},
    {{label:'A1 净资产(10)',v:v2.A1,max:10,col:'#2980b9'}},
    {{label:'A2 扣非主营收入(12)',v:v2.A2,max:12,col:'#1a5e35'}},
    {{label:'A3 扣非净利润(6)',v:v2.A3,max:6,col:'#27ae60'}},
    {{label:'D1 现金流质量(4)',v:v2.D1,max:4,col:'#1a5276'}},
    {{label:'B1 立案/造假★(10)',v:v2.B1,max:10,col:'#2e86c1'}},
    {{label:'B2 审计意见★(12)',v:v2.B2,max:12,col:'#5499c7'}},
    {{label:'F2 重组/纾困★(6)',v:v2.F2,max:6,col:'#f39c12'}},
    {{label:'F1 财务趋势◆(4)',v:v2.F1,max:4,col:'#117a65'}},
    {{label:'H1 司法风险★(4)',v:v2.H1,max:4,col:'#af601a'}},
  ] : [];
  const sigHTML = c.flags.length
    ? c.flags.map(f=>`<span class="sig-tag ${{SIG_CLASS[f]}}">${{FLAG_CN[f]}}</span>`).join('')
    : '<span class="sig-tag sig-none">近24个月无命中信号</span>';
  const ctrlHTML = v2 && v2.controller
    ? `${{v2.controller}}<span style="font-size:10px;color:#999">（${{v2.controller_cat}}）</span>`
    : '未获取';
  const v2Note = v2 && v2.note2 ? v2.note2 : c.note;
  document.getElementById('qResult').innerHTML=`
    <div class="report-card">
      <div class="report-top">
        <div>
          <div class="report-name">${{c.name}} <span class="rtag rtag-${{c.level}}">${{c.level}}</span></div>
          <div class="report-sub">${{c.code}} · ${{c.board}} · ${{c.type}}</div>
        </div>
        <div style="text-align:right">
          <div class="score-big" style="color:${{col}}">${{c.score}}<span style="font-size:16px;font-weight:400"> 分</span></div>
          <div class="score-label">全榜第 ${{c.rank}} / ${{UNIQUE.length}}（越高越易保壳）</div>
          ${{c.moyuRank ? `<div class="score-label" style="color:#b9770e">🎣 摸鱼榜第 ${{c.moyuRank}} / ${{MOYU_POOL.length}} · 指数 ${{c.moyu}}</div>` : ''}}
        </div>
      </div>
      <div class="info-row">
        <div class="info-chip"><div class="info-chip-label">实控人（S1）</div><div class="info-chip-val" style="font-size:11px">${{ctrlHTML}}</div></div>
        <div class="info-chip"><div class="info-chip-label">风险原因</div><div class="info-chip-val" style="font-size:11px">${{c.reason}}</div></div>
        <div class="info-chip"><div class="info-chip-label">昨收 / 总市值</div><div class="info-chip-val">${{c.prev_close}} · ${{c.market_cap_str}}亿</div></div>
        <div class="info-chip"><div class="info-chip-label">财务报告期</div><div class="info-chip-val">{report_label}</div></div>
      </div>
      <div class="factors-section" style="margin-bottom:8px">
        <div class="factors-title">公告风险/纾困信号（巨潮资讯网 · 近24个月）</div>
        <div class="signal-row">${{sigHTML}}</div>
      </div>
      <div class="factors-section">
        <div class="factors-title">ST保壳评分系统V2 十三维退市概率打分明细（满分100分 · ★=公告数据 ◆=外部数据接口）</div>
        ${{v2f.map(f=>`<div class="factor-row">
          <div class="factor-label">${{f.label}}</div>
          <div class="factor-bar-wrap"><div class="factor-bar" style="width:${{Math.round(f.v/f.max*100)}}%;background:${{f.col}}"></div></div>
          <div class="factor-score" style="color:${{f.col}}">${{f.v}}/${{f.max}}</div>
        </div>`).join('')}}
      </div>
      <div class="conclusion-box ${{c.level}}">
        <div class="conclusion-title">${{LE[c.level]}}</div>
        <div class="conclusion-text">${{v2Note}}</div>
      </div>
      <button class="expert-btn" onclick="openExpertReport('${{c.code}}')">🧠 ST股分析专家 · 即时分析报告（会员专享）</button>
      ${{c.moyuRank ? `<button class="moyu-btn" onclick="openMoyuReport('${{c.code}}')">🎣 ST摸鱼模型 · 摸鱼分析报告（会员专享 · 可分享链接）</button>` : ''}}
    </div>
    ${{voteSectionHTML(c.code)}}`;
}}

const VK = 'bkfl_company_v2';

function loadAllVotes(){{ try{{ return JSON.parse(localStorage.getItem(VK))||{{}}; }}catch(e){{ return {{}}; }} }}
function saveAllVotes(v){{ localStorage.setItem(VK,JSON.stringify(v)); }}

function loadCompanyVote(code){{
  const all = loadAllVotes();
  return all[code] || {{A:0,B:0,C:0,D:0,my:null}};
}}
function saveCompanyVote(code, data){{
  const all = loadAllVotes();
  all[code] = data;
  saveAllVotes(all);
}}

function voteSectionHTML(code){{
  const v = loadCompanyVote(code);
  const c = UNIQUE.find(x=>x.code===code);
  const name = c ? c.name : code;
  const total = (v.A||0)+(v.B||0)+(v.C||0)+(v.D||0);
  const voted = !!v.my;
  return `
    <div class="vote-box" style="margin-top:16px" id="voteBox_${{code}}">
      <h3>🗳️ 你觉得 ${{name}} 保壳难度如何？</h3>
      <div class="vote-desc">为这家公司的保壳难度投票，${{total}} 人已参与</div>
      <div class="vote-options">
        <div class="vopt A ${{v.my==='A'?'selected':''}}" id="vo_${{code}}_A" onclick="pickCompanyVote('${{code}}','A')">
          <div class="vopt-letter">A</div>
          <div class="vopt-label">容易保壳</div>
        </div>
        <div class="vopt B ${{v.my==='B'?'selected':''}}" id="vo_${{code}}_B" onclick="pickCompanyVote('${{code}}','B')">
          <div class="vopt-letter">B</div>
          <div class="vopt-label">较容易</div>
        </div>
        <div class="vopt C ${{v.my==='C'?'selected':''}}" id="vo_${{code}}_C" onclick="pickCompanyVote('${{code}}','C')">
          <div class="vopt-letter">C</div>
          <div class="vopt-label">较困难</div>
        </div>
        <div class="vopt D ${{v.my==='D'?'selected':''}}" id="vo_${{code}}_D" onclick="pickCompanyVote('${{code}}','D')">
          <div class="vopt-letter">D</div>
          <div class="vopt-label">必定退市</div>
        </div>
      </div>
      <div style="text-align:center">
        <button class="vote-btn" id="vBtn_${{code}}" onclick="castCompanyVote('${{code}}')" ${{voted?'disabled':''}}>${{voted?'已投票 ✓（点击修改）':'请选择后提交'}}</button>
      </div>
      <div class="vresult-inline" id="vRes_${{code}}" style="display:${{total>0?'block':'none'}}">
        ${{voteBarsHTML(v, total)}}
        <div class="voted-tip">感谢投票！可随时修改你的判断</div>
      </div>
    </div>`;
}}

function voteBarsHTML(v, total){{
  return ['A','B','C','D'].map(o=>{{
    const cnt=v[o]||0, pct=total>0?Math.round(cnt/total*100):0;
    return `<div class="vbar-row">
      <div class="vbar-letter" style="color:${{LC[o]}}">${{o}}</div>
      <div class="vbar-outer"><div class="vbar-inner vbar-${{o}}" style="width:${{pct}}%;min-width:${{pct>0?'20px':'0'}}">${{pct>=8?pct+'%':''}}</div></div>
      <div class="vbar-count">${{cnt}}票${{v.my===o?' 👈':''}}</div>
    </div>`;
  }}).join('');
}}

let pendingVote = {{}};
function pickCompanyVote(code, opt){{
  pendingVote[code] = opt;
  ['A','B','C','D'].forEach(x=>{{
    const el = document.getElementById('vo_'+code+'_'+x);
    if(el) el.classList.toggle('selected', x===opt);
  }});
  const btn = document.getElementById('vBtn_'+code);
  if(btn){{ btn.disabled=false; btn.textContent='提交投票：'+opt+' 级'; }}
}}

function castCompanyVote(code){{
  const opt = pendingVote[code];
  if(!opt) return;
  const v = loadCompanyVote(code);
  if(v.my && v.my!==opt) v[v.my]--;
  if(!v.my || v.my!==opt) v[opt]++;
  v.my = opt;
  saveCompanyVote(code, v);
  const btn = document.getElementById('vBtn_'+code);
  if(btn){{ btn.textContent='已投票 ✓（点击修改）'; btn.disabled=false; }}
  const total = (v.A||0)+(v.B||0)+(v.C||0)+(v.D||0);
  const res = document.getElementById('vRes_'+code);
  if(res){{ res.style.display='block'; res.innerHTML = voteBarsHTML(v,total)+'<div class="voted-tip">感谢投票！可随时修改你的判断</div>'; }}
  const box = document.getElementById('voteBox_'+code);
  if(box){{
    const desc = box.querySelector('.vote-desc');
    if(desc) desc.textContent='为这家公司的保壳难度投票，'+total+' 人已参与';
  }}
  renderVoteRank();
}}

function renderVoteRank(){{
  const all = loadAllVotes();
  const entries = Object.entries(all).filter(([code,v])=>{{
    const t = (v.A||0)+(v.B||0)+(v.C||0)+(v.D||0);
    return t > 0;
  }});
  if(entries.length===0){{
    document.getElementById('voteHardList').innerHTML='<div class="vote-empty">暂无投票数据<br>去查询页看看公司详情并投票吧</div>';
    document.getElementById('voteEasyList').innerHTML='<div class="vote-empty">暂无投票数据<br>去查询页看看公司详情并投票吧</div>';
    return;
  }}
  const scored = entries.map(([code,v])=>{{
    const t = (v.A||0)+(v.B||0)+(v.C||0)+(v.D||0);
    const hard = (v.C||0)+(v.D||0);
    const easy = (v.A||0)+(v.B||0);
    const c = UNIQUE.find(x=>x.code===code);
    const name = c ? c.name : code;
    return {{code, name, total:t, hard, easy, v}};
  }});
  const hardRank = [...scored].sort((a,b)=>b.hard-a.hard || b.total-a.total).slice(0,8);
  const easyRank = [...scored].sort((a,b)=>b.easy-a.easy || b.total-a.total).slice(0,8);
  const maxH = Math.max(1, hardRank[0]?.hard||1);
  const maxE = Math.max(1, easyRank[0]?.easy||1);
  document.getElementById('voteHardList').innerHTML = hardRank.map((r,i)=>`
    <div class="vrc-item">
      <div class="vrc-rank">${{i+1}}</div>
      <div class="vrc-name" onclick="gotoDetail('${{r.code}}')">${{r.name}}</div>
      <div class="vrc-bar"><div class="vrc-bar-inner" style="width:${{Math.round(r.hard/maxH*100)}}%;background:#c0392b"></div></div>
      <div class="vrc-count">${{r.hard}}票</div>
    </div>`).join('');
  document.getElementById('voteEasyList').innerHTML = easyRank.map((r,i)=>`
    <div class="vrc-item">
      <div class="vrc-rank">${{i+1}}</div>
      <div class="vrc-name" onclick="gotoDetail('${{r.code}}')">${{r.name}}</div>
      <div class="vrc-bar"><div class="vrc-bar-inner" style="width:${{Math.round(r.easy/maxE*100)}}%;background:#27ae60"></div></div>
      <div class="vrc-count">${{r.easy}}票</div>
    </div>`).join('');
}}

// ===================== ST股分析专家 · 即时分析报告（会员专享） =====================
const MK = 'bkfl_member';
function getMember(){{ try{{ return JSON.parse(localStorage.getItem(MK)); }}catch(e){{ return null; }} }}
function closeModal(id){{ const el=document.getElementById(id); if(el) el.classList.remove('show'); }}
let MEM_AFTER = null; // 注册成功后要打开的报告：{{fn:'expert'|'moyu', code}}
function openExpertReport(code){{
  if(getMember()){{ showExpertReport(code); return; }}
  MEM_AFTER = {{fn:'expert', code:code}};
  const c = UNIQUE.find(x=>x.code===code);
  document.getElementById('memBody').innerHTML = `
    <div class="mem-locked">
      <div style="font-size:44px">🔐</div>
      <div style="font-weight:700;font-size:15px;margin:10px 0 4px">即时分析报告为会员专享内容</div>
      <div style="font-size:12.5px;color:#888">注册会员后即可免费查看「${{c?c.name+' ('+c.code+')':code}}」的 ST股分析专家即时报告</div>
    </div>
    <div style="margin-top:14px">
      <input class="mem-input" id="memPhone" placeholder="手机号（11位）" maxlength="11" inputmode="numeric">
      <input class="mem-input" id="memName" placeholder="昵称（选填）" maxlength="12">
      <button class="mem-btn" onclick="doRegister()">注册会员并查看报告</button>
      <div style="font-size:11px;color:#aaa;margin-top:8px;text-align:center">注册即代表同意《会员服务条款》· 会员信息仅保存在本机浏览器，不上传服务器</div>
    </div>`;
  document.getElementById('memMask').classList.add('show');
}}
function doRegister(){{
  const phone = (document.getElementById('memPhone').value||'').trim();
  if(!/^1\\d{{10}}$/.test(phone)){{ alert('请输入正确的11位手机号'); return; }}
  const name = (document.getElementById('memName').value||'').trim() || ('会员'+phone.slice(-4));
  localStorage.setItem(MK, JSON.stringify({{phone:phone, name:name, ts:Date.now()}}));
  closeModal('memMask');
  const a = MEM_AFTER; MEM_AFTER = null;
  if(a && a.fn==='moyu') showMoyuReport(a.code);
  else if(a && a.code) showExpertReport(a.code);
}}
function showExpertReport(code){{
  const c = UNIQUE.find(x=>x.code===code);
  if(!c) return;
  const m = getMember() || {{}};
  const v2 = c.v2 || {{}};
  const DIMP = [
    ['C1','面值距离',6],['C2','壳价值',8],['S1','实控人性质',12],['S2','股权质押',6],
    ['A1','净资产',10],['A2','扣非主营收入',12],['A3','扣非净利润',6],['D1','现金流质量',4],
    ['B1','立案/造假',10],['B2','审计意见',12],['F2','重组纾困',6],['F1','财务趋势',4],['H1','司法风险',4]
  ];
  const scored = DIMP.map(d=>({{t:d[1], v:(v2[d[0]]!=null?v2[d[0]]:null), max:d[2]}}))
    .filter(x=>x.v!=null).sort((a,b)=>a.v-b.v);
  const weak = scored.slice(0,3).map(x=>`${{x.t}} ${{x.v}}/${{x.max}}`).join('　') || '暂缺V2维度数据';
  const LV_TXT = {{
    A:'保壳压力低、退市风险小，短期无强制退市通道命中的迹象。',
    B:'保壳压力中等，个别维度存在失分，需跟踪下一报告期的修复情况。',
    C:'保壳压力较大，存在明确风险敞口，若短板维度不修复，存在退市可能。',
    D:'退市风险高，多通道濒临触发，除非出现实质性重整/纾困进展，否则应谨慎对待。'
  }};
  const sigNames = c.flags.map(f=>FLAG_CN[f]).filter(Boolean);
  const sigTxt = sigNames.length
    ? `近24个月命中公告信号 ${{sigNames.length}} 项：${{sigNames.join('、')}}。${{c.rescueN>0?'其中含纾困/重组类正向信号，保壳主动权仍在。':'暂无纾困类正向信号，保壳动作有待观察。'}}`
    : '近24个月无公告信号命中，监管与司法层面暂无新增事件。';
  const moyuSec = c.moyuRank
    ? `<div class="er-sec"><div class="er-sec-t">四、摸鱼视角（壳价 × 保壳）</div><div class="er-sec-b">摸鱼榜第 ${{c.moyuRank}} / ${{MOYU_POOL.length}} 名，指数 ${{c.moyu}}（壳便宜分 ${{c.cheap}}）。市值 ${{c.market_cap_str}}亿 ${{c.market_cap_yi<=SHELL_BASE_YI?'低于':'高于'}}${{SHELL_BASE_LABEL}}亿基准壳费线，${{c.moyu>=60?'并购/借壳成本优势与保壳确定性兼备，属于低位潜伏观察区。':'综合机会一般，壳价或保壳确定性至少一头不占优。'}}</div></div>`
    : '';
  document.getElementById('expBody').innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
      <div>
        <div style="font-weight:700;font-size:16px">${{c.name}} <span class="rtag rtag-${{c.level}}">${{c.level}}</span></div>
        <div style="font-size:11.5px;color:#999;margin-top:3px">${{c.code}} · ${{c.board}} · 全榜第 ${{c.rank}}/${{UNIQUE.length}} 名</div>
      </div>
      <div style="text-align:right;flex-shrink:0">
        <div style="font-size:26px;font-weight:800;color:${{LC[c.level]}}">${{c.score}}</div>
        <div style="font-size:10.5px;color:#999">V2保壳分</div>
      </div>
    </div>
    <div class="er-sec"><div class="er-sec-t">一、核心结论</div><div class="er-sec-b">${{c.name}}（${{c.code}}）当前V2保壳评分 ${{c.score}} 分，评级 ${{c.level}} 级，全榜第 ${{c.rank}} 名。${{LV_TXT[c.level]}}风险原因：${{c.reason}}。</div></div>
    <div class="er-sec"><div class="er-sec-t">二、三大短板维度</div><div class="er-sec-b">${{weak}}</div></div>
    <div class="er-sec"><div class="er-sec-t">三、公告信号面（巨潮资讯网 · 近24个月）</div><div class="er-sec-b">${{sigTxt}}</div></div>
    ${{moyuSec}}
    <button class="pdf-btn" id="pdfBtn" onclick="exportPDF('${{c.code}}')">📄 下载正式PDF版报告（A4 · ST股分析专家）</button>
    <div class="er-member-tip">👤 会员 ${{m.name||''}} 专属 · 报告基于报告期 <b>{report_label}</b> 数据即时生成</div>
    <div class="er-disclaim">⚠️ 免责声明：本报告由ST股分析专家基于公开数据自动生成，仅供参考，不构成任何投资建议。数据来源：巨潮资讯网、东方财富、腾讯财经。股市有风险，投资需谨慎。</div>`;
  document.getElementById('expTitle').textContent = '🧠 ST股分析专家 · 即时分析报告';
  document.getElementById('expMask').classList.add('show');
}}

// ===================== ST摸鱼模型 · 摸鱼分析报告（会员专享 · 链接直达 #moyu-代码） =====================
function openMoyuReport(code){{
  const c = UNIQUE.find(x=>x.code===code);
  if(!c) return;
  if(!c.moyuRank){{ alert('该标的未入摸鱼池（已锁定退市或无市值数据），暂无摸鱼分析报告。'); return; }}
  if(getMember()){{ showMoyuReport(code); return; }}
  MEM_AFTER = {{fn:'moyu', code:code}};
  document.getElementById('memBody').innerHTML = `
    <div class="mem-locked">
      <div style="font-size:44px">🔐🎣</div>
      <div style="font-weight:700;font-size:15px;margin:10px 0 4px">摸鱼分析报告为会员专享内容</div>
      <div style="font-size:12.5px;color:#888">注册会员后即可免费查看「${{c.name}}（${{c.code}}）」的 ST摸鱼模型摸鱼分析报告</div>
    </div>
    <div style="margin-top:14px">
      <input class="mem-input" id="memPhone" placeholder="手机号（11位）" maxlength="11" inputmode="numeric">
      <input class="mem-input" id="memName" placeholder="昵称（选填）" maxlength="12">
      <button class="mem-btn" onclick="doRegister()">注册会员并查看报告</button>
      <div style="font-size:11px;color:#aaa;margin-top:8px;text-align:center">注册即代表同意《会员服务条款》· 会员信息仅保存在本机浏览器，不上传服务器</div>
    </div>`;
  document.getElementById('memMask').classList.add('show');
}}
function showMoyuReport(code){{
  const c = UNIQUE.find(x=>x.code===code);
  if(!c || !c.moyuRank) return;
  const m = getMember() || {{}};
  const v2 = c.v2 || {{}};
  const KC = {{A:1.0, B:1.0, C:0.85, D:0.6}};
  const K = KC[c.level];
  const half = Math.round((c.score*0.5 + c.cheap*0.5)*10)/10;
  const DIMP = [
    ['C1','面值距离',6],['C2','壳价值',8],['S1','实控人性质',12],['S2','股权质押',6],
    ['A1','净资产',10],['A2','扣非主营收入',12],['A3','扣非净利润',6],['D1','现金流质量',4],
    ['B1','立案/造假',10],['B2','审计意见',12],['F2','重组纾困',6],['F1','财务趋势',4],['H1','司法风险',4]
  ];
  const scored = DIMP.map(d=>({{t:d[1], v:(v2[d[0]]!=null?v2[d[0]]:null), max:d[2]}}))
    .filter(x=>x.v!=null).sort((a,b)=>a.v-b.v);
  const weak = scored.slice(0,3).map(x=>`${{x.t}} ${{x.v}}/${{x.max}}`).join('　') || '暂缺V2维度数据';
  const KWHY = {{A:'A级保壳压力低，不折扣', B:'B级保壳压力中等，不折扣', C:'C级存在明确风险敞口，打85折', D:'D级多通道濒临触发，打6折防飞刀'}};
  const cap = c.market_cap_yi;
  const capPct = cap>0 ? Math.round(cap/SHELL_BASE_YI*100) : null;
  const capTxt = cap<=SHELL_BASE_YI
    ? `当前市值 ${{c.market_cap_str}} 亿，仅为${{SHELL_BASE_LABEL}}亿基准壳费线的 ${{capPct}}% —— 买方并购/借壳成本低，壳价具备明显折价优势，是摸鱼模型"便宜"一侧的核心加分项。`
    : `当前市值 ${{c.market_cap_str}} 亿，为${{SHELL_BASE_LABEL}}亿基准壳费线的 ${{capPct}}% —— 壳价偏贵，并购/借壳成本高于基准线，"便宜"一侧不占优。`;
  let zone, zoneCol, zoneTxt;
  if(c.moyu>=65){{ zone='🎣 重点潜伏区'; zoneCol='#1a6b3a';
    zoneTxt='壳便宜与保壳确定性双优：市值低于或接近基准壳费线，同时V2保壳分不低，属于摸鱼模型的低位潜伏核心池。策略上适合小仓位跟踪公告信号，等待并购/借壳/重整预期发酵，不宜追高。'; }}
  else if(c.moyu>=50){{ zone='👀 观察区'; zoneCol='#8e6a1f';
    zoneTxt='壳价或保壳确定性一头占优、一头平平：综合机会中等。适合列入观察清单，等待市值回落或保壳分修复（营收达标、审计意见改善、纾困公告落地）后升级。'; }}
  else if(c.moyu>=35){{ zone='⚠️ 谨慎区'; zoneCol='#a04000';
    zoneTxt='壳价与保壳确定性均不突出，或等级系数已折价：综合机会偏弱。除非出现明确重组/纾困催化，否则性价比一般。'; }}
  else{{ zone='🚫 回避区'; zoneCol='#922b21';
    zoneTxt='综合机会差：要么壳太贵，要么保壳确定性太低（常见于D级或面值/审计通道濒临触发）。摸鱼模型建议回避，谨防"超便宜但快退市"的飞刀。'; }}
  const sigNames = c.flags.map(f=>FLAG_CN[f]).filter(Boolean);
  const sigTxt = sigNames.length
    ? `近24个月命中公告信号 ${{sigNames.length}} 项：${{sigNames.join('、')}}。${{c.rescueN>0?'含纾困/重组类正向信号 —— 摸鱼视角下属于催化事件，可提升潜伏价值。':'无纾困类正向信号，催化事件尚未出现。'}}`
    : '近24个月无公告信号命中，监管与司法层面暂无新增事件。';
  document.getElementById('expBody').innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
      <div>
        <div style="font-weight:700;font-size:16px">${{c.name}} <span class="rtag rtag-${{c.level}}">${{c.level}}</span></div>
        <div style="font-size:11.5px;color:#999;margin-top:3px">${{c.code}} · ${{c.board}} · 保壳分全榜第 ${{c.rank}}/${{UNIQUE.length}} 名</div>
      </div>
      <div style="text-align:right;flex-shrink:0">
        <div style="font-size:26px;font-weight:800;color:#b9770e">${{c.moyu}}</div>
        <div style="font-size:10.5px;color:#999">摸鱼指数</div>
      </div>
    </div>
    <div class="er-sec"><div class="er-sec-t" style="color:#8e6a1f">一、摸鱼指数计算明细</div>
      <table class="mr-calc">
        <tr><td>V2保壳分（权重50%）</td><td>${{c.score}} 分</td></tr>
        <tr><td>壳便宜分（权重50%，市值对数归一化）</td><td>${{c.cheap}} 分</td></tr>
        <tr><td>加权合计</td><td>${{half}} 分</td></tr>
        <tr><td>× 等级系数（${{c.level}}级 · ${{KWHY[c.level]}}）</td><td>× ${{K}}</td></tr>
        <tr><td><b>摸鱼指数（全池第 ${{c.moyuRank}} / ${{MOYU_POOL.length}} 名）</b></td><td><b>${{c.moyu}}</b></td></tr>
      </table>
    </div>
    <div class="er-sec"><div class="er-sec-t" style="color:#8e6a1f">二、壳价分析（对标${{SHELL_BASE_LABEL}}亿基准壳费）</div><div class="er-sec-b">${{capTxt}}</div></div>
    <div class="er-sec"><div class="er-sec-t" style="color:#8e6a1f">三、保壳确定性</div><div class="er-sec-b">V2保壳评分 ${{c.score}} 分（${{c.level}}级），三大短板维度：${{weak}}。${{c.level==='A'||c.level==='B'?'退市通道短期内无集中触发迹象，确定性一侧达标。':'确定性一侧存在失分，需跟踪短板维度下一报告期的修复情况。'}}</div></div>
    <div class="er-sec"><div class="er-sec-t" style="color:#8e6a1f">四、公告信号面（巨潮资讯网 · 近24个月）</div><div class="er-sec-b">${{sigTxt}}</div></div>
    <div class="er-sec"><div class="er-sec-t" style="color:${{zoneCol}}">五、摸鱼结论：${{zone}}</div><div class="er-sec-b">${{zoneTxt}}</div></div>
    <button class="moyu-btn" onclick="copyMoyuLink('${{c.code}}')">🔗 复制本报告链接（#moyu-${{c.code}}，打开直达）</button>
    <div class="er-member-tip">👤 会员 ${{m.name||''}} 专属 · ST摸鱼模型基于报告期 <b>{report_label}</b> 数据即时生成</div>
    <div class="er-disclaim">⚠️ 免责声明：本报告由ST摸鱼模型基于公开数据自动生成，"摸鱼指数"仅为壳价与保壳确定性的复合观察指标，不构成任何投资建议。数据来源：巨潮资讯网、东方财富、腾讯财经。股市有风险，投资需谨慎。</div>`;
  document.getElementById('expTitle').textContent = '🎣 ST摸鱼模型 · 摸鱼分析报告';
  document.getElementById('expMask').classList.add('show');
}}
function copyMoyuLink(code){{
  const url = location.href.split('#')[0] + '#moyu-' + code;
  const show = ()=>alert('报告链接已复制：\\n' + url + '\\n\\n任何人打开该链接（注册会员后）即可直达「' + (UNIQUE.find(x=>x.code===code)||{{}}).name + '」的摸鱼分析报告。');
  const fallback = ()=>{{
    const ta = document.createElement('textarea');
    ta.value = url; ta.style.cssText='position:fixed;left:-9999px;';
    document.body.appendChild(ta); ta.select();
    try{{ document.execCommand('copy'); show(); }}catch(e){{ prompt('请手动复制链接：', url); }}
    document.body.removeChild(ta);
  }};
  if(navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(show).catch(fallback);
  else fallback();
}}
function checkHashRoute(){{
  const h = decodeURIComponent(location.hash||'').trim();
  const m = h.match(/^#moyu-(\\d{{6}})$/);
  if(m){{
    const code = m[1];
    const c = UNIQUE.find(x=>x.code===code);
    switchTab('moyu');
    if(!c){{ alert('链接中的标的 '+code+' 不在当前榜单数据中（可能已摘帽或退市），请从摸鱼榜重新选择。'); return true; }}
    openMoyuReport(code);
    return true;
  }}
  return false;
}}
window.addEventListener('hashchange', ()=>{{ checkHashRoute(); }});

// ===================== 正式版PDF报告（A4版式 · html2pdf页面端导出） =====================
// 引擎自托管于 assets/html2pdf.bundle.min.js（含html2canvas+jsPDF），首次点击懒加载
function loadHtml2Pdf(){{
  return new Promise((resolve, reject) => {{
    if (window.html2pdf) return resolve();
    const s = document.createElement('script');
    s.src = 'assets/html2pdf.bundle.min.js';
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('engine load failed'));
    document.head.appendChild(s);
  }});
}}
const DDESC = {{
  C1:'股价对面值退市线的安全距离', C2:'市值越低，并购/借壳机会越大', S1:'实控人背景与资本运作能力',
  S2:'质押比例反映股权稳定性', A1:'归母净资产充裕度', A2:'主营造血能力（主板3亿/双创1亿线）',
  A3:'主业盈利修复能力', D1:'经营现金流对营收的支撑', B1:'涉造假立案的违法类退市通道',
  B2:'年审意见类型对应的规范类通道', F2:'重整/出售/豁免等保壳动作', F1:'营收与扣非的趋势方向', H1:'实控人冻结/限高等司法事件'
}};
function buildFormalReport(c){{
  const m = getMember() || {{}};
  const v2 = c.v2 || {{}};
  const DIMP = [
    ['C1','面值距离',6],['C2','壳价值',8],['S1','实控人性质',12],['S2','股权质押',6],
    ['A1','净资产',10],['A2','扣非主营收入',12],['A3','扣非净利润',6],['D1','现金流质量',4],
    ['B1','立案/造假',10],['B2','审计意见',12],['F2','重组纾困',6],['F1','财务趋势',4],['H1','司法风险',4]
  ];
  const LV_TXT2 = {{
    A:'保壳压力低、退市风险小，短期无强制退市通道命中的迹象。',
    B:'保壳压力中等，个别维度存在失分，需跟踪下一报告期的修复情况。',
    C:'保壳压力较大，存在明确风险敞口，若短板维度不修复，存在退市可能。',
    D:'退市风险高，多通道濒临触发，除非出现实质性重整/纾困进展，否则应谨慎对待。'
  }};
  const dimRows = DIMP.map(d => {{
    const v = (v2[d[0]] != null) ? v2[d[0]] : null;
    const col = v==null ? '#8aa294' : (v/d[2]>=0.6 ? '#27ae60' : v/d[2]>=0.3 ? '#e67e22' : '#c0392b');
    return `<tr><td>${{d[1]}}（${{d[0]}}）</td><td style="color:${{col}};font-weight:700">${{v==null?'—':v}}</td><td>${{d[2]}}</td><td style="color:#6b7f74">${{DDESC[d[0]]}}</td></tr>`;
  }}).join('');
  const scored = DIMP.map(d=>({{t:d[1], v:(v2[d[0]]!=null?v2[d[0]]:null), max:d[2]}})).filter(x=>x.v!=null).sort((a,b)=>a.v-b.v);
  const weak = scored.slice(0,3).map(x=>`${{x.t}}（${{x.v}}/${{x.max}}分）`).join('、') || '暂缺V2维度数据';
  const sigChips = c.flags.map(f=>`<span class="fr-chip" style="background:${{SIG_CLASS[f]==='sig-rescue'?'#d5f5e3':'#fadbd8'}};color:${{SIG_CLASS[f]==='sig-rescue'?'#1a6b3a':'#922b21'}}">${{FLAG_CN[f]||f}}</span>`).join('') || '<span style="color:#6b7f74">近24个月无公告信号命中</span>';
  const sigTxt = c.flags.length
    ? `近24个月命中公告信号 ${{c.flags.length}} 项（风险类 ${{c.riskN}} 项 / 纾困类 ${{c.rescueN}} 项）。${{c.rescueN>0?'其中含纾困/重组类正向信号，保壳主动权仍在公司手中。':'暂无纾困类正向信号，保壳动作有待观察。'}}`
    : '近24个月无公告信号命中，监管与司法层面暂无新增事件。';
  const capTxt = [];
  if (v2.C1 === 0) capTxt.push('面值退市危机通道已触发（C1=0），总分封顶50分');
  if (v2.B2 === 0) capTxt.push('审计意见为无法表示/否定意见（B2=0），总分封顶50分');
  if (v2.B1 === 0) capTxt.push('涉造假立案（B1=0），总分封顶30分');
  const capHtml = capTxt.length ? `<div class="fr-sec"><div class="fr-sec-t">六、通道封顶警示</div><div class="fr-sec-b"><b style="color:#c0392b">${{capTxt.join('；')}}。</b>该标的存在已触发的强制退市通道，评分封顶机制生效，实际退市风险显著高于总分表象。</div></div>` : '';
  const moyuSec = c.moyuRank
    ? `<div class="fr-sec"><div class="fr-sec-t">五、摸鱼视角（壳价 × 保壳确定性）</div><div class="fr-sec-b">摸鱼榜第 ${{c.moyuRank}} / ${{MOYU_POOL.length}} 名，摸鱼指数 ${{c.moyu}}（壳便宜分 ${{c.cheap}}）。当前市值 ${{c.market_cap_str}} 亿，${{c.market_cap_yi<=SHELL_BASE_YI?'低于':'高于'}}${{SHELL_BASE_LABEL}}亿元基准壳费线。${{c.moyu>=60?'并购/借壳成本优势与保壳确定性兼备，属于低位潜伏观察区。':'综合机会一般，壳价或保壳确定性至少一头不占优。'}}</div></div>`
    : '<div class="fr-sec"><div class="fr-sec-t">五、摸鱼视角（壳价 × 保壳确定性）</div><div class="fr-sec-b">该标的因已锁定退市或无市值数据，未纳入摸鱼榜（摸鱼池仅含非退市且市值>0标的）。</div></div>';
  const now = new Date();
  const ts = now.getFullYear()+'年'+(now.getMonth()+1)+'月'+now.getDate()+'日 '+String(now.getHours()).padStart(2,'0')+':'+String(now.getMinutes()).padStart(2,'0');
  const col = LC[c.level];
  return `
  <div class="fr">
    <div class="fr-band">
      <div class="fr-band-l">ST保壳评分系统 V2</div>
      <div class="fr-band-r">A013-208号 · 会员专享正式报告<br>报告期：${{REPORT_LABEL}}</div>
    </div>
    <div class="fr-pad">
      <div class="fr-title">${{c.name}}（${{c.code}}）<br>退市风险与保壳能力分析报告</div>
      <div class="fr-subtitle">ST股分析专家 · 基于V2十三维评分体系</div>
      <div class="fr-meta"><div class="fr-meta-grid">
        <div class="fr-mcell"><div class="fr-mk">评级 / 总分</div><div class="fr-mv"><b style="color:${{col}};font-size:14px">${{c.level}} 级 · ${{c.score}} 分</b>（${{LT[c.level]}}）</div></div>
        <div class="fr-mcell"><div class="fr-mk">全榜排名</div><div class="fr-mv">第 ${{c.rank}} 名 / 共 ${{UNIQUE.length}} 家 ST/*ST</div></div>
        <div class="fr-mcell"><div class="fr-mk">摸鱼榜排名</div><div class="fr-mv">${{c.moyuRank?('第 '+c.moyuRank+' 名 · 指数 '+c.moyu):'未入池'}}</div></div>
        <div class="fr-mcell"><div class="fr-mk">市值</div><div class="fr-mv">${{c.market_cap_str||'—'}} 亿元（昨收 ${{c.prev_close||'—'}} 元）</div></div>
        <div class="fr-mcell"><div class="fr-mk">板块 / 类型</div><div class="fr-mv">${{c.board}} · ${{c.type}}</div></div>
        <div class="fr-mcell"><div class="fr-mk">实控人</div><div class="fr-mv">${{v2.controller||'—'}}${{v2.controller_cat?('（'+v2.controller_cat+'）'):''}}</div></div>
        <div class="fr-mcell"><div class="fr-mk">风险原因</div><div class="fr-mv">${{c.reason||'—'}}</div></div>
        <div class="fr-mcell"><div class="fr-mk">退市状态</div><div class="fr-mv">${{c.delisted?'⚠️ 已锁定退市':'正常挂牌'}}</div></div>
      </div></div>
      <div class="fr-sec"><div class="fr-sec-t">一、核心结论</div><div class="fr-sec-b">${{c.name}}（${{c.code}}）当前V2保壳评分 <b>${{c.score}} 分</b>，评级 <b style="color:${{col}}">${{c.level}} 级</b>，全榜第 ${{c.rank}} 名。${{LV_TXT2[c.level]}}主要风险原因：${{c.reason}}。</div></div>
      <div class="fr-sec"><div class="fr-sec-t">二、V2十三维评分明细（满分100）</div>
        <table class="fr-table"><thead><tr><th style="width:26%">维度</th><th style="width:12%">得分</th><th style="width:10%">满分</th><th>评分说明</th></tr></thead><tbody>${{dimRows}}</tbody></table>
      </div>
      <div class="fr-sec"><div class="fr-sec-t">三、三大短板维度</div><div class="fr-sec-b">失分最严重的三个维度为：${{weak}}。上述维度是决定该标的保壳成败的关键观察点，建议重点跟踪下一报告期的修复进展。</div></div>
      <div class="fr-sec"><div class="fr-sec-t">四、公告信号面（巨潮资讯网 · 近24个月）</div><div class="fr-sec-b" style="margin-bottom:6px">${{sigChips}}</div><div class="fr-sec-b">${{sigTxt}}</div></div>
      ${{moyuSec}}
      ${{capHtml}}
      <div class="fr-disclaim">⚠️ 免责声明：本报告由ST股分析专家基于公开数据（巨潮资讯网、东方财富、腾讯财经）与V2十三维评分体系自动生成，仅供研究参考，不构成任何投资建议。评分与信号为动态数据，以最新公告为准。股市有风险，投资需谨慎。</div>
      <div class="fr-foot">ST保壳评分系统 V2 · 保壳风云榜 &nbsp;|&nbsp; 会员：${{m.name||'—'}} &nbsp;|&nbsp; 生成时间：${{ts}} &nbsp;|&nbsp; 报告期：${{REPORT_LABEL}}</div>
    </div>
  </div>`;
}}
function exportPDF(code){{
  const c = UNIQUE.find(x=>x.code===code);
  if(!c) return;
  const btn = document.getElementById('pdfBtn');
  const ori = btn ? btn.innerHTML : '';
  if(btn){{ btn.disabled = true; btn.innerHTML = '⏳ 正在生成正式版PDF报告…'; }}
  loadHtml2Pdf().then(() => {{
    const holder = document.createElement('div');
    holder.style.cssText = 'position:fixed;left:-10000px;top:0;background:#fff;';
    holder.innerHTML = buildFormalReport(c);
    document.body.appendChild(holder);
    const fname = 'ST保壳分析报告_'+c.code+'_'+(c.name||'').replace(/[*\\/:?<>|"]/g,'')+'.pdf';
    const opt = {{
      margin: 0,
      filename: fname,
      image: {{ type:'jpeg', quality: 0.95 }},
      html2canvas: {{ scale: 2, useCORS: true, backgroundColor: '#ffffff', windowWidth: 794 }},
      jsPDF: {{ unit:'mm', format:'a4', orientation:'portrait' }},
      pagebreak: {{ mode: ['css','legacy'], avoid: ['.fr-sec','.fr-table tr','.fr-meta'] }}
    }};
    html2pdf().set(opt).from(holder.firstElementChild).save().then(() => {{
      document.body.removeChild(holder);
      if(btn){{ btn.disabled = false; btn.innerHTML = ori; }}
    }}).catch(err => {{
      if(holder.parentNode) document.body.removeChild(holder);
      if(btn){{ btn.disabled = false; btn.innerHTML = ori; }}
      alert('PDF生成失败：'+(err&&err.message||err));
    }});
  }}).catch(() => {{
    if(btn){{ btn.disabled = false; btn.innerHTML = ori; }}
    alert('PDF引擎加载失败，请检查网络后重试');
  }});
}}

initStats();
renderRank();
renderMoyu();
renderList();
renderVoteRank();
checkHashRoute();
</script>
<div class="modal-mask" id="memMask" onclick="if(event.target===this)closeModal('memMask')">
  <div class="modal">
    <div class="modal-head"><div class="modal-title">🔐 会员专享 · ST股分析专家</div><button class="modal-close" onclick="closeModal('memMask')">✕</button></div>
    <div class="modal-body" id="memBody"></div>
  </div>
</div>
<div class="modal-mask" id="expMask" onclick="if(event.target===this)closeModal('expMask')">
  <div class="modal">
    <div class="modal-head"><div class="modal-title" id="expTitle">🧠 ST股分析专家 · 即时分析报告</div><button class="modal-close" onclick="closeModal('expMask')">✕</button></div>
    <div class="modal-body" id="expBody"></div>
  </div>
</div>
</body>
</html>'''

with open('baokeng-rank.html', 'w', encoding='utf-8') as f:
    f.write(html)

# GitHub Pages 首页同步：index.html 与 baokeng-rank.html 内容一致，
# 别人打开 https://zsheng007.github.io/baokeng-ranking/ 即可看到最新版
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Generated baokeng-rank.html + index.html ({len(html)} bytes) | ST保壳评分系统V2正式版(十三维+摸鱼榜) | 报告期: {report_label} | 公司数: {len(v2scores)}')
