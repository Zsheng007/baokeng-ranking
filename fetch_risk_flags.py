#!/usr/bin/env python3
"""fetch_risk_flags.py — 从巨潮资讯网批量拉取ST公司的公告风险/纾困信号

数据源: https://www.cninfo.com.cn/new/hisAnnouncement/query (POST, 全市场关键词搜索)
方法: 12个关键词 × 近24个月窗口 × 分页拉取 → 过滤ST名单 → 按维度分类
输出: st_risk_flags.json
  {code: {
    "investigation": [...],   # B1 立案调查公告
    "penalty": [...],          # B3 行政处罚公告
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

注: 每条公告记录 {title, date}。北交所股票不在巨潮沪深库中, 走规则降级。
"""
import json, os, re, sys, time, random
import urllib.request, urllib.parse
import http.cookiejar
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.abspath(__file__))

# ── 配置 ──────────────────────────────────────────
KEYWORDS = [
    '非标准', '无法表示意见', '否定意见',      # B2 审计意见
    '立案',                                   # B1
    '处罚', '警示函', '监管函',               # B3
    '重整', '重大资产', '债务豁免', '赠与',   # F2
    '股份冻结', '限制消费',                   # H1
]
MONTHS_BACK = 24
MAX_PAGES_PER_KW = 80          # 每关键词最多80页(8000条)防失控
PAGE_SIZE = 100
SLEEP_RANGE = (1.0, 2.0)

API_URL = 'https://www.cninfo.com.cn/new/hisAnnouncement/query'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'https://www.cninfo.com.cn',
    'Referer': 'https://www.cninfo.com.cn/new/commonUrl?url=disclosure/list/notice',
}


def make_opener():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = list(HEADERS.items())
    try:
        opener.open('https://www.cninfo.com.cn/new/index.jsp', timeout=10).read(200)
        time.sleep(0.5)
    except Exception:
        pass
    return opener


def strip_tags(text):
    return re.sub(r'<[^>]+>', '', text or '').strip()


def ts_to_date(ts_ms):
    if not ts_ms:
        return ''
    try:
        return datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d')
    except Exception:
        return ''


def fetch_kw(opener, kw, se_date):
    """全市场关键词搜索, 返回该关键词全部公告(分页)"""
    all_anns = []
    page = 1
    while page <= MAX_PAGES_PER_KW:
        data = urllib.parse.urlencode({
            'pageNum': str(page), 'pageSize': str(PAGE_SIZE),
            'column': 'szse', 'tabName': 'fulltext',
            'searchkey': kw, 'seDate': se_date, 'isHLtitle': 'true',
        }).encode()
        try:
            r = opener.open(API_URL, data, timeout=20)
            j = json.loads(r.read().decode('utf-8'))
        except Exception as e:
            print(f'    第{page}页失败({e}), 重试一次...')
            time.sleep(5)
            try:
                r = opener.open(API_URL, data, timeout=20)
                j = json.loads(r.read().decode('utf-8'))
            except Exception:
                break
        anns = j.get('announcements') or []
        all_anns.extend(anns)
        total = j.get('totalAnnouncement', 0)
        if page == 1:
            print(f'    总量 {total} 条, 约 {min((total + PAGE_SIZE - 1)//PAGE_SIZE, MAX_PAGES_PER_KW)} 页')
        if len(all_anns) >= total or not anns:
            break
        page += 1
        time.sleep(random.uniform(*SLEEP_RANGE))
    return all_anns


