#!/usr/bin/env python3
"""Generate baokeng-rank.html from V618 scores (分数越高=保壳越容易)"""

import json
from datetime import date

with open('st_scores.json', encoding='utf-8') as f:
    scores = json.load(f)

active = [s for s in scores if not s['delisted']]

# Count stats
stats = {'A':0,'B':0,'C':0,'D':0}
for s in active: stats[s['level']] += 1

# Top lists (scores already sorted descending: highest = easiest first)
easy10 = scores[:10]
hard10 = scores[-10:][::-1]  # lowest scores = hardest

# Colors
LC = {'A':'#27ae60','B':'#2980b9','C':'#e67e22','D':'#c0392b'}
LT = {'A':'低风险·退市概率低','B':'中风险·保壳有希望','C':'高风险·保壳难度大','D':'极高风险·退市警钟'}
LE = {'A':'✅ 综合评估：保壳能力较强','B':'🔵 综合评估：中等退市风险','C':'🟠 综合评估：较高退市风险','D':'🔴 综合评估：退市风险极高'}

today = date.today().isoformat()

# Generate RAW data array
raw_lines = []
for s in scores:
    raw_lines.append(
        f'  ["{s["code"]}","{s["name"]}","{s["type"]}","{s["board"]}","{s["reason"]}",'
        f'{s["A1"]},{s["A2"]},{s["A3"]},{s["B1"]},{s["B2"]},{s["B3"]},'
        f'{s["C1"]},{s["D1"]},{s["E1"]},{s["F1"]},{str(s["delisted"]).lower()},'
        f'"{s["note"]}"]'
    )
raw_str = '[\n' + ',\n'.join(raw_lines) + '\n]'

# JS for scoring: 所有维度之和 = 保壳能力总分（越高越好）
# Map: score = A1+A2+A3+B1+B2+B3+C1+D1+E1+F1

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>保壳风云榜 · A股退市风险评估 V618</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #f0f7f2; color: #1a2b1f; font-size: 14px; }}

