#!/usr/bin/env python3
"""S1实控人数据管道 — 东财数据中心RPT_F10_BASIC_ORGINFO批量采集（2026-08-28）

数据源：https://datacenter.eastmoney.com/securities/api/data/v1/get
  reportName=RPT_F10_BASIC_ORGINFO  字段 ACTUAL_HOLDER（实控人名称）
覆盖：沪/深/北交所全部ST/*ST（214家），含退市股（回测复用）
分类规则（S1定稿口径，Excel Sheet3）：
  央企:10 / 省级国资:10 / 市县国资:8 / 高校院所:8 / 强产业资本民企:6(名称不可判,暂按3)
  一般民企:3 / 失联无实控:1
输出：st_controllers.json
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
    'Referer': 'https://datacenter.eastmoney.com/',
}
URL = 'https://datacenter.eastmoney.com/securities/api/data/v1/get'

CENTRAL_SOE_HINTS = ('国务院国有资产监督管理委员会', '中国中信', '中国宝武', '中国铝业',
                     '中国节能', '中国医药集团', '中国航天', '中国航空', '中国船舶',
                     '中国兵器', '中粮集团', '招商局', '华润', '国机集团', '东风汽车')
SOE_HINTS = ('国资委', '国有资产', '国有资本', '财政局', '财政厅', '国有资产经营',
             '国有控股', '国有独资')
LOCAL_MARKS = ('市', '县', '区', '州', '盟', '旗', '自治区', '地区')
PROV_MARKS = ('省', '自治区')
ACADEMY_HINTS = ('大学', '学院', '研究所', '科学院', '研究院')


def secu_code(code: str) -> str:
    c3 = code[:3]
    if c3 in ('600', '601', '603', '605', '688', '689', '900'):
        return code + '.SH'
    if c3 == '920' or code.startswith('4') or code.startswith('8'):
        return code + '.BJ'
    return code + '.SZ'


def classify(holder: str):
    """实控人名称 → (类别, S1基础分)"""
    if not holder or holder in ('无', '-', '无实际控制人', '无控股股东'):
        return ('无实控人', 1)
    h = holder.strip()
    # 央企：国务院国资委直接实控或知名央企集团
    if h == '国务院国有资产监督管理委员会' or any(k in h for k in CENTRAL_SOE_HINTS):
        return ('央企', 10)
    # 国资体系
    if any(k in h for k in SOE_HINTS) or '人民政府' in h or h.endswith('管委会'):
        # 省级 vs 市县
        has_prov = any(m in h for m in PROV_MARKS)
        has_local = any(m in h for m in LOCAL_MARKS)
        if has_prov and not has_local:
            return ('省级国资', 10)
        if has_local:
            return ('市县国资', 8)
        return ('国资(未分层)', 8)
    # 高校/科研院所
    if any(k in h for k in ACADEMY_HINTS):
        return ('高校院所', 8)
    # 自然人（2-4字中文，无机构后缀）
    if re.fullmatch(r'[\u4e00-\u9fa5·]{2,4}', h) and not any(
            k in h for k in ('公司', '集团', '厂', '局', '委', '府')):
        return ('民企(个人)', 3)
    # 法人（公司/集团），无国资关键词 → 民企法人；产业资本强度需企查查穿透，暂按3
    return ('民企(法人)', 3)


def fetch_one(code: str):
    sc = secu_code(code)
    for attempt in range(3):
        try:
            r = requests.get(URL, params={
                'reportName': 'RPT_F10_BASIC_ORGINFO', 'columns': 'ALL',
                'filter': f'(SECUCODE="{sc}")', 'pageNumber': 1, 'pageSize': 1,
            }, headers=HEADERS, timeout=12)
            res = r.json().get('result')
            if res and res.get('data'):
                d = res['data'][0]
                holder = (d.get('ACTUAL_HOLDER') or '').strip() or None
                cat, base = classify(holder or '')
                return code, {
                    'secucode': sc,
                    'name': d.get('SECURITY_NAME_ABBR'),
                    'controller': holder,
                    'category': cat if holder else '未获取',
                    's1_base': base,
                    'province': d.get('PROVINCE'),
                    'reg_capital_wan': d.get('REG_CAPITAL'),
                }
            return code, None  # 接口通但无数据
        except Exception:
            time.sleep(1 + attempt)
    return code, None


def main():
    with open(os.path.join(BASE, 'st_names.json'), encoding='utf-8') as f:
        name_map = json.load(f)
    codes = list(name_map.keys())
    print(f'[S1] 开始批量采集实控人：{len(codes)}家')

    out, fails = {}, []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, c): c for c in codes}
        done = 0
        for fut in as_completed(futs):
            code, info = fut.result()
            done += 1
            if info:
                out[code] = info
            else:
                fails.append(code)
            if done % 50 == 0:
                print(f'  进度 {done}/{len(codes)}，失败 {len(fails)}')

    payload = {
        'meta': {
            'source': 'datacenter.eastmoney.com RPT_F10_BASIC_ORGINFO.ACTUAL_HOLDER',
            'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total': len(codes), 'ok': len(out), 'fail': len(fails),
            'rule': '央企/省级:10 市县/高校:8 民企:3 无实控:1；涉造假立案封顶4(评分引擎执行)',
        },
        'data': out,
    }
    with open(os.path.join(BASE, 'st_controllers.json'), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    # 分布统计
    from collections import Counter
    dist = Counter(v['category'] for v in out.values())
    print(f'[S1] 完成：成功 {len(out)}，失败 {len(fails)} {fails[:10]}')
    print('[S1] 实控人分布：')
    for cat, n in dist.most_common():
        print(f'    {cat}: {n}')
    # 抽样展示
    for probe in ('600543', '000585', '920575'):
        if probe in out:
            v = out[probe]
            print(f'  样例 {probe} {v["name"]}: {v["controller"]} → {v["category"]}')


if __name__ == '__main__':
    main()