# ── 分类逻辑 ──────────────────────────────────────
def classify(kw, title):
    """按关键词+标题内容分类, 返回桶名或None"""
    t = title
    if kw in ('非标准', '无法表示意见', '否定意见'):
        if '无法表示意见' in t:
            return 'audit_adverse'
        if '否定意见' in t:
            return 'audit_adverse'
        if '保留意见' in t:
            return 'audit_qualified'
        if '非标准' in t:
            return 'audit_emphasis'
        return None
    if kw == '立案':
        if '立案' in t and ('调查' in t or '证监会' in t or '进展' in t or '告知书' in t or '决定书' in t or '涉嫌' in t):
            return 'investigation'
        return None
    if kw == '处罚':
        if '处罚' in t and ('决定书' in t or '事先告知' in t or '行政处罚' in t):
            return 'penalty'
        return None
    if kw in ('警示函', '监管函'):
        return 'warning'
    if kw == '重整':
        return 'restructuring'
    if kw == '重大资产':
        if '出售' in t or '重组' in t or '购买' in t:
            return 'asset_sale'
        return None
    if kw == '债务豁免':
        if '豁免' in t and '债务' in t:
            return 'debt_waiver'
        if '债务重组' in t:
            return 'debt_waiver'
        return None
    if kw == '赠与':
        if '赠与' in t or '捐赠' in t or '无偿' in t:
            return 'donation'
        return None
    if kw == '股份冻结':
        if '冻结' in t:
            return 'freeze'
        return None
    if kw == '限制消费':
        return 'consume_limit'
    return None


BUCKETS = ['investigation', 'penalty', 'warning', 'audit_adverse',
           'audit_qualified', 'audit_emphasis', 'freeze', 'consume_limit',
           'restructuring', 'asset_sale', 'debt_waiver', 'donation']

RESTRUCT_STAGE = re.compile(r'计划(执行|获|批|通过|获准|获法院)|裁定批准|执行进展|重整完成|终结')


def main():
    # 加载ST名单
    with open(os.path.join(BASE, 'st_names.json'), encoding='utf-8') as f:
        name_map = json.load(f)
    st_codes = set(name_map.keys())
    print(f'[1/3] ST名单: {len(st_codes)} 只')

    # 日期窗口: 近24个月
    today = datetime.now()
    start = today - timedelta(days=MONTHS_BACK * 30)
    se_date = f"{start.strftime('%Y-%m-%d')}~{today.strftime('%Y-%m-%d')}"
    print(f'[2/3] 窗口: {se_date}')

    opener = make_opener()
    flags = {c: {b: [] for b in BUCKETS} for c in st_codes}
    stats = {}
    seen = set()  # (code, bucket, title, date) 去重 — 巨潮全文搜索同一公告会重复返回

    for i, kw in enumerate(KEYWORDS):
        print(f'  [{i+1}/{len(KEYWORDS)}] 关键词: {kw}')
        anns = fetch_kw(opener, kw, se_date)
        hit = 0
        for a in anns:
            code = a.get('secCode', '')
            if code not in st_codes:
                continue
            title = strip_tags(a.get('announcementTitle', ''))
            bucket = classify(kw, title)
            if bucket is None:
                continue
            date = ts_to_date(a.get('announcementTime'))
            key = (code, bucket, title, date)
            if key in seen:
                continue
            seen.add(key)
            # 重整分阶段: 早期(申请/预重整/受理) vs 执行期
            if bucket == 'restructuring':
                stage = 'exec' if RESTRUCT_STAGE.search(title) else 'early'
                flags[code][bucket].append({'title': title, 'date': date, 'stage': stage})
            else:
                flags[code][bucket].append({'title': title, 'date': date})
            hit += 1
        stats[kw] = hit
        print(f'    ST命中: {hit} 条(去重后)')
        time.sleep(random.uniform(2.0, 3.0))

    # 保存
    out = os.path.join(BASE, 'st_risk_flags.json')
    meta = {
        'fetched_at': today.strftime('%Y-%m-%d %H:%M'),
        'window': se_date,
        'keyword_stats': stats,
    }
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({'meta': meta, 'flags': flags}, f, ensure_ascii=False, indent=1)
    print(f'[3/3] 已写入 {out}')

    # 统计摘要
    n_inv = sum(1 for c in flags if flags[c]['investigation'])
    n_pen = sum(1 for c in flags if flags[c]['penalty'])
    n_adv = sum(1 for c in flags if flags[c]['audit_adverse'])
    n_frz = sum(1 for c in flags if flags[c]['freeze'])
    n_res = sum(1 for c in flags if flags[c]['restructuring'])
    n_sale = sum(1 for c in flags if flags[c]['asset_sale'])
    print(f'\nST命中公司数: 立案{n_inv} 处罚{n_pen} 非标(重){n_adv} 冻结{n_frz} 重整{n_res} 资产出售{n_sale}')
    print('完成!')


if __name__ == '__main__':
    main()
