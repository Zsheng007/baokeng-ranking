# -*- coding: utf-8 -*-
"""生成公众号竖版长图HTML（750px宽）——保壳风云榜V2"""
import json, math, html

BASE = "C:/Users/xiaot/WorkBuddy/2026-05-16-task-2"
d = json.load(open(f"{BASE}/st_scores_v2.json", encoding="utf-8"))
rows = d["data"]
meta = d["meta"]

# ---------- 统计 ----------
levels = {"A": 0, "B": 0, "C": 0, "D": 0}
for r in rows:
    levels[r["level"]] = levels.get(r["level"], 0) + 1
n_total = len(rows)

# ---------- 摸鱼指数（复刻页面端公式） ----------
pool = [r for r in rows if not r.get("delisted") and (r.get("market_cap_yi") or 0) > 0]
caps = [r["market_cap_yi"] for r in pool]
cap_min, cap_max = min(caps), max(caps)
LOG_MAX, LOG_MIN = math.log(cap_max), math.log(cap_min)
COEF = {"A": 1.0, "B": 1.0, "C": 0.85, "D": 0.6}

for r in pool:
    cheap = 100 * (LOG_MAX - math.log(r["market_cap_yi"])) / (LOG_MAX - LOG_MIN)
    r["moyu"] = round((0.5 * r["total"] + 0.5 * cheap) * COEF[r["level"]], 1)

moyu_top = sorted(pool, key=lambda x: -x["moyu"])[:10]
easy_top = sorted(rows, key=lambda x: (-x["total"], x["rank"]))[:10]
hard_bottom = sorted([r for r in rows if not r.get("delisted")], key=lambda x: x["total"])[:10]
c2_full = [r for r in pool if r["C2"] == 8]

gen_date = meta.get("generated_at", "")[:10]
rpt = "2025年报" if meta.get("report_date") == "20251231" else meta.get("report_date", "")

esc = html.escape

def fmt_row(i, r, extra=""):
    lv_color = {"A": "#2E7D32", "B": "#558B2F", "C": "#E65100", "D": "#C62828"}[r["level"]]
    return f'''<tr>
<td class="rk">{i}</td>
<td class="nm">{esc(r['name'])}<span class="cd">{r['code']}</span></td>
<td class="ex">{extra}</td>
<td class="lv" style="color:{lv_color}">{r['level']}</td>
<td class="sc" style="color:{lv_color}">{r['total']}</td>
</tr>'''


def build_table(title, sub, rows_data, extra_fn):
    trs = "\n".join(fmt_row(i + 1, r, extra_fn(r)) for i, r in enumerate(rows_data))
    return f'''<div class="card">
<div class="ct">{title}<span class="cs">{sub}</span></div>
<table><thead><tr><th>排名</th><th>公司</th><th style="text-align:right">{extra_fn(None) if extra_fn.__name__ != 'x' else ''}</th><th>等级</th><th>得分</th></tr></thead>
<tbody>{trs}</tbody></table>
</div>'''


def cap_extra(r):  # noqa
    return f"{r['market_cap_yi']:.1f}亿" if r.get("market_cap_yi") else "—"


def ctrl_extra(r):
    return esc(r.get("controller_cat") or "—")


def moyu_extra(r):
    return f"{r['moyu']}"


def x(r):  # placeholder
    return ""


extra_labels = {"cap": "市值", "ctrl": "实控人", "moyu": "摸鱼指数"}


def table_block(title, sub, rows_data, extra_fn, extra_label):
    lv_map = {"A": "#2E7D32", "B": "#558B2F", "C": "#E65100", "D": "#C62828"}
    trs = []
    for i, r in enumerate(rows_data):
        lv_color = lv_map[r["level"]]
        trs.append(f'''<div class="row">
<div class="rk">{i+1}</div>
<div class="nm">{esc(r['name'])}<span class="cd">{r['code']}</span></div>
<div class="ex">{extra_fn(r)}</div>
<div class="lv" style="background:{lv_color}">{r['level']}</div>
<div class="sc" style="color:{lv_color}">{r['total']}</div>
</div>''')
    trs = "\n".join(trs)
    return f'''<div class="card">
<div class="ct">{title}<span class="cs">{sub}</span></div>
<div class="thead"><span>排名</span><span>公司</span><span style="text-align:right">{extra_label}</span><span>等级</span><span>得分</span></div>
{trs}
</div>'''


# ---------- 等级分布条 ----------
lv_desc = {"A": "保壳无忧（>70）", "B": "保壳较稳（51-70）", "C": "保壳承压（31-50）", "D": "退市高危（≤30）"}
lv_colors = {"A": "#2E7D32", "B": "#639922", "C": "#E8920A", "D": "#C62828"}
dist_rows = "\n".join(
    f'''<div class="dist"><span class="dl" style="background:{lv_colors[k]}">{k}</span>
<span class="dn">{lv_desc[k]}</span><div class="bar"><i style="width:{levels[k]/n_total*100:.0f}%;background:{lv_colors[k]}"></i></div>
<span class="dv">{levels[k]}家</span></div>'''
    for k in "ABCD")

