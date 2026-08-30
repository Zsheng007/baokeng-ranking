#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""backtest_fetch.py — 回测点时数据采集

对 backtest_cohorts.json 的每家公司，在快照日 T0 采集：
  1. orgId + 当前名(巨潮topSearch，缓存复用)
  2. [T0-24月, T0] 全部公告 → 12桶分类(复用fetch_risk_flags) + T0时点公司简称(标题前缀)
  3. 东财K线: T0收盘价(不复权) + T0/摘帽日 前复权价(算涨幅)
  4. 新浪财务摘要: T0前最近年报期5字段 + 期末股本(股东权益/每股净资产)

输出: backtest_data.json (增量可断点续跑: 已采集code跳过)
运行环境: envs/default (需akshare)
"""
import json
import re
import os
import time
import random
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

BASE = r'C:\Users\xiaot\WorkBuddy\2026-05-16-task-2'
TOPSEARCH = 'http://www.cninfo.com.cn/new/information/topSearch/query'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

from fetch_risk_flags import (make_opener, strip_tags, ts_to_date,
                              fetch_company, classify_title, BUCKETS, RESTRUCT_STAGE)

FIN_ROWS = {'营业总收入': 'revenue', '扣非净利润': 'deducted_profit',
            '股东权益合计(净资产)': 'total_equity', '经营现金流量净额': 'operating_cf',
            '每股净资产': 'bps'}

GENERIC = {'公司', '本公司', '关于', '公告', '股票', '重大', '临时', '停牌', '风险', '提示'}


def post(url, data, retries=3):
    for i in range(retries):
        try:
            body = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(url, data=body, headers={
                'User-Agent': UA,
                'Referer': 'https://www.cninfo.com.cn/new/fulltextSearch',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            })
            r = urllib.request.urlopen(req, timeout=25)
            return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            if i == retries - 1:
                return None
            time.sleep(2 + i)


def top_search(code, opener):
    d = post(TOPSEARCH, {'keyWord': code, 'maxNum': '10'})
    if isinstance(d, list):
        for x in d:
            if x.get('code') == code:
                return x
    return None


def name_from_titles(anns, t0, secname):
    """从公告标题前缀推断T0时点简称(标题中的公司简称含当时ST前缀)"""
    lim = (datetime.strptime(t0, '%Y-%m-%d') - timedelta(days=120)).strftime('%Y-%m-%d')
    cands = []
    for a in anns:
        d = ts_to_date(a.get('announcementTime'))
        if not (lim <= d <= t0):
            continue
        title = strip_tags(a.get('announcementTitle', ''))
        for sep in ('关于', '：', ':'):
            if sep in title:
                pre = title.split(sep)[0].strip()
                pre = re.sub(r'[（(].*', '', pre).strip()
                if 2 <= len(pre) <= 14 and pre not in GENERIC and not pre.isdigit():
                    cands.append(pre)
                break
    if cands:
        # 最常见候选; 优先含ST的候选
        from collections import Counter
        cnt = Counter(cands)
        st_c = [c for c in cands if 'ST' in c.upper()]
        if st_c:
            return Counter(st_c).most_common(1)[0][0]
        return cnt.most_common(1)[0][0]
    return secname or ''


def tencent_symbol(code):
    """腾讯行情市场前缀: 沪A/B 6/9开头, 深A/B其余, 北交所 4/8/92开头"""
    if code.startswith(('6', '9')):
        return f'sh{code}'
    if code.startswith(('4', '8', '92')):
        return f'bj{code}'
    return f'sz{code}'


def fetch_kline(code, start, end, adjust=''):
    """腾讯K线(退市股可用), 返回[(date, close)]列表或None"""
    sym = tencent_symbol(code)
    if adjust == 'qfq':
        p = f'param={sym},day,{start},{end},640,qfq'
        key = 'qfqday'
    else:
        p = f'param={sym},day,{start},{end},640,'
        key = 'day'
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?' + p
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        d = json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8'))
        days = (d.get('data', {}).get(sym) or {}).get(key) or []
        out = [(str(x[0]), float(x[2])) for x in days]  # [日期,开,收,...]
        return out if out else None
    except Exception:
        return None


def kline_close_at(rows, date):
    """date当日或之前最近一根收盘; rows为[(date,close)]列表"""
    if not rows:
        return None
    sub = [r for r in rows if r[0] <= date]
    if not sub:
        return None
    row = sub[-1]
    return row[1], row[0]


def fetch_financials(code, t0):
    """新浪财务摘要: 取T0前最近年报期5字段+股本"""
    try:
        df = ak.stock_financial_abstract(symbol=code)
    except Exception:
        return None
    if df is None or len(df) == 0:
        return None
    period = f"{int(t0[:4]) - 1}1231"  # T0当年4月底前披露的上年年报
    if period not in df.columns:
        return None
    out = {'period': period}
    for _, r in df.iterrows():
        if str(r.get('选项')) != '常用指标':
            continue
        ind = str(r.get('指标'))
        if ind in FIN_ROWS:
            v = r.get(period)
            try:
                v = float(v) if v == v and v is not None else None  # NaN→None
            except Exception:
                v = None
            out[FIN_ROWS[ind]] = v
    # 期末股本 = 股东权益 / 每股净资产
    eq, bps = out.get('total_equity'), out.get('bps')
    if eq and bps and bps > 0:
        out['shares'] = eq / bps
    else:
        out['shares'] = None
    return out


def main():
    with open(f'{BASE}\\backtest_cohorts.json', encoding='utf-8') as f:
        cohorts = json.load(f)
    targets = cohorts['delist'] + cohorts['uncap']
    print(f'回测采集目标: {len(targets)} 家 (退市{len(cohorts["delist"])} + 摘帽{len(cohorts["uncap"])})')

    # 断点续跑
    data_path = f'{BASE}\\backtest_data.json'
    if os.path.exists(data_path):
        with open(data_path, encoding='utf-8') as f:
            payload = json.load(f)
        done = payload.get('data', {})
    else:
        payload, done = {'meta': {}, 'data': {}}, {}
    print(f'已完成: {len(done)} 家, 续跑')

    opener = make_opener()
    t_start = time.time()
    for i, tgt in enumerate(targets, 1):
        code = tgt['code']
        if code in done:
            continue
        t0 = tgt['t0']
        try:
            rec = {'code': code, 'name': tgt['name'], 'group': tgt['group'],
                   'event_date': tgt['event_date'], 't0': t0, 'cat': tgt.get('cat'),
                   'title': tgt.get('title', '')}

            # 1) orgId
            ts = top_search(code, opener)
            org_id = (ts or {}).get('orgId')
            rec['cur_name'] = (ts or {}).get('zwjc')
            rec['org_id'] = org_id
            time.sleep(random.uniform(0.2, 0.5))

            # 2) 公告24个月窗口 → 12桶
            start = (datetime.strptime(t0, '%Y-%m-%d') - timedelta(days=730)).strftime('%Y-%m-%d')
            se_date = f'{start}~{t0}'
            buckets = {b: [] for b in BUCKETS}
            n_ann = 0
            if org_id:
                anns = fetch_company(opener, code, org_id, se_date)
                n_ann = len(anns)
                secname = strip_tags((anns[0].get('secName') if anns else '') or '')
                rec['name_t0'] = name_from_titles(anns, t0, secname)
                for a in anns:
                    title = strip_tags(a.get('announcementTitle', ''))
                    bucket = classify_title(title)
                    if bucket is None:
                        continue
                    d = ts_to_date(a.get('announcementTime'))
                    r = {'title': title, 'date': d}
                    if bucket == 'restructuring':
                        r['stage'] = 'exec' if RESTRUCT_STAGE.search(title) else 'early'
                    buckets[bucket].append(r)
            else:
                rec['name_t0'] = tgt['name']
            rec['flags'] = buckets
            rec['n_ann'] = n_ann

            # 3) K线: T0价格(不复权) + 事件价格(前复权)
            d0 = datetime.strptime(t0, '%Y-%m-%d')
            k_raw = fetch_kline(code, (d0 - timedelta(days=20)).strftime('%Y-%m-%d'),
                                (d0 + timedelta(days=5)).strftime('%Y-%m-%d'), '')
            c = kline_close_at(k_raw, t0)
            if c:
                rec['price_t0'], rec['price_t0_date'] = c
            ev = datetime.strptime(tgt['event_date'], '%Y-%m-%d')
            k_qfq = fetch_kline(code, (d0 - timedelta(days=7)).strftime('%Y-%m-%d'),
                                (ev + timedelta(days=7)).strftime('%Y-%m-%d'), 'qfq')
            cq = kline_close_at(k_qfq, t0)
            if cq:
                rec['qfq_price_t0'] = cq[0]
            ce = kline_close_at(k_qfq, tgt['event_date']) if k_qfq is not None else None
            if ce:
                rec['qfq_price_event'], rec['event_trade_date'] = ce
            # 摘帽组: 事件日不复权价+市值
            if tgt['group'] == 'uncap' and k_qfq is not None:
                k_ev_raw = fetch_kline(code, (ev - timedelta(days=5)).strftime('%Y-%m-%d'),
                                       (ev + timedelta(days=7)).strftime('%Y-%m-%d'), '')
                ce_raw = kline_close_at(k_ev_raw, tgt['event_date'])
                if ce_raw:
                    rec['price_event'], _ = ce_raw
            time.sleep(random.uniform(0.3, 0.7))

            # 4) 财务摘要(最近年报期)
            fin = fetch_financials(code, t0)
            rec['fin'] = fin
            # 摘帽组事件期财务(算事件市值用年报股本, 快照股本沿用)
            if tgt['group'] == 'uncap':
                fin_ev = fetch_financials(code, tgt['event_date'])
                rec['fin_event'] = fin_ev

            done[code] = rec
        except Exception as e:
            print(f'[ERR] {code} {tgt["name"]}: {e}')
            continue
        # 每5家落盘
        if i % 5 == 0 or i == len(targets):
            payload['data'] = done
            payload['meta'] = {'fetched_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
                               'n': len(done)}
            with open(data_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False)
            el = (time.time() - t_start) / 60
            remain = len(targets) - len(done)
            rate = max(len(done) / max((time.time() - t_start) / 60, 0.1), 0.1)
            print(f'[{i}/{len(targets)}] {code} {tgt["name"]} 公告{rec.get("n_ann", 0)}条 '
                  f'| price_t0={rec.get("price_t0")} | 累计{len(done)}家 已用{el:.1f}分 剩余约{remain/rate:.0f}分')

    payload['data'] = done
    payload['meta'] = {'fetched_at': datetime.now().strftime('%Y-%m-%d %H:%M'), 'n': len(done)}
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=0)
    print(f'\n完成: {len(done)}家 → backtest_data.json')


if __name__ == '__main__':
    main()
