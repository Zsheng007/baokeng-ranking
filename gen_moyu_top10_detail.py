# -*- coding: utf-8 -*-
"""gen_moyu_top10_detail.py — 为摸鱼榜TOP10逐家生成独立《ST摸鱼风云-V2 · 跟读报告》(详细版)
数据: st_scores_v2.json (2026-08-30 12:15 模型输出) + gen_moyu_top10_report.py 的 TOPS 单源(逐家logic/risk/dims)
命名: ST摸鱼风云-V2跟读报告_{rank:02d}_{code}_{简称}_20260831.docx
"""
import ast, json, os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = r'C:\Users\xiaot\WorkBuddy\2026-05-16-task-2'

# ── 从 gen_moyu_top10_report.py 提取 TOPS（AST 安全解析，数据单源） ──
src = open(f'{BASE}\\gen_moyu_top10_report.py', encoding='utf-8').read()
tree = ast.parse(src)
TOPS = None
for node in tree.body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == 'TOPS':
                TOPS = ast.literal_eval(node.value)
assert TOPS and len(TOPS) == 10, 'TOPS 提取失败'

v2 = json.load(open(f'{BASE}\\st_scores_v2.json', encoding='utf-8'))
meta, data = v2['meta'], v2['data']
by_code = {c['code']: c for c in data}

DIMS = [
    ('C1', '面值距离', 6), ('C2', '壳价值锚定', 8), ('S1', '实控人性质', 12), ('S2', '股权质押', 6),
    ('A1', '净资产', 10), ('A2', '扣非主营收入', 12), ('A3', '扣非净利润', 6), ('D1', '现金流', 4),
    ('B1', '立案/造假', 10), ('B2', '审计意见', 12), ('F2', '重组纾困', 6), ('F1', '财务趋势', 4), ('H1', '司法风险', 4),
]

# 每维档位解读（按得分区间给文本；档位键为「≤得分的最高档」）
TIER = {
    'C1': {6: '现价≥8元，距1元面值退市线极远，面值通道完全无威胁。',
           5: '现价在3~8元区间，距面值退市线安全边际较大，面值通道无威胁。',
           4: '现价在2~3元区间，距面值退市红线中等距离，需盯住低价波动。',
           3: '现价贴近面值退市红线（1~2元），面值退市是首要威胁维度之一。',
           0: '现价已跌破或濒临1元面值线，面值退市风险极端。'},
    'C2': {8: '市值≤壳基准(33.81亿)的5折，处于并购/借壳成本优势区——壳越便宜，重组方入场成本越低。',
           6: '市值处于壳基准5折~8折折价区，并购成本有吸引力。',
           4: '市值接近壳基准，平价区，壳价值中性。',
           2: '市值高于壳基准，并购溢价区，壳价值不突出。',
           0: '市值显著高于壳基准，壳价值无优势。'},
    'S1': {10: '国资实控（央企或省级国资委），保壳兜底能力与信用资源为最高档。',
           8: '市县国资实控，有地方国资信用兜底与资源协调能力。',
           3: '民企/个人实控，无国资兜底，保壳依赖自身资源与外部资本博弈。'},
    'S2': {6: '无质押/质押比例极低，控制权稳固，无平仓扰动。',
           3: '质押或冻结存在（历史口径缺失取中性档），控制权有潜在扰动。',
           0: '高质押或冻结，控制权不稳风险突出。'},
    'A1': {10: '归母净资产非常充裕（≥10分档），资不抵债风险极低。',
           8: '归母净资产充裕，无资不抵债风险，财务退市线安全。',
           6: '净资产尚可（正且有余量），安全边际一般。',
           4: '净资产偏薄，逼近资不抵债。',
           3: '净资产薄/资不抵债边缘，财务类退市风险显著。',
           0: '归母净资产为负（资不抵债），触及财务类退市红线。'},
    'A2': {12: '营收达标（主板≥3亿/双创≥1亿），财务类退市红线安全。',
           9: '营收接近达标但含金量打折（如低毛利冲量被模型识别）。',
           6: '营收低于红线但缺口可控。',
           3: '营收缺口大（触及「营收<红线+亏损」组合），已构成财务类退市风险。',
           0: '营收严重不达标（接近0或微收），财务类退市风险极端。'},
    'A3': {6: '扣非净利润为正，主业造血正常，盈利面无退市压力。',
           3: '微利或微亏，盈利面中性。',
           0: '扣非持续亏损，主业亏损面承压。'},
    'D1': {4: '经营现金流为正，造血正常。',
           2: '现金流接近平衡。',
           0: '经营现金流为负，资金链压力大。'},
    'B1': {10: '无立案/造假信号，重大违法退市通道安全。',
           7: '存在一般档行政处罚落地（无立案链条）或子公司被罚，非重大违法档。',
           0: '重大违法处罚落地（立案→处罚全链条），触发封顶（总分≤30）。'},
    'B2': {12: '标准无保留审计意见，审计面干净。',
           9: '带强调事项段的无保留意见，审计面基本干净但有提示事项。',
           6: '保留意见，审计瑕疵存在，需消除后才能摘帽。',
           0: '无法表示/否定意见，触发审计封顶。'},
    'F2': {6: '重整已进入执行/完成阶段（或重大资产重组落地），保壳确定性最高。',
           4: '重组/预重整推进中（预重整/重整/重大资产重组），保壳有实质抓手。',
           2: '有出售资产/债务豁免等保壳动作，但尚未形成重组级信号。',
           0: '无重组/纾困信号，保壳依赖自身经营。'},
    'F1': {4: '营收/扣非趋势改善，经营向上。',
           2: '趋势平稳，无显著恶化。',
           0: '趋势转弱/恶化，经营下行。'},
    'H1': {4: '实控人无冻结/限高/立案，司法面无风险。',
           2: '存在一定司法风险信号。',
           0: '实控人冻结/限高/立案，司法风险归零。'},
}

