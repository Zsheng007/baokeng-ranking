#!/usr/bin/env python3
"""一次性剔除东财/国证板块残留的已摘帽标的（600165 宁科生物 / 600525 长园集团）。
腾讯行情证实两者已不带 ST 前缀（2026-08-28 名单核验轮结论）。
永久剔除机制已写入 weekly_update_friday.py 的 EXCLUDE_CODES。
本脚本幂等：可重复运行，已剔除时无操作。
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
EXCLUDE = {'600165', '600525'}


def purge_dict(path, key_check=lambda k: k in EXCLUDE):
    """剔除 dict 顶层键为排除代码的文件"""
    p = os.path.join(BASE, path)
    if not os.path.exists(p):
        print(f'  [skip] {path} 不存在')
        return 0
    d = json.load(open(p, encoding='utf-8'))
    n = 0
    for c in EXCLUDE:
        if c in d:
            del d[c]
            n += 1
    if n:
        json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'  {path}: 剔除 {n} 只')
    return n


def purge_list_by_code(path, container=None):
    """剔除 list 或 {container: list} 结构中 code 在排除集的记录"""
    p = os.path.join(BASE, path)
    if not os.path.exists(p):
        print(f'  [skip] {path} 不存在')
        return 0
    d = json.load(open(p, encoding='utf-8'))
    if container:
        lst = d.get(container)
        if not isinstance(lst, list):
            print(f'  {path}: {container} 非list，跳过')
            return 0
    else:
        lst = d
    n = 0
    if isinstance(lst, list):
        before = len(lst)
        lst = [x for x in lst if x.get('code') not in EXCLUDE]
        n = before - len(lst)
        if container:
            d[container] = lst
            json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        else:
            json.dump(lst, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'  {path}: 剔除 {n} 只')
    return n


if __name__ == '__main__':
    print('剔除摘帽残留标的:', sorted(EXCLUDE))
    print()

    print('[1] 名单与行情')
    purge_dict('st_names.json')
    purge_dict('st_market_data.json')
    purge_dict('market_cap.json')

    print('[2] 财务与公告数据')
    p = os.path.join(BASE, 'st_financials.json')
    d = json.load(open(p, encoding='utf-8'))
    n = sum(1 for c in EXCLUDE if c in d.get('data', {}))
    for c in EXCLUDE:
        d['data'].pop(c, None)
    d['total_stocks'] = len(d['data'])
    json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'  st_financials.json: 剔除 {n} 只 (total_stocks={d["total_stocks"]})')

    p = os.path.join(BASE, 'st_risk_flags.json')
    d = json.load(open(p, encoding='utf-8'))
    n = sum(1 for c in EXCLUDE if c in d.get('flags', {}))
    for c in EXCLUDE:
        d['flags'].pop(c, None)
    json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'  st_risk_flags.json: 剔除 {n} 只')

    print('[3] V2 数据管道')
    for fn in ['st_controllers.json', 'st_pledges.json', 'st_trends.json', 'st_deduct_income.json']:
        p = os.path.join(BASE, fn)
        if not os.path.exists(p):
            print(f'  [skip] {fn} 不存在')
            continue
        d = json.load(open(p, encoding='utf-8'))
        n = 0
        for key in ('data',):
            sub = d.get(key)
            if isinstance(sub, dict):
                n = sum(1 for c in EXCLUDE if c in sub)
                for c in EXCLUDE:
                    sub.pop(c, None)
            elif isinstance(sub, list):
                b = len(sub)
                d[key] = [x for x in sub if x.get('code') not in EXCLUDE]
                n = b - len(d[key])
        if n or True:
            json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'  {fn}: 剔除 {n} 只')

    print('[4] 评分结果（将被重跑覆盖，先同步剔除）')
    purge_list_by_code('st_scores.json')
    purge_list_by_code('st_scores_v2.json', container='data')

    print()
    print('清洗完成。下一步：重跑 build_baokeng.py / build_baokeng_v2.py / generate_html.py')