/* 头部 */
.header {{ background: linear-gradient(135deg, #1a3d2b 0%, #0f2519 100%); color: #fff; padding: 22px 24px 16px; border-bottom: 2px solid #2d6e47; }}
.header-inner {{ max-width: 1200px; margin: 0 auto; }}
.header h1 {{ font-size: 24px; font-weight: 600; letter-spacing: 2px; display: flex; align-items: center; gap: 10px; }}
.header p {{ font-size: 13px; color: #7dbf96; margin-top: 4px; }}
.header-meta {{ display: flex; gap: 12px; margin-top: 12px; flex-wrap: wrap; }}
.header-meta span {{ font-size: 12px; background: rgba(255,255,255,0.1); padding: 3px 10px; border-radius: 20px; color: #a8d8b8; border: 0.5px solid rgba(255,255,255,0.15); }}

/* 主容器 */
.container {{ max-width: 1200px; margin: 0 auto; padding: 20px 16px; }}

/* 评分体系说明 */
.score-legend {{ background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; padding: 16px 20px; margin-bottom: 20px; }}
.score-legend h3 {{ font-size: 14px; font-weight: 600; color: #1a3d2b; margin-bottom: 8px; }}
.score-legend-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; }}
.slg-item {{ font-size: 11px; padding: 8px; background: #f4fbf6; border-radius: 8px; text-align: center; }}
.slg-dim {{ font-weight: 600; color: #1a5e35; }}
.slg-weight {{ color: #999; font-size: 10px; }}

/* 统计卡片 */
.stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }}
.stat-card {{ background: #fff; border-radius: 12px; padding: 16px 12px; border: 0.5px solid #c8e6d0; text-align: center; }}
.stat-num {{ font-size: 32px; font-weight: 700; margin-bottom: 4px; }}
.stat-label {{ font-size: 11px; color: #6b8a75; }}
.stat-card.lv-D .stat-num {{ color: #c0392b; }}
.stat-card.lv-C .stat-num {{ color: #d35400; }}
.stat-card.lv-B .stat-num {{ color: #1a6b3a; }}
.stat-card.lv-A .stat-num {{ color: #27ae60; }}

/* Tab */
.tabs {{ display: flex; background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; margin-bottom: 20px; overflow: hidden; }}
.tab {{ flex: 1; padding: 12px 8px; text-align: center; font-size: 13px; cursor: pointer; border: none; background: transparent; color: #5a7a64; font-weight: 500; border-bottom: 2px solid transparent; transition: all 0.2s; }}
.tab.active {{ color: #1a5e35; border-bottom-color: #27ae60; background: #edf7f1; }}
.tab:hover:not(.active) {{ background: #f4fbf6; }}

.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

/* 排行榜 */
.rank-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
.rank-panel {{ background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; overflow: hidden; }}
.rank-header-easy {{ padding: 14px 16px; border-bottom: 0.5px solid #c8e6d0; background: #edf7f1; }}
.rank-header-hard {{ padding: 14px 16px; border-bottom: 0.5px solid #fad5d0; background: #fdf3f1; }}
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

/* 风险标签 */
.rtag {{ font-size: 10px; padding: 1px 6px; border-radius: 8px; margin-left: 5px; flex-shrink: 0; }}
.rtag-A {{ background: #d5f5e3; color: #1a6b3a; }}
.rtag-B {{ background: #d6eaf8; color: #1a5276; }}
.rtag-C {{ background: #fde8d8; color: #a04000; }}
.rtag-D {{ background: #fadbd8; color: #922b21; }}

/* 查询区 */
.search-box {{ background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; padding: 20px; }}
.search-row {{ display: flex; gap: 10px; margin-bottom: 16px; }}
.search-input {{ flex: 1; padding: 10px 14px; border: 0.5px solid #a8d8b8; border-radius: 8px; font-size: 14px; outline: none; background: #f8fcf9; }}
.search-input:focus {{ border-color: #27ae60; box-shadow: 0 0 0 2px rgba(39,174,96,0.15); }}
.search-btn {{ padding: 10px 22px; background: #1a5e35; color: #fff; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; }}
.search-btn:hover {{ background: #1e7a44; }}

/* 详情报告 */
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

.factors-section {{ margin-bottom: 14px; }}
.factors-title {{ font-size: 12px; color: #5a7a64; font-weight: 500; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 0.5px solid #e8f5ec; }}
.factor-row {{ display: flex; align-items: center; gap: 10px; padding: 5px 0; }}
.factor-label {{ width: 140px; font-size: 12px; color: #555; flex-shrink: 0; }}
.factor-bar-wrap {{ flex: 1; height: 6px; background: #e8f5ec; border-radius: 3px; }}
.factor-bar {{ height: 6px; border-radius: 3px; transition: width 0.4s; }}
.factor-score {{ width: 32px; text-align: right; font-size: 12px; font-weight: 600; }}

.conclusion-box {{ padding: 12px 14px; border-radius: 8px; margin-top: 12px; }}
.conclusion-box.A {{ background: #d5f5e3; border-left: 3px solid #27ae60; }}
.conclusion-box.B {{ background: #d6eaf8; border-left: 3px solid #2980b9; }}
.conclusion-box.C {{ background: #fde8d8; border-left: 3px solid #e67e22; }}
.conclusion-box.D {{ background: #fadbd8; border-left: 3px solid #c0392b; }}
.conclusion-title {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
.conclusion-text {{ font-size: 12px; line-height: 1.7; color: #444; }}

/* 全名单 */
.table-wrap {{ overflow-x: auto; background: #fff; border-radius: 12px; border: 0.5px solid #c8e6d0; }}
table {{ width: 100%; border-collapse: collapse; }}
thead th {{ background: #1a5e35; color: #fff; padding: 10px 12px; font-size: 12px; font-weight: 500; text-align: left; white-space: nowrap; }}
tbody tr {{ border-bottom: 0.5px solid #f0f9f3; cursor: pointer; transition: background 0.15s; }}
tbody tr:last-child {{ border-bottom: none; }}
tbody tr:hover {{ background: #f4fbf6; }}
tbody td {{ padding: 9px 12px; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.link-style {{ color: #1a5e35; cursor: pointer; }}

/* 筛选 */
.filter-row {{ display: flex; gap: 8px; padding: 12px 16px; background: #edf7f1; border-bottom: 0.5px solid #c8e6d0; flex-wrap: wrap; }}
.filter-chip {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; cursor: pointer; border: 1px solid #c8e6d0; background: #fff; color: #5a7a64; transition: all 0.15s; }}
.filter-chip.active {{ background: #1a5e35; color: #fff; border-color: #1a5e35; }}
.filter-chip:hover:not(.active) {{ border-color: #27ae60; }}

/* 投票（公司级） */
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

/* 投票排行Tab */
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

/* 数据来源提示 */
.source-tip {{ font-size: 11px; color: #999; padding: 8px 16px; background: #fafafa; border-radius: 8px; margin-bottom: 16px; text-align: center; }}

/* 免责声明 */
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
  <h1>🌿 保壳风云榜 <span style="font-size:13px;font-weight:400;opacity:0.7">V618</span></h1>
  <p>A股 ST / *ST 上市公司保壳能力评估 · 100分制六维评分 · 实时排名</p>
  <div class="header-meta">
    <span>更新时间：{today}</span>
    <span>覆盖公司：{len(scores)} 家</span>
    <span>数据来源：沪深交易所 · 风险警示板</span>
    <span>评分模型：V618 六维100分制</span>
    <span>每周五更新</span>
  </div>
</div>
</div>

<div class="container">

  <!-- 评分体系说明 -->
  <div class="score-legend">
    <h3>📐 V618 100分制六维评分体系（分数越高=保壳能力越强）</h3>
    <div class="score-legend-grid">
      <div class="slg-item"><div class="slg-dim">A 财务健康</div><div class="slg-weight">28分</div></div>
      <div class="slg-item"><div class="slg-dim">B 治理合规</div><div class="slg-weight">25分</div></div>
      <div class="slg-item"><div class="slg-dim">C 面值/市值</div><div class="slg-weight">15分</div></div>
      <div class="slg-item"><div class="slg-dim">D 现金流质量</div><div class="slg-weight">12分</div></div>
      <div class="slg-item"><div class="slg-dim">E 股权稳定性</div><div class="slg-weight">10分</div></div>
      <div class="slg-item"><div class="slg-dim">F 持续经营</div><div class="slg-weight">10分</div></div>
    </div>
  </div>

  <div class="stats-grid">
    <div class="stat-card lv-A"><div class="stat-num">{stats["A"]}</div><div class="stat-label">A级 · 保壳能力强（>65分）</div></div>
    <div class="stat-card lv-B"><div class="stat-num">{stats["B"]}</div><div class="stat-label">B级 · 保壳有希望（46-65分）</div></div>
    <div class="stat-card lv-C"><div class="stat-num">{stats["C"]}</div><div class="stat-label">C级 · 保壳难度大（26-45分）</div></div>
    <div class="stat-card lv-D"><div class="stat-num">{stats["D"]}</div><div class="stat-label">D级 · 退市警钟（≤25分）</div></div>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('rank')">📊 风云榜</button>
    <button class="tab" onclick="switchTab('query')">🔍 查询详情</button>
    <button class="tab" onclick="switchTab('list')">📋 全名单（{len(scores)}家）</button>
    <button class="tab" onclick="switchTab('vote')">🗳️ 投票排行</button>
  </div>

  <!-- 风云榜 -->
  <div id="tab-rank" class="tab-content active">
    <div class="source-tip">📊 数据覆盖 <b>{len(scores)}</b> 家 ST/*ST 公司 · V618六维评分 100分制 · 分数越高保壳越容易 · 更新于 {today}</div>
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
    </div>
  </div>

  <!-- 查询 -->
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

  <!-- 全名单 -->
  <div id="tab-list" class="tab-content">
    <div class="source-tip"><b id="listTotal">{len(scores)}</b> 家 · 排序：按保壳能力分（分数越高保壳越容易）</div>
    <div class="filter-row">
      <span class="filter-chip active" onclick="setFilter('all',this)">全部</span>
      <span class="filter-chip" onclick="setFilter('ST',this)">ST</span>
      <span class="filter-chip" onclick="setFilter('*ST',this)">*ST</span>
      <span class="filter-chip" onclick="setFilter('A',this)">A级 >65</span>
      <span class="filter-chip" onclick="setFilter('B',this)">B级 46-65</span>
      <span class="filter-chip" onclick="setFilter('C',this)">C级 26-45</span>
      <span class="filter-chip" onclick="setFilter('D',this)">D级 ≤25</span>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th style="width:46px">排名</th>
            <th style="width:80px">代码</th>
            <th style="width:120px">简称</th>
            <th style="width:55px">类型</th>
            <th>风险原因</th>
            <th style="width:55px">保壳分</th>
            <th style="width:50px">等级</th>
            <th style="width:55px">详情</th>
          </tr>
        </thead>
        <tbody id="listBody"></tbody>
      </table>
    </div>
  </div>

  <!-- 投票排行 -->
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

  <!-- 免责声明 -->
  <div class="disclaimer">
    <h4>⚠️ 免责声明</h4>
    <p>1. 本工具仅供学习研究参考，<b>不构成任何投资建议</b>。评分模型基于公开数据和算法推断，可能存在偏差与滞后。</p>
    <p>2. 投资者应自行判断风险，<b>据此操作风险自负</b>。退市涉及复杂的财务、法律及监管因素，本工具无法全面覆盖。</p>
    <p>3. 数据来源：沪深交易所风险警示板公开名单、公开市场行情。评分模型 V618 为独立研究框架，<b>不代表任何机构观点</b>。</p>
    <p>4. 历史评分不代表未来结果，保壳能力评分仅反映基于公开信息的综合评估，不保证准确性。</p>
  </div>

</div>

<script>
// ===================== V618 保壳能力评分数据 =====================
// [代码, 简称, 类型, 板块, 风险原因, A1, A2, A3, B1, B2, B3, C1, D1, E1, F1, 已锁定退市, 备注]
// 分数越高 = 保壳能力越强
const RAW = {raw_str};

// V618 保壳能力总分 = 所有维度之和（越高越好）
function calcScore(r) {{ return r[5]+r[6]+r[7]+r[8]+r[9]+r[10]+r[11]+r[12]+r[13]+r[14]; }}

// 评级（分数越高=保壳越容易）
function calcLevel(s) {{ return s>65?'A': s>45?'B': s>25?'C': 'D'; }}

const COS = RAW.map(r => {{
  const s = calcScore(r);
  return {{ code:r[0], name:r[1], type:r[2], board:r[3], reason:r[4],
    A1:r[5], A2:r[6], A3:r[7], B1:r[8], B2:r[9], B3:r[10],
    C1:r[11], D1:r[12], E1:r[13], F1:r[14], delisted:r[15], note:r[16],
    score:s, level:calcLevel(s) }};
}});

// 去重（按代码）
const CODE_MAP = new Map();
COS.forEach(c => {{ if(!CODE_MAP.has(c.code)) CODE_MAP.set(c.code, c); }});
const UNIQUE = Array.from(CODE_MAP.values());

// 按保壳能力分降序排列（高分=容易保壳排前面）
const BY_SCORE = [...UNIQUE].sort((a,b)=>b.score-a.score);
BY_SCORE.forEach((c,i)=>c.rank=i+1);

const LC = {{'A':'#27ae60','B':'#2980b9','C':'#e67e22','D':'#c0392b'}};
const LT = {{'A':'低风险·退市概率低','B':'中风险·保壳有希望','C':'高风险·保壳难度大','D':'极高风险·退市警钟'}};
const LE = {{'A':'✅ 综合评估：保壳能力较强','B':'🔵 综合评估：中等退市风险','C':'🟠 综合评估：较高退市风险','D':'🔴 综合评估：退市风险极高'}};

let currentFilter = 'all';

// ---- 统计 ----
function initStats(){{
  try {{
    const active = UNIQUE.filter(c=>!c.delisted);
    ['A','B','C','D'].forEach(l=>{{
      const el = document.getElementById('s'+l);
      if(el) el.textContent=active.filter(c=>c.level===l).length;
    }});
  }} catch(e){{ /* stats pre-filled, non-critical */ }}
}}

// ---- 排行榜 ----
function renderRank(){{
  // BY_SCORE 已按降序排列：高分在前 = 容易保壳
  const easy = BY_SCORE.slice(0,10);
  const hard = BY_SCORE.slice(-10).reverse();
  document.getElementById('easyList').innerHTML = easy.map((c,i)=>rankItemEasy(c,i)).join('');
  document.getElementById('hardList').innerHTML = hard.map((c,i)=>rankItemHard(c,i)).join('');
}}

function numClass(i){{ return i===0?'gold':i===1?'silver':i===2?'bronze':'other'; }}
function rankItemEasy(c, i){{
  const col = LC[c.level];
  return `<div class="rank-item" onclick="gotoDetail('${{c.code}}')">
    <div class="rank-num ${{numClass(i)}}">${{i+1}}</div>
    <div class="rank-info">
      <div class="rank-name">${{c.name}}<span class="rtag rtag-${{c.level}}">${{c.level}}</span></div>
      <div class="rank-code">${{c.code}} · ${{c.board}} · ${{c.reason.length>20?c.reason.slice(0,20)+'…':c.reason}}</div>
    </div>
    <div class="rank-score-col">
      <div class="mini-bar-wrap"><div class="mini-bar" style="width:${{Math.round(c.score/80*100)}}%;background:${{col}}"></div></div>
      <div class="score-val" style="color:${{col}}">${{c.score}}</div>
    </div>
  </div>`;
}}
function rankItemHard(c, i){{
  const col = LC[c.level];
  return `<div class="rank-item" onclick="gotoDetail('${{c.code}}')">
    <div class="rank-num ${{numClass(i)}}">${{i+1}}</div>
    <div class="rank-info">
      <div class="rank-name">${{c.name}}<span class="rtag rtag-${{c.level}}">${{c.level}}</span></div>
      <div class="rank-code">${{c.code}} · ${{c.board}} · ${{c.reason.length>20?c.reason.slice(0,20)+'…':c.reason}}</div>
    </div>
    <div class="rank-score-col">
      <div class="mini-bar-wrap"><div class="mini-bar" style="width:${{Math.round(c.score/80*100)}}%;background:${{col}}"></div></div>
      <div class="score-val" style="color:${{col}}">${{c.score}}</div>
    </div>
  </div>`;
}}

// ---- 全名单 ----
function getFiltered(){{
  if(currentFilter==='all') return BY_SCORE;
  if(currentFilter==='ST') return BY_SCORE.filter(c=>c.type==='ST');
  if(currentFilter==='*ST') return BY_SCORE.filter(c=>c.type==='*ST');
  return BY_SCORE.filter(c=>c.level===currentFilter);
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
      <td>${{i+1}}</td><td>${{c.code}}</td><td>${{c.name}}</td><td>${{c.type}}</td>
      <td title="${{c.reason}}">${{c.reason.length>20?c.reason.slice(0,20)+'…':c.reason}}</td>
      <td style="font-weight:700;color:${{LC[c.level]}}">${{c.score}}</td>
      <td><span class="rtag rtag-${{c.level}}">${{c.level}}</span></td>
      <td class="link-style">查看 →</td>
    </tr>`).join('');
}}

// ---- Tab ----
function switchTab(n){{
  document.querySelectorAll('.tab').forEach((t,i)=>t.classList.toggle('active',['rank','query','list','vote'][i]===n));
  document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));
  document.getElementById('tab-'+n).classList.add('active');
  if(n==='vote') renderVoteRank();
}}

// ---- 查询 ----
function doQuery(){{
  const q = document.getElementById('qInput').value.trim();
  if(!q) return;
  let c = UNIQUE.find(x=>x.code===q);
  if(!c) c = UNIQUE.find(x=>x.name===q);
  if(!c) c = UNIQUE.find(x=>x.name.replace(/[*＊]?ST/,'').includes(q.replace(/[*＊]?ST/,'')));
  if(!c) c = UNIQUE.find(x=>q.includes(x.name.replace(/[*＊]?ST/,'')));
  if(!c){{
    const kw = q.replace(/[*＊]?ST/gi,'').trim();
    if(kw.length>=1) c = UNIQUE.find(x=>x.name.replace(/[*＊]?ST/gi,'').includes(kw));
  }}
  if(!c){{
    document.getElementById('qResult').innerHTML=`
      <div class="empty-state">
        <div style="font-size:40px;margin-bottom:10px">😕</div>
        <div style="margin-bottom:8px">未找到「<b>${{q}}</b>」</div>
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
  const factors = [
    {{label:'A1 财务健康(5)','v':c.A1,'max':5,'col':'#27ae60'}},
    {{label:'A2 营收能力(13)','v':c.A2,'max':13,'col':'#1a5e35'}},
    {{label:'A3 净资产(10)','v':c.A3,'max':10,'col':'#2980b9'}},
    {{label:'B1 合规治理(8)','v':c.B1,'max':8,'col':'#2e86c1'}},
    {{label:'B2 内控审计(7)','v':c.B2,'max':7,'col':'#27ae60'}},
    {{label:'B3 监管记录(10)','v':c.B3,'max':10,'col':'#1e8449'}},
    {{label:'C1 面值/市值(15)','v':c.C1,'max':15,'col':'#117a65'}},
    {{label:'D1 现金流质量(12)','v':c.D1,'max':12,'col':'#1a5276'}},
    {{label:'E1 股权稳定性(10)','v':c.E1,'max':10,'col':'#6c3483'}},
    {{label:'F1 持续经营(10)','v':c.F1,'max':10,'col':'#117a65'}},
  ];
  document.getElementById('qResult').innerHTML=`
    <div class="report-card">
      <div class="report-top">
        <div>
          <div class="report-name">${{c.name}}</div>
          <div class="report-sub">${{c.code}} · ${{c.board}} · ${{c.type}} <span class="rtag rtag-${{c.level}}">${{LT[c.level]}}</span></div>
        </div>
        <div style="text-align:right">
          <div class="score-big" style="color:${{col}}">${{c.score}}<span style="font-size:16px;font-weight:400"> 分</span></div>
          <div class="score-label">全榜第 ${{c.rank}} / ${{UNIQUE.length}}（越高越易保壳）</div>
        </div>
      </div>
      <div class="info-row">
        <div class="info-chip"><div class="info-chip-label">风险原因</div><div class="info-chip-val" style="font-size:11px">${{c.reason}}</div></div>
        <div class="info-chip"><div class="info-chip-label">所属板块</div><div class="info-chip-val">${{c.board}} · ${{c.type}}</div></div>
        <div class="info-chip"><div class="info-chip-label">保壳能力</div><div class="info-chip-val" style="color:${{col}}">${{c.level}} 级 · ${{c.score}}分</div></div>
        <div class="info-chip"><div class="info-chip-label">备注</div><div class="info-chip-val" style="font-size:11px">${{c.note}}</div></div>
      </div>
      <div class="factors-section">
        <div class="factors-title">V618 六维保壳能力评分明细（满分100分，得分越高保壳能力越强）</div>
        ${{factors.map(f=>`<div class="factor-row">
          <div class="factor-label">${{f.label}}</div>
          <div class="factor-bar-wrap"><div class="factor-bar" style="width:${{Math.round(f.v/f.max*100)}}%;background:${{f.col}}"></div></div>
          <div class="factor-score" style="color:${{f.col}}">${{f.v}}/${{f.max}}</div>
        </div>`).join('')}}
      </div>
      <div class="conclusion-box ${{c.level}}">
        <div class="conclusion-title">${{LE[c.level]}}</div>
        <div class="conclusion-text">${{c.note}}</div>
      </div>
    </div>
    ${{voteSectionHTML(c.code)}}`;
}}

// ---- 投票（公司级保壳难度） ----
const VK = 'bkfl_company_v1';

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

// ---- 启动 ----
initStats();
renderRank();
renderList();
renderVoteRank();
</script>
</body>
</html>'''

with open('baokeng-rank.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Generated baokeng-rank.html ({len(html)} bytes)')
