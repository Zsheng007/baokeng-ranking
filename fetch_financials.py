#!/usr/bin/env python3
"""批量获取ST/*ST公司财务数据 — 用于保壳风云榜真实评分
数据来源：AkShare → 东方财富/同花顺
输出：st_financials.json

数据维度：
- 营业总收入、净利润（最新年报）
- 扣非净利润（同花顺财务摘要）
- 归母股东权益、资产负债率
- 经营活动现金流净额
- 股权质押比例
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import akshare as ak
import pandas as pd

# ── 配置 ──
REPORT_DATE = '20251231'  # 2025年年报
MAX_WORKERS = 20

# ── 加载ST名单 ──
with open('st_names.json', encoding='utf-8') as f:
    name_map = json.load(f)

codes = list(name_map.keys())
print(f'目标股票数: {len(codes)}')


# ============================================================
# 第一步：批量下载四大报表
# ============================================================

print('\n[1/5] 下载业绩报表 (yjbb)...')
df_yjbb = ak.stock_yjbb_em(date=REPORT_DATE)
df_yjbb = df_yjbb.set_index('股票代码')
print(f'  获取 {len(df_yjbb)} 条记录')

print('[2/5] 下载资产负债表 (zcfz)...')
df_zcfz = ak.stock_zcfz_em(date=REPORT_DATE)
df_zcfz = df_zcfz.set_index('股票代码')
print(f'  获取 {len(df_zcfz)} 条记录')

print('[3/5] 下载现金流量表 (xjll)...')
df_xjll = ak.stock_xjll_em(date=REPORT_DATE)
df_xjll = df_xjll.set_index('股票代码')
print(f'  获取 {len(df_xjll)} 条记录')

print('[4/5] 下载股权质押比例...')
df_pledge = ak.stock_gpzy_pledge_ratio_em()
df_pledge = df_pledge.set_index('股票代码')
print(f'  获取 {len(df_pledge)} 条记录')


# ============================================================
# 第二步：并发获取扣非净利润
# ============================================================

def parse_cn_number(v):
    """解析中文数字格式：'3.45亿' -> 345000000, '-4456.33万' -> -44563300, 'False'/None -> None"""
    if v is None or v == 'False' or v is False:
        return None
    if isinstance(v, (int, float)):
        if pd.isna(v):
            return None
        return float(v)
    s = str(v).strip()
    if not s or s == 'False':
        return None
    try:
        if '亿' in s:
            return float(s.replace('亿', '')) * 100000000
        elif '万' in s:
            return float(s.replace('万', '')) * 10000
        else:
            return float(s)
    except (ValueError, TypeError):
        return None


def fetch_deducted(code):
    """获取单只股票的扣非净利润"""
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator='按报告期')
        if df.empty:
            return code, None, None

        # 找最新报告期（2025-12-31）
        latest = df[df['报告期'] == '2025-12-31']
        if latest.empty:
            latest = df[df['报告期'] == '2025-09-30']
        if latest.empty:
            df_sorted = df.sort_values('报告期', ascending=False)
            latest = df_sorted.head(1)

        row = latest.iloc[0]
        deducted = row.get('扣非净利润', None)
        return code, parse_cn_number(deducted), None
    except Exception as e:
        return code, None, None


print(f'\n[5/5] 并发获取扣非净利润 ({len(codes)} 只, {MAX_WORKERS} 线程)...')
deducted_map = {}
done = 0
errors = 0

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(fetch_deducted, c): c for c in codes}
    for future in as_completed(futures):
        code, deducted, net_profit = future.result()
        deducted_map[code] = {'deducted_profit': deducted, 'ths_net_profit': net_profit}
        done += 1
        if deducted is None:
            errors += 1
        if done % 50 == 0:
            print(f'  进度: {done}/{len(codes)} (缺失: {errors})')

print(f'  完成: {done}/{len(codes)} (扣非净利润缺失: {errors})')


# ============================================================
# 第三步：合并数据
# ============================================================

def safe_num(val, default=None):
    """安全转换为数值"""
    if val is None:
        return default
    try:
        v = float(val)
        if pd.isna(v):
            return default
        return v
    except (ValueError, TypeError):
        return default


financials = {}

for code in codes:
    fin = {
        'code': code,
        'name': name_map[code],
        # 利润表
        'revenue': None,          # 营业总收入
        'net_profit': None,       # 净利润
        'deducted_profit': None,  # 扣非净利润
        'bps': None,              # 每股净资产
        'ocf_per_share': None,    # 每股经营现金流
        # 资产负债表
        'total_equity': None,     # 股东权益合计
        'debt_ratio': None,       # 资产负债率
        # 现金流量表
        'operating_cf': None,     # 经营性现金流净额
        # 质押
        'pledge_ratio': None,     # 质押比例
    }

    # --- 业绩报表 (使用位置索引，列顺序固定) ---
    # yjbb columns: 序号,股票代码,股票简称,每股收益,营业收入,营收同比,营收环比,
    #                净利润,净利同比,净利环比,每股净资产,净资产收益率,每股经营现金流,销售毛利率,所处行业,公告日期
    if code in df_yjbb.index:
        row = df_yjbb.loc[code]
        fin['revenue'] = safe_num(row.iloc[3] if len(row) > 3 else None)
        fin['net_profit'] = safe_num(row.iloc[6] if len(row) > 6 else None)
        fin['bps'] = safe_num(row.iloc[9] if len(row) > 9 else None)
        fin['ocf_per_share'] = safe_num(row.iloc[11] if len(row) > 11 else None)

    # --- 资产负债表 (位置索引) ---
    # zcfz after set_index: iloc[0]=序号, [11]=资产负债率, [12]=股东权益合计, [13]=公告日期
    if code in df_zcfz.index:
        row = df_zcfz.loc[code]
        fin['total_equity'] = safe_num(row.iloc[12] if len(row) > 12 else None)
        fin['debt_ratio'] = safe_num(row.iloc[11] if len(row) > 11 else None)

    # --- 现金流量表 (位置索引) ---
    # xjll after set_index: iloc[0]=序号, [4]=经营性现金流净额, [10]=公告日期
    if code in df_xjll.index:
        row = df_xjll.loc[code]
        fin['operating_cf'] = safe_num(row.iloc[4] if len(row) > 4 else None)

    # --- 质押比例 (位置索引) ---
    # pledge after set_index: iloc[0]=序号, [5]=质押比例
    if code in df_pledge.index:
        row = df_pledge.loc[code]
        fin['pledge_ratio'] = safe_num(row.iloc[4] if len(row) > 4 else None)

    # --- 扣非净利润 ---
    if code in deducted_map:
        fin['deducted_profit'] = deducted_map[code]['deducted_profit']

    financials[code] = fin


# ============================================================
# 第四步：统计与保存
# ============================================================

# 统计覆盖率
cov = {
    'revenue': sum(1 for f in financials.values() if f['revenue'] is not None),
    'net_profit': sum(1 for f in financials.values() if f['net_profit'] is not None),
    'deducted_profit': sum(1 for f in financials.values() if f['deducted_profit'] is not None),
    'total_equity': sum(1 for f in financials.values() if f['total_equity'] is not None),
    'debt_ratio': sum(1 for f in financials.values() if f['debt_ratio'] is not None),
    'operating_cf': sum(1 for f in financials.values() if f['operating_cf'] is not None),
    'pledge_ratio': sum(1 for f in financials.values() if f['pledge_ratio'] is not None),
}

print('\n=== Coverage ===')
for k, v in cov.items():
    pct = v / len(codes) * 100
    bar = '#' * int(pct / 5) + '-' * (20 - int(pct / 5))
    print(f'  {k:20s}: {v:3d}/{len(codes)} ({pct:5.1f}%) {bar}')

# 保存
output = {
    'report_date': REPORT_DATE,
    'fetch_time': time.strftime('%Y-%m-%d %H:%M:%S'),
    'total_stocks': len(codes),
    'coverage': cov,
    'data': financials,
}

with open('st_financials.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=1)

print(f'\n[DONE] Saved st_financials.json ({len(codes)} stocks)')
