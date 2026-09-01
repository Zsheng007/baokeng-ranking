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

## 巨潮采集与B1三档（2026-08-30元道案例沉淀）
- **巨潮关键词搜索翻页bug（根因级）**：hisAnnouncement/query大窗口关键词搜索5页500条实际仅150条（120条重复），元道类立案公告排在400名开外永远翻不到→采集须用**公司定向查询**：orgId取自官方映射 https://www.cninfo.com.cn/new/data/szse_stock.json（6243只），stock=code,orgId，pageSize服务端钳制30，定向翻页正常
- fetch_risk_flags.py已重写为定向方案：2965条信号/194家有信号（旧方案仅~150条）
- **B1三档**：重大档(0分封顶30)=公司本体处罚+立案全链条(38家)；一般档(7分)=本体单发处罚无立案(22家，沈化/人福/绝味类)；子公司档(7分)=仅子公司被罚(纳川/启环)。PERSON_CASE个人案(董监高/实控人)不归零走H1（莫高案例）；SUBSIDIARY_CASE=子公司|分公司|孙公司
- 分布基线（2026-08-30）：A8/B91/C66/D42共207家；元道30/D/171名
- 修改建议报告：ST保壳评分系统V2修改建议_301139元道案例_20260830.docx；P0待拍板=退市锁定一票否决+摸鱼池防飞刀闸门
- 会员配额：localStorage{quota:3,used}，申请码BK-{尾4}-{代码}，V168+G九章式深度报告走企微人工交付

## 页面V2化+全榜报告库（2026-08-31，commit f932056）
- 页面（baokeng-rank.html/index.html）V168+G品牌字样彻底清零，申请深度报告按钮/弹窗/回执统一为「ST摸鱼风云-V2」七章完整版（V2评分模块为骨架），交付承诺"60分钟内企微交付"
- **项目铁律：页面文案改动必须落 generate_html.py 模板（HTML是产物，直接改会被下次生成覆盖）；模板内JS的 ${...} 需写 ${ {...}} 转义**
- 企微二维码槽位：申请回执嵌 `<img src="assets/wecom_qr.png" onerror→fallback提示>`，图片就位即自动显示，无图不影响上线
- 方案A报告库：reports_baokeng_v2/ 共207份docx（命名`ST摸鱼风云-V2跟读报告_{摸鱼排名:03d}_{code}_{简称}_日期.docx`），客服按申请码直发；gen_moyu_all_reports.py 全榜批跑（TOP10手写logic/risk AST单源提取+197家模板规则引擎），每周榜单更新后可重跑刷新
- gen_moyu_top10_detail.py 为可复用生成器（build参数化、3位排名、__main__保护）；摸鱼公式复刻见2026-08-31日志
- 数据待查：*ST岭南 controller_cat="民企(法人)"但controller=中山火炬管委会，疑似国资误分类

## 报告升级：V168+G九章式结构 × V2评分刻度（2026-09-01）
- 老Z定调："报告更深度168G版本，评分系统用V2，保持得分一致"→ 报告骨架=九章式深度结构，评分=score_v2单源十三维，榜单分数=报告分数不变
- 新结构：投资要点页+九章（公司概况/财务分析[V2红线口径]/股权结构/司法信号/退市研判[五通道矩阵]/壳价值与并购成本/驱动压制/综合评级/附录）；新增 channel_matrix() 五通道归组（市场C1C2/财务A1A2A3D1/规范B2/违法B1/股东治理S1S2H1/纾困F2F1）
- 数据铁律：只用st_scores_v2.json可得字段，缺报表级数据用V2维度替代并声明口径，不编造
- gen_moyu_top10_detail.py build()重写（签名不变，全榜脚本复用）；默认日期参数20260901
- 全库207份重跑29秒0失败；旧版20260831文件已清；坑：dict(DIMS)对三元组报错须用full字典推导式
- 周更后重跑 gen_moyu_all_reports.py 即刷新九章式报告库

## 跟读报告功能整体下线（2026-09-01，老Z决策）
- 老Z明确"不再需要跟读报告"→ 确认：**整个报告功能下线，页面只保留评分榜单；207份报告库保留**（reports_baokeng_v2/ 继续留仓库，客服如需可人工直发）
- 页面已移除：即时跟读报告/申请完整版/摸鱼分析报告全部按钮+弹窗、注册会员流程（bkfl_member）、申请码、PDF导出、#moyu-分享路由；摸鱼榜行点击改绑 gotoDetail
- 页面现状=纯榜单工具：全名单/风云榜/摸鱼榜三视图+投票+详情评分面板；无会员/无注册/无报告按钮
- **产品结论：榜单是免费公开工具，报告交付改走线下人工（库内docx直发），不再由页面承载**
- 项目铁律补充：页面模板 generate_html.py 有镜像文件 _check.js（用户编辑器自动同步，改动主模板后须留意）
- GitHub推送应急方案：github.com被限流时用 Git Data API 模拟推送（blobs→trees→commits→refs），注意会产生与本地git历史分叉的commit，网络恢复后 fetch+reset --hard origin/main 对齐