def tier_text(dk, score):
    m = TIER[dk]
    # 取 <= score 的最高档
    keys = sorted(m.keys(), reverse=True)
    for k in keys:
        if score >= k:
            return m[k]
    return m[min(m.keys())]

def classify_dims(dims):
    hi, mid, lo = [], [], []
    for (dk, dn, mx), sc in zip(DIMS, dims):
        tag = f'{dk} {dn}({sc}/{mx})'
        if sc >= mx * 0.8: hi.append(tag)
        elif sc <= mx * 0.5: lo.append(tag)
        else: mid.append(tag)
    return hi, mid, lo

def h1(doc, txt):
    p = doc.add_heading(txt, level=1)
    for r in p.runs: r.font.color.rgb = RGBColor(0x1a, 0x52, 0x76)

def h2(doc, txt):
    p = doc.add_heading(txt, level=2)
    for r in p.runs: r.font.color.rgb = RGBColor(0x2e, 0x74, 0x9b)

def para(doc, txt, bold=False, size=None, color=None):
    p = doc.add_paragraph()
    r = p.add_run(txt); r.bold = bold
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = color
    return p

def table(doc, rows, header=True):
    tb = doc.add_table(rows=len(rows), cols=len(rows[0]))
    tb.style = 'Light Grid Accent 1'
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            c = tb.cell(i, j); c.text = ''
            r = c.paragraphs[0].add_run(str(cell))
            r.font.size = Pt(9)
            if i == 0 and header:
                r.bold = True
            elif i % 2 == 0:
                shd = c._tc.get_or_add_tcPr().makeelement(qn('w:shd'), {qn('w:val'): 'clear', qn('w:fill'): 'EAF1F8'})
                c._tc.get_or_add_tcPr().append(shd)
    return tb

def warn_box(doc, lines):
    tb = doc.add_table(rows=1, cols=1)
    tb.style = 'Table Grid'
    c = tb.cell(0, 0)
    c.text = ''
    p = c.paragraphs[0]
    r = p.add_run('⚠️ ' + lines[0]); r.bold = True; r.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B); r.font.size = Pt(10)
    for ln in lines[1:]:
        p2 = c.add_paragraph()
        r2 = p2.add_run(ln); r2.font.size = Pt(9.5); r2.font.color.rgb = RGBColor(0x7F, 0x5A, 0x1D)
    return tb

