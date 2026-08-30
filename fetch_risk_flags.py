#!/usr/bin/env python3
"""fetch_risk_flags.py — 从巨潮资讯网按公司定向拉取ST公告风险/纾困信号

数据源: https://www.cninfo.com.cn/new/hisAnnouncement/query (POST, 公司定向查询)
方法: 每家ST公司定向拉取近24个月全部公告标题(翻页+去重) → 本地关键词分类进12桶
输出: st_risk_flags.json
  {code: {
    "investigation": [...],   # B1 立案调查公告
    "penalty": [...],          # B1/B3 行政处罚公告(2026-08-30起并入B1: 处罚落地=违法实锤)
    "warning": [...],          # B3 警示函/监管函
    "audit_adverse": [...],    # B2 无法表示意见/否定意见(最重)
    "audit_qualified": [...],  # B2 保留意见
    "audit_emphasis": [...],   # B2 带强调事项/持续经营/非标准(轻)
    "freeze": [...],           # H1 股份冻结
    "consume_limit": [...],    # H1 限制消费/限高
    "restructuring": [...],    # F2 重整(分阶段)
    "asset_sale": [...],       # F2 重大资产出售/重组
    "debt_waiver": [...],      # F2 债务豁免/债务重组
    "donation": [...]          # F2 资产赠与/捐赠
  }}

历史(2026-08-30方案切换): 旧版用全市场关键词搜索, 但巨潮关键词大窗口翻页存在
重复返回+截断bug(5页请求500条实际唯一仅~30条, 元道立案公告永远翻不到)；
公司定向查询(stock=code,orgId)翻页正常且覆盖全量, 故弃关键词方案改定向。
orgId 来源: https://www.cninfo.com.cn/new/data/szse_stock.json (巨潮官方股票映射)
注: 每条公告记录 {title, date}。北交所股票不在巨潮沪深库中, 走规则降级。
"""
import json, os, re, sys, time, random
import urllib.request, urllib.parse
import http.cookiejar
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))

# ── 配置 ──────────────────────────────────────────
MONTHS_BACK = 24
PAGE_SIZE = 30                 # 巨潮服务端钳制: 定向查询pageSize最大30
MAX_PAGES_PER_STOCK = 20       # 每公司最多20页(600条公告)防失控
SLEEP_RANGE = (0.6, 1.2)

API_URL = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
ORG_URL = 'https://www.cninfo.com.cn/new/data/szse_stock.json'


def make_opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.open('https://www.cninfo.com.cn', timeout=15)  # 领cookie
    return op


def strip_tags(text):
    return re.sub(r'<[^>]+>', '', text or '')


def ts_to_date(ts_ms):
    if not ts_ms:
        return ''
    return datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d')