# ---------- 五通道权重 ----------
chans = [("市场类", 14, "面值·壳价值"), ("财务红线", 32, "净资产·营收·扣非·现金流"),
         ("监管类", 22, "立案造假·审计意见"), ("股东调节", 18, "实控人·质押·司法"),
         ("纾困类", 14, "重组·趋势")]
chans_html = "\n".join(
    f'<div class="ch"><div class="chn">{n}<i>{d}</i></div><div class="bar2"><i style="width:{w*2.5}%;background:linear-gradient(90deg,#639922,#97C45B)"></i></div><span class="chv">{w}%</span></div>'
    for n, w, d in chans)

# ---------- C2并购机会区名单（前10） ----------
c2_sorted = sorted(c2_full, key=lambda r: r["market_cap_yi"])[:10]
c2_names = "、".join(f"{esc(r['name'])}({r['market_cap_yi']:.1f}亿)" for r in c2_sorted[:6])

html_doc = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ width:750px; font-family:"Noto Sans SC","Microsoft YaHei",sans-serif; background:#F5F8EF; color:#2B3A1A; }}
.hero {{ background:linear-gradient(135deg,#3B6D11 0%,#639922 60%,#97C45B 100%); padding:64px 40px 52px; text-align:center; }}
.hero .tag {{ display:inline-block; border:1px solid rgba(255,255,255,.5); color:#fff; font-size:22px; padding:6px 22px; border-radius:999px; letter-spacing:2px; margin-bottom:26px; }}
.hero h1 {{ color:#fff; font-size:64px; letter-spacing:8px; font-weight:800; }}
.hero h2 {{ color:#EFF7E2; font-size:26px; font-weight:400; margin-top:18px; letter-spacing:2px; }}
.hero .meta {{ color:rgba(255,255,255,.85); font-size:20px; margin-top:26px; }}
.stats {{ display:flex; padding:28px 30px; gap:14px; background:#fff; margin:-30px 24px 24px; border-radius:16px; box-shadow:0 6px 24px rgba(59,109,17,.14); position:relative; }}
.st {{ flex:1; text-align:center; }}
.st b {{ display:block; font-size:44px; color:#3B6D11; font-weight:800; }}
.st i {{ font-style:normal; font-size:19px; color:#7B8A6A; }}
.card {{ background:#fff; margin:0 24px 24px; border-radius:16px; padding:30px 28px 22px; box-shadow:0 4px 18px rgba(59,109,17,.10); }}
.ct {{ font-size:34px; font-weight:800; color:#3B6D11; margin-bottom:6px; }}
.ct .cs {{ display:block; font-size:20px; color:#8A9A78; font-weight:400; margin-top:6px; }}
.dist {{ display:flex; align-items:center; gap:12px; padding:9px 0; }}
.dl {{ width:40px; height:40px; border-radius:10px; color:#fff; font-size:22px; font-weight:800; display:flex; align-items:center; justify-content:center; }}
.dn {{ width:210px; font-size:21px; }}
.bar {{ flex:1; height:16px; background:#EDF2E4; border-radius:8px; overflow:hidden; }}
.bar i {{ display:block; height:100%; }}
.dv {{ width:76px; text-align:right; font-size:21px; font-weight:700; }}
.thead {{ display:flex; align-items:center; padding:14px 0 8px; border-bottom:2px solid #E8EFDC; color:#8A9A78; font-size:18px; }}
.row {{ display:flex; align-items:center; padding:13px 0; border-bottom:1px solid #F0F4E8; font-size:22px; }}
.thead span:nth-child(1) {{ width:70px; }}
.row .rk {{ width:70px; color:#97A88A; font-weight:700; }}
.row .nm {{ flex:1; font-weight:700; }}
.row .cd {{ font-size:17px; color:#A0AE8E; font-weight:400; margin-left:10px; }}
.row .ex {{ width:170px; text-align:right; color:#5C6B4A; font-size:20px; }}
.row .lv {{ width:48px; height:34px; margin:0 12px 0 20px; border-radius:8px; color:#fff; font-size:18px; font-weight:800; display:flex; align-items:center; justify-content:center; }}
.row .sc {{ width:76px; text-align:right; font-size:26px; font-weight:800; }}
.ch {{ display:flex; align-items:center; gap:14px; padding:10px 0; }}
.chn {{ width:160px; font-size:22px; font-weight:700; }}
.chn i {{ display:block; font-style:normal; font-size:16px; color:#97A88A; font-weight:400; }}
.bar2 {{ flex:1; height:14px; background:#EDF2E4; border-radius:7px; }}
.bar2 i {{ display:block; height:100%; border-radius:7px; }}
.chv {{ width:64px; text-align:right; font-size:22px; font-weight:800; color:#3B6D11; }}
.note {{ font-size:20px; color:#5C6B4A; line-height:1.7; padding:6px 0; }}
.c2box {{ margin:14px 24px; background:linear-gradient(135deg,#EFF7E2,#FDFEF8); border:1px dashed #97C45B; border-radius:16px; padding:24px 28px; }}
.c2box b {{ color:#3B6D11; font-size:24px; }}
.c2box p {{ font-size:20px; color:#5C6B4A; line-height:1.7; margin-top:8px; }}
.foot {{ background:#3B6D11; margin-top:8px; padding:48px 40px 36px; text-align:center; }}
.foot h3 {{ color:#fff; font-size:30px; letter-spacing:2px; }}
.foot p {{ color:rgba(255,255,255,.85); font-size:20px; margin-top:14px; line-height:1.7; }}
.foot .go {{ display:inline-block; margin-top:24px; background:#fff; color:#3B6D11; font-size:24px; font-weight:800; padding:14px 44px; border-radius:999px; }}
.disclaim {{ background:#EAF0DF; padding:26px 30px 34px; font-size:16px; color:#8A9A78; line-height:1.8; }}
</style></head><body>

<div class="hero">
<div class="tag">V2 · 十三维 · 100分制</div>
<h1>保壳风云榜</h1>
<h2>A股 ST/*ST 全市场退市风险横评</h2>
<div class="meta">覆盖 {n_total} 家 · 财务基准 {rpt} · 生成日期 {gen_date} · 每周五更新</div>
</div>

<div class="stats">
<div class="st"><b>{n_total}</b><i>覆盖ST/*ST公司</i></div>
<div class="st"><b>13</b><i>评分维度</i></div>
<div class="st"><b>{len(c2_full)}</b><i>并购机会区标的</i></div>
<div class="st"><b>176</b><i>退市案例回测样本</i></div>
</div>

<div class="card">
<div class="ct">等级分布<span class="cs">分数越高 = 保壳越容易</span></div>
{dist_rows}
</div>

{table_block("保壳最容易 TOP 10", "国资背景 + 财务达标 + 无监管雷区", easy_top, ctrl_extra, "实控人")}

{table_block("摸鱼指数 TOP 10", "壳便宜 × 保壳稳 —— 低成本并购视角", moyu_top, moyu_extra, "摸鱼指数")}

{table_block("保壳最难 TOP 10", "临近面值/财务红线/监管高压，退市高危区", hard_bottom, cap_extra, "市值")}

<div class="card">
<div class="ct">评分体系<span class="cs">五通道权重 = 5年176家退市案例实证贡献度</span></div>
{chans_html}
<div class="note" style="margin-top:12px">十三维：C1面值6 · C2壳价值8 · S1实控人12 · S2质押6 · A1净资产10 · A2扣非主营收入12 · A3扣非6 · D1现金流4 · B1立案造假10 · B2审计12 · F2重组6 · F1趋势4 · H1司法4；联动闸门：面值危机压制壳价值、涉造假立案实控人维度封顶。</div>
</div>

<div class="c2box">
<b>并购机会区（C2满分，{len(c2_full)}家）</b>
<p>市值 ≤ 16.9亿（壳基准33.8亿的五折）：{c2_names} 等。壳价值评分规则反转——市值越低于壳基准，并购重组的机会弹性越大。</p>
</div>

<div class="foot">
<h3>完整榜单 · 个股保壳报告 · 摸鱼榜</h3>
<p>全市场207家排序 / 通道封顶预警 / 点击个股看13维明细</p>
<div class="go">点击文末「阅读原文」查看 →</div>
</div>

<div class="disclaim">
免责声明：本榜单基于公开数据（巨潮公告、交易所行情、AkShare财务数据）自动量化生成，评分仅供研究参考，不构成任何投资建议。ST/*ST股票退市风险高、流动性差，数据可能存在滞后或口径差异，请以交易所及上市公司正式披露为准。据此操作，风险自担。
</div>

</body></html>'''

open(f"{BASE}/poster_gzh.html", "w", encoding="utf-8").write(html_doc)
print("OK poster_gzh.html")
print(f"等级分布: {levels} | 摸鱼TOP3: {[(r['name'], r['moyu']) for r in moyu_top[:3]]}")
print(f"保壳最难TOP3: {[(r['name'], r['total']) for r in hard_bottom[:3]]}")
print(f"C2满分: {len(c2_full)}家")