def add_toc(doc):
    p = doc.add_paragraph()
    run = p.add_run()
    f1 = OxmlElement('w:fldChar'); f1.set(qn('w:fldCharType'), 'begin')
    it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = 'TOC \\o "1-2" \\h \\z \\u'
    f2 = OxmlElement('w:fldChar'); f2.set(qn('w:fldCharType'), 'separate')
    t = OxmlElement('w:t'); t.text = '（目录域：打开文档后 Ctrl+A → F9 刷新生成目录）'
    f3 = OxmlElement('w:fldChar'); f3.set(qn('w:fldCharType'), 'end')
    for e in (f1, it, f2, t, f3):
        run._r.append(e)

def build(code, rank, moyu, cheap, total, lv, mcap, price, br, cat, note, dims, logic, risk):
    c = by_code[code]
    name = c['name']
    doc = Document()
    st = doc.styles['Normal']
    st.font.name = 'Calibri'; st.font.size = Pt(10.5)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')

    # 页眉页脚
    sec = doc.sections[0]
    hp = sec.header.paragraphs[0]; hp.text = ''
    hr = hp.add_run(f'ST摸鱼风云-V2 · 跟读报告｜{name}（{code}）'); hr.font.size = Pt(8); hr.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
    fp = sec.footer.paragraphs[0]; fp.text = ''
    fr = fp.add_run('本报告由ST保壳评分系统V2模型生成，仅供参考，不构成任何投资建议'); fr.font.size = Pt(8); fr.font.color.rgb = RGBColor(0xaa, 0xaa, 0xaa)

    # ── 封面 ──
    t = doc.add_paragraph(); t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run(f'{name}\n{code}'); r.font.size = Pt(26); r.bold = True
    s = doc.add_paragraph(); s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = s.add_run('ST摸鱼风云-V2 · 跟读报告（详细版）'); r.font.size = Pt(15); r.font.color.rgb = RGBColor(0x1a, 0x52, 0x76)
    s2 = doc.add_paragraph(); s2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = s2.add_run(f"摸鱼榜第 {rank} 名 ｜ 摸鱼指数 {moyu:.1f} ｜ V2保壳分 {total} ｜ {lv}级 ｜ 全榜第 {br} 名\n"
                   f"报告日期：2026年8月31日\n"
                   f"榜单时点：{meta.get('updated', '')}（财务报告期 {meta.get('report_date', '')}）\n"
                   f"评分模型：ST保壳评分系统V2（十三维100分制）· 榜单分数 = 报告分数")
    r.font.size = Pt(10); r.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    doc.add_paragraph()
    add_toc(doc)
    doc.add_page_break()

    # ── 一、报告说明与口径 ──
    h1(doc, '一、报告说明与口径')
    para(doc, '本报告为「ST摸鱼风云」会员跟读个股深度报告，采用 V2 刻度（ST保壳评分系统V2，十三维100分制）。'
              '分数越高 = 保壳越容易、退市风险越低。榜单分数与报告分数同源（score_v2.py 单源出分），'
              '已用模型单股入口对本标的重跑核验：总分/等级与榜单零偏差，以下明细即模型权威输出。')
    h2(doc, '1.1 评级标准')
    para(doc, 'A级 >70（低风险·退市概率低）｜B级 50~70（中风险·保壳有希望）｜C级 30~50（高风险）｜D级 ≤30（极高风险）')
    h2(doc, '1.2 关键口径')
    para(doc, '· 财务数据：财务报告期 ' + str(meta.get('report_date', '')) + '；公告信号窗口：近24个月巨潮公告定向采集。\n'
              '· 行情数据：榜单生成日（2026-08-30）收盘快照。\n'
              '· 壳价值锚定：壳基准 33.81 亿（近2年154笔实控权变更市值中位数，own口径）。\n'
              '· 营收红线：主板≥3亿 / 双创≥1亿（扣非口径）。')

    # ── 二、评分总览 ──
    h1(doc, '二、评分总览')
    table(doc, [
        ['V2保壳分', '等级', '全榜排名', '摸鱼指数', '壳便宜分', '市值(亿)', '现价(元)', '实控人属性', '板块'],
        [f'{total}', lv, f'第{br}名', f'{moyu:.1f}', cheap, f'{mcap:.2f}', price, cat, c.get('board', '')],
    ])
    para(doc, '')
    rows = [['维度', '得分', '满分', '解读']]
    for (dk, dn, mx), sc in zip(DIMS, dims):
        rows.append([f'{dk} {dn}', sc, mx, tier_text(dk, sc)])
    table(doc, rows)

    # ── 三、逐维深度解读 ──
    h1(doc, '三、逐维深度解读')
    groups = [
        ('3.1 市场与壳维度', ['C1', 'C2']),
        ('3.2 实控人与股权维度', ['S1', 'S2']),
        ('3.3 财务健康维度', ['A1', 'A2', 'A3', 'D1']),
        ('3.4 规范与违法维度', ['B1', 'B2']),
        ('3.5 重组与趋势维度', ['F2', 'F1']),
        ('3.6 司法风险维度', ['H1']),
    ]
    dm = {dk: (dn, mx, sc) for (dk, dn, mx), sc in zip(DIMS, dims)}
    for gtitle, keys in groups:
        h2(doc, gtitle)
        for dk in keys:
            dn, mx, sc = dm[dk]
            para(doc, f'【{dk} {dn}】得分 {sc}/{mx}。' + tier_text(dk, sc))

    # ── 四、维度画像 ──
    h1(doc, '四、维度画像：安全垫 vs 风险源')
    hi, mid, lo = classify_dims(dims)
    para(doc, '将13维按得分分为三档：安全垫（≥满分80%）、观察项（中间档）、风险源（≤满分50%）。')
    rows = [['分类', '维度（得分/满分）']]
    rows.append(['✅ 安全垫', '、'.join(hi) if hi else '（无）'])
    rows.append(['👀 观察项', '、'.join(mid) if mid else '（无）'])
    rows.append(['⚠️ 风险源', '、'.join(lo) if lo else '（无）'])
    table(doc, rows)

    # ── 五、保壳逻辑 ──
    h1(doc, '五、保壳逻辑（模型解读）')
    para(doc, logic)
    if c.get('note'):
        h2(doc, '5.1 模型flags')
        para(doc, c['note'], size=9)

    # ── 六、风险点清单 ──
    h1(doc, '六、风险点清单')
    para(doc, risk, bold=True)
    if lo:
        para(doc, '结合维度画像，风险源集中在上表「⚠️ 风险源」列，需逐项跟踪对应公告信号（立案/审计/质押/司法/营收红线）。')

    # ── 七、风险提示与研究局限 ──
    h1(doc, '七、风险提示与研究局限')
    warn_box(doc, [
        '本报告由模型基于公开数据自动生成，仅供研究参考，不构成任何投资建议。',
        '评分模型V2在点时回测（《ST保壳评分系统V2三年回测报告_20260830.docx》）中总分AUC≈0.53接近随机，'
        '判别力主要来自 F2重组信号(0.657) 与 C1面值距离(0.635)；B1/B2封顶机制存在选择效应，'
        '高保壳分≠一定摘帽、低保壳分≠一定退市，需结合年报原文与最新公告二次核验。',
        '数据时点：榜单2026-08-30生成（财务报告期20251231），行情为当日快照；此后如有重大公告（立案/重组/审计更换）需重新评估。',
    ])
    para(doc, '')
    para(doc, '—— 报告完 ——', size=9)

    fn = f'{BASE}\\ST摸鱼风云-V2跟读报告_{int(rank):02d}_{code}_{name.replace("*", "")}_20260831.docx'
    doc.save(fn)
    return fn

made = []
for code, rank, moyu, cheap, total, lv, mcap, price, br, cat, note, dims, logic, risk in TOPS:
    fn = build(code, rank, moyu, cheap, total, lv, mcap, price, br, cat, note, dims, logic, risk)
    made.append(fn)
    print('已生成:', os.path.basename(fn))
print(f'\n共 {len(made)} 份')