# ── 公司定向拉取 ──────────────────────────────────
def fetch_company(opener, code, org_id, se_date):
    """定向拉取单家公司窗口内全部公告(翻页+announcementId去重)"""
    all_anns, seen_ids = [], set()
    page = 1
    while page <= MAX_PAGES_PER_STOCK:
        data = urllib.parse.urlencode({
            'pageNum': str(page), 'pageSize': str(PAGE_SIZE),
            'column': 'szse', 'tabName': 'fulltext',
            'stock': f'{code},{org_id}', 'searchkey': '',
            'seDate': se_date, 'isHLtitle': 'true',
        }).encode()
        try:
            r = opener.open(urllib.request.Request(API_URL, data=data, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.cninfo.com.cn/new/fulltextSearch',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            }), timeout=20)
            j = json.loads(r.read().decode('utf-8'))
        except Exception as e:
            print(f'    第{page}页失败({e}), 重试一次...')
            time.sleep(5)
            try:
                r = opener.open(urllib.request.Request(API_URL, data=data, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Referer': 'https://www.cninfo.com.cn/new/fulltextSearch',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                }), timeout=20)
                j = json.loads(r.read().decode('utf-8'))
            except Exception:
                break
        anns = j.get('announcements') or []
        new = [a for a in anns if a.get('announcementId') and a['announcementId'] not in seen_ids]
        for a in anns:
            if a.get('announcementId'):
                seen_ids.add(a['announcementId'])
        all_anns.extend(new)
        if not new or not anns:  # 翻页重复或到底
            break
        page += 1
        time.sleep(random.uniform(*SLEEP_RANGE))
    return all_anns


# ── 标题分类(替代旧版kw+title双因子分类, 定向方案无kw) ──
def classify_title(title):
    t = title
    # B2 审计意见
    if '无法表示意见' in t or '否定意见' in t:
        return 'audit_adverse'
    if '保留意见' in t:
        return 'audit_qualified'
    if '非标准' in t and ('审计' in t or '意见' in t or '专项说明' in t):
        return 'audit_emphasis'
    # B1 立案/处罚
    if '立案' in t and ('调查' in t or '证监会' in t or '进展' in t or '告知书' in t or '决定书' in t or '涉嫌' in t):
        return 'investigation'
    if '处罚' in t and ('决定书' in t or '事先告知' in t or '行政处罚' in t):
        return 'penalty'
    # B3 警示
    if '警示函' in t or '监管函' in t:
        return 'warning'
    # F2 纾困/重组
    if '重整' in t:
        return 'restructuring'
    if ('重大资产' in t and ('出售' in t or '重组' in t or '购买' in t)) or '资产出售' in t:
        return 'asset_sale'
    if ('豁免' in t and '债务' in t) or '债务重组' in t:
        return 'debt_waiver'
    if '赠与' in t or '捐赠' in t or '无偿' in t:
        return 'donation'
    # H1 司法
    if '冻结' in t:
        return 'freeze'
    if '限制消费' in t or '限高' in t:
        return 'consume_limit'
    return None


BUCKETS = ['investigation', 'penalty', 'warning', 'audit_adverse',
           'audit_qualified', 'audit_emphasis', 'freeze', 'consume_limit',
           'restructuring', 'asset_sale', 'debt_waiver', 'donation']

RESTRUCT_STAGE = re.compile(r'计划(执行|获|批|通过|获准|获法院)|裁定批准|执行进展|重整完成|终结')


def load_org_map(opener):
    """巨潮官方股票映射: code -> orgId"""
    r = opener.open(urllib.request.Request(ORG_URL, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }), timeout=20)
    j = json.loads(r.read().decode('utf-8'))
    return {x['code']: x['orgId'] for x in (j.get('stockList') or []) if x.get('code') and x.get('orgId')}


def main():
    # 加载ST名单
    with open(os.path.join(BASE, 'st_names.json'), encoding='utf-8') as f:
        name_map = json.load(f)
    st_codes = sorted(name_map.keys())
    print(f'[1/3] ST名单: {len(st_codes)} 只')

    # 日期窗口: 近24个月
    today = datetime.now()
    start = today - timedelta(days=MONTHS_BACK * 30)
    se_date = f"{start.strftime('%Y-%m-%d')}~{today.strftime('%Y-%m-%d')}"
    print(f'[2/3] 窗口: {se_date}（公司定向查询）')

    opener = make_opener()
    org_map = load_org_map(opener)
    print(f'      orgId映射: {len(org_map)} 只')

    flags = {c: {b: [] for b in BUCKETS} for c in st_codes}
    stats = {}

    t0 = time.time()
    done = 0
    for i, code in enumerate(st_codes, 1):
        org_id = org_map.get(code)
        if not org_id:
            continue  # 北交所等不在巨潮沪深库, 走类型推演
        anns = fetch_company(opener, code, org_id, se_date)
        n_hit = 0
        for a in anns:
            title = strip_tags(a.get('announcementTitle', ''))
            bucket = classify_title(title)
            if bucket is None:
                continue
            date = ts_to_date(a.get('announcementTime'))
            rec = {'title': title, 'date': date}
            # 重整分阶段: 早期(申请/预重整/受理) vs 执行期
            if bucket == 'restructuring':
                rec['stage'] = 'exec' if RESTRUCT_STAGE.search(title) else 'early'
            flags[code][bucket].append(rec)
            stats[bucket] = stats.get(bucket, 0) + 1
            n_hit += 1
        done += 1
        if i % 20 == 0 or i == len(st_codes):
            el = time.time() - t0
            print(f'  [{i}/{len(st_codes)}] {code} 公告{len(anns)}条 命中{n_hit} | 累计{sum(stats.values())}条 | 已用{el/60:.1f}分钟')

    # 写出
    out = {
        'meta': {
            'fetched_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'window': se_date,
            'method': 'company_targeted',  # 公司定向查询(旧keyword_search方案2026-08-30废弃)
            'bucket_stats': stats,
        },
        'flags': flags,
    }
    path = os.path.join(BASE, 'st_risk_flags.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f'[3/3] 已写入 {path}')
    print(f'完成! 桶统计: {json.dumps(stats, ensure_ascii=False)}')
    print(f'有信号公司数: {sum(1 for v in flags.values() if any(v.values()))} / {len(st_codes)}')


if __name__ == '__main__':
    main()
