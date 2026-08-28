# 保壳风云榜 项目记忆

## 项目概述
- A股ST/*ST上市公司退市风险评估排名工具
- 纯HTML网页（baokeng-rank.html），浏览器直接打开
- 绿色主题（印象派森林色系）

## 数据来源
- 东方财富ST板块API（BK0511）获取最新ST/*ST名单
- 腾讯财经API（qt.gtimg.cn）实时行情（含市值）
- AkShare 获取真实财务数据（同花顺/东方财富）
- 当前覆盖：214家ST/*ST公司（含B股3家）

## 评分体系：ST保壳评分系统V1（2026-08-28定名；前身V618+G十一维，中间内部迭代名V7已废弃）

| 维度 | 分值 | 数据源 | 说明 |
|------|------|--------|------|
| A1 扣非净利润 | 5 | AkShare 同花顺 | 扣非净利润>0加分 |
| A2 营业收入 | 12 | AkShare 东方财富 | vs板块阈值(主板3亿/双创1亿) |
| A3 净资产 | 8 | AkShare 东方财富 | 归母权益，资不抵债扣分 |
| B1 违规存量 | 5 | **巨潮公告** | 近12月立案=0，立案历史=1，无=类型推演 |
| B2 内控审计 | 5 | **巨潮公告** | 无法表示/否定=0，保留=2，带强调=3 |
| B3 监管处罚 | 6 | **巨潮公告** | 近12月行政处罚=0，历史=1，警示函=3 |
| C1 面值距离 | 8 | 腾讯行情 | ≥10元:8 → <1元:0(面值退市危机) |
| C2 市值水平 | 4 | 腾讯行情 | ≥30亿:4，<4亿:0 |
| D1 现金流质量 | 10 | AkShare 东方财富 | 经营现金流/营收比率 |
| E1 股权稳定性 | 8 | AkShare 质押比例 | 质押<5%=满分 |
| F1 持续经营 | 9 | 扣非+营收复合 | 双达标满分 |
| F2 重组/纾困 | 7 | **巨潮公告** | 重整执行+4，预重整+1，出售+2，豁免/赠与+1 |
| G1 市值偏离度 | 5 | 归母权益+市值 | V618+G时10分，降权 |
| H1 实控人风险 | 8 | **巨潮公告** | 冻结+3/限高+3/实控人立案+2（风险扣分） |
| **合计** | **100** | | |

- 北交所(920开头)B1/B2/B3/F2/H1降级走类型推演（巨潮沪深库不含北交所）
- 信号窗口：近24个月公告；财务报告期标记显示在页面
- V7关键坑（历史名）：巨潮全文搜索同一公告重复返回（×45次），必须按(code,bucket,title,date)去重

### 评级（分数越高=保壳越容易）
- A级(>65) B级(46-65) C级(26-45) D级(≤25)

## V2正式版已切换（2026-08-28晚，灰度对照同日取消）
- baokeng-rank.html/index.html 单口径：V2十三维；当前207家 A59/B113/C34/D1
- 莫高终验：V1 53分/171名 → V2 70分/B级/第64名（A线边界）
- 回测终版：166家强制退市99.4%落C/D，漏报仅退市国化（已知边界案例）
- V2数据管道：st_controllers/st_pledges/st_trends/st_deduct_income.json → build_baokeng_v2.py → st_scores_v2.json
- 通道封顶JS同步：C1=0/B2=0→封顶50、B1=0→封顶30（generate_html.py calcScore2）
- RAW瘦身为11字段纯数据（V1分值移除，承载reason/flags/市值/昨收）；V2RAW 22字段13维从idx4起；verify_html.js生成后必跑
- **V2五脚本已接入weekly_update_friday.py（步骤7-11）**；build_baokeng.py保留在链中仅为提供RAW数据字段

## 更新流程（全自动化）
- weekly_update_friday.py（每周五9:00，共13步）：国证ST名单（EXCLUDE_CODES过滤摘帽残留）→ 新浪行情+腾讯市值 → build_baokeng.py（RAW数据字段载体）→ V2四采集（controllers/pledges/trends/deduct_income，纯requests）→ build_baokeng_v2.py（唯一评分口径）→ generate_html.py（baokeng-rank.html+index.html）
- 财务/公告数据在链外刷新：fetch_financials.py（AkShare）与 fetch_risk_flags.py（巨潮，11.5分钟）读存量JSON进评分引擎，需另行定期跑（自动化prompt或手动）
- 11:00跑名单核验（verify_st_list.py）

## 工具链
- weekly_update_friday.py：每周五全自动更新脚本（含三层数据源降级 + AkShare并发）
- weekly_update.py：兼容性入口（早期版本，主脚本已迁移到 *_friday.py）
- fetch_all_data.py / fetch_financials.py：批量获取财务数据
- fetch_risk_flags.py：巨潮公告信号采集（13关键词×24个月×12桶，去重）
- build_baokeng.py：ST保壳评分系统V1评分引擎（真实公告信号驱动）
- fetch_market_cap.py / patch_market_cap.py：腾讯市值补全
- generate_html.py：HTML生成器（11维度RAW + 全角规范化 + 全列排序）
- fix_missing.py：北交所数据补全
- verify_st_list.py：ST名单周度交叉核验（东财板块×沪深交易所官方名录×腾讯三方仲裁）
- Python: C:/Users/xiaot/.workbuddy/binaries/python/versions/3.13.12/python.exe（核验脚本用venv: envs/default/Scripts/python.exe，需requests+openpyxl）

## 已沉淀为 skill（2026-08-28）
- `~/.workbuddy/skills/baokeng-rank/`：保壳风云榜独立skill
  - SKILL.md（主）
  - references/html_generation_rules.md（5条HTML铁律）
  - references/data_sources.md（API+降级方案）
- 自动化ID：automation-1782198499699（每周五9:00执行）、automation-1787916836110（每周五11:00名单核验）

## ST名单交叉核验（2026-08-28新增，verify_st_list.py）
- 数据源：上交所 query.sse.com.cn commonQuery（sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L，Referer必须带）+ 深交所 www.szse.cn/api/report/ShowReport（CATALOGID=1110，SHOWTYPE=xlsx，A股tab1/B股tab2，列结构一致：A股代码=4/A股简称=5/B股代码=9/B股简称=10）
- 三方仲裁：东财有但官方名称无ST时，用腾讯行情简称判断——腾讯也无ST=东财板块残留（已摘帽）；腾讯有ST=官方名称滞后
- 坑：①上交所COMPANY_ABBR的ST前缀不齐（600165显示"宁科生物"）②深交所英文名含ST子串（Distillery），须用`(?<![A-Za-z])\*?S?ST(?![A-Za-z])`正则③上交所B_STOCK_CODE='-'表示无B股非有效代码④东财板块不含沪B股ST（900915系统性漏）
- 首轮发现（2026-08-28）：东财漏301117 ST佳缘、900915 ST中路B（沪B缺口）；600165/600525已摘帽残留应剔除；无退市残留

## V2重设计方案（2026-08-28设计稿，等老Z改Excel后实施）
- 起因：莫高失真（V1得53分/B级，国资壳系统性低估——缺实控人维度）→ V2演算68分/A级
- V2十三维：C1面值10/C2壳价值8/S1实控人性质12(新增)/S2质押6/A1净资产10/A2营收达标能力12(重构)/A3扣非4/D1现金流4/B1立案造假10/B2审计8/F2重组8/F1趋势4/H1司法4
- 哲学：财务健康度打分→退市概率打分；维度=退市通道，权重=5年176家退市案例实证贡献度（交易类55%/财务32%/规范8%/违法5-9%）
- S1联动：涉造假立案实控人维度封顶4分（退市国化/同达教训：国资非免死金牌）
- 交付物：ST保壳评分系统V1_V2重设计方案.xlsx（老Z可改）、V2重设计研究报告.docx、delist_cases_final.json(176家)
- 采集脚本：delist_history.py（巨潮按年分段，长窗口截断坑）/classify_delist.py/merge_delist.py/build_scoring_xlsx.py/gen_v2_report.js
- S1数据源：企查查MCP批量穿透 + 巨潮实控人持股变动监测（akshare/westock均无全量实控人表）
- 实施待办：老Z改完Excel → build_baokeng.py/generate_html.py V2改造、V1/V2灰度并行、176案例回测

## V2权重老Z定稿（2026-08-28晚定稿，覆盖上节草案数值）
- 定稿六处调整：C1面值10→6、B2审计8→12（与S1并列第一权重）、C2壳价值8分规则反转（市值≤壳基准的5折→8分满，越便宜=并购机会越大）、A2改"扣非主营业务收入"口径、F2重组8→6、A3扣非4→6；总分=100
- 五通道权重：市场14/财务红线32/监管22/股东调节18/纾困14
- 莫高重演算仍≈68分/A级（B2/C2提权对冲C1收紧与A2口径加严）
- Excel/build_scoring_xlsx.py/gen_v2_report.js+Word三处已同步定稿；Excel黄色列仍可微调
- editor_sdk坐标坑：CSV读取跳过空行致行号错位，须用return_csv=false结构化读取定位

## V2正式固化（2026-08-29凌晨，commit c5f2bfe）
- **C2壳基准单源化**：SHELL_BASE=33.81亿（shell-fee-base自家口径：近2年完成实控权变更154样本市值中位数），build_baokeng_v2.py与generate_html.py均动态读取 shell_transactions.json 的 own_mcap_median_yi（兜底33.81）；旧28亿口径降级为交叉验证
- 切换后分布：A64/B109/C33/D1（原A59/B113/C34/D1）；莫高70/B不变；C2=8并购机会区30家
- 摸鱼榜（页面端衍生指标，不落数据）：指数=(50%×V2分+50%×壳便宜分)×等级系数(A/B 1.0、C 0.85、D 0.6)，池=非退市+市值>0共204家；首页三表并排（保壳易/难/摸鱼各TOP10四列简化）；摸鱼报告可分享链接 #moyu-代码 直达
- 会员体系（页面端）：localStorage['bkfl_member']本机存储；专家即时报告+正式PDF版（自托管 assets/html2pdf.bundle.min.js A4导出）+摸鱼报告均会员门控
- 周更链13步含V2五脚本；壳基准变更只需重跑 build_baokeng_v2.py + generate_html.py，页面自动同步
