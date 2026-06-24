#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_market_cap.py
本地运行（需要网络）：获取188家ST公司真实市值，
写入 market_cap.json（供页面加载）+ 更新 st_scores.json
用法: python fetch_market_cap.py
"""

import json
import sys
import os
import time
import urllib.request
import urllib.parse

BASE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()

def fetch_market_cap(codes, delay=0.15):
    """
    逐只查询东方财富 API，返回 {code: mv_yi, ...}
    """
    results = {}
    total = len(codes)
    for i, code in enumerate(codes):
        secid = "0." + code if code.startswith(("6","9")) else "1." + code
        url = (
            f"https://push2.eastmoney.com/api/qt/stock/get?"
            f"secid={secid}&fields=f12,f117"
            f"&ut=bd1d9ddb04089700cf9c27f6f7426281"
        )
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Referer": "https://quote.eastmoney.com/"
            })
            resp = urllib.request.urlopen(req, timeout=10)
            data = json.loads(resp.read())
            d = data.get("data", {})
            if d:
                total_mv_wan = float(d.get("f117", 0) or 0)
                mv_yi = round(total_mv_wan / 10000, 2) if total_mv_wan else 0
                results[code] = mv_yi
        except Exception as e:
            print(f"  {code} 失败: {e}")
        if (i + 1) % 20 == 0:
            print(f"  进度: {i+1}/{total}")
        time.sleep(delay)
    return results


def main():
    print("=" * 50)
    print("  保壳风云榜 - 市值数据获取工具（本地运行）")
    print("=" * 50)

    # 1. 加载 ST 名单
    names_path = os.path.join(BASE, "st_names.json")
    if not os.path.exists(names_path):
        print(f"❌ 找不到 {names_path}，请在项目目录下运行")
        return
    with open(names_path, encoding="utf-8") as f:
        name_map = json.load(f)
    st_codes = sorted(name_map.keys())
    print(f"[1/4] 加载 ST 名单: {len(st_codes)} 只")

    # 2. 获取市值
    print("[2/4] 正在从东方财富获取市值（逐只查询，约需30秒）...")
    market_data = fetch_market_cap(st_codes)
    print(f"  ✅ 获取到 {len(market_data)}/{len(st_codes)} 只")

    failed = [c for c in st_codes if c not in market_data]
    if failed:
        print(f"  ⚠️ 未获取到: {failed[:10]}{'...' if len(failed)>10 else ''}")

    # 3. 写入 market_cap.json（页面直接加载的格式）
    print("[3/4] 写入 market_cap.json...")
    mkt_file = os.path.join(BASE, "market_cap.json")
    with open(mkt_file, "w", encoding="utf-8") as f:
        json.dump(market_data, f, ensure_ascii=False, indent=1)
    print(f"  ✅ 已写入 {mkt_file}")

    # 4. 更新 st_scores.json
    print("[4/4] 更新 st_scores.json...")
    scores_path = os.path.join(BASE, "st_scores.json")
    with open(scores_path, encoding="utf-8") as f:
        scores = json.load(f)

    updated = 0
    for s in scores:
        code = s["code"]
        if code in market_data:
            s["market_cap_yi"] = market_data[code]
            updated += 1

    with open(scores_path, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=1)
    print(f"  ✅ 已更新 {updated} 条")

    # 5. 重新生成 HTML（可选）
    print("\n是否重新生成 baokeng-rank.html？(y/n): ", end="")
    choice = input().strip().lower()
    if choice == "y":
        gen_path = os.path.join(BASE, "generate_html.py")
        ret = os.system(f'"{sys.executable}" "{gen_path}"')
        if ret == 0:
            print("  ✅ HTML 已重新生成")
        else:
            print("  ❌ HTML 重新生成失败")

    # 6. 推送到 GitHub（可选）
    print("\n是否推送到 GitHub Pages？(y/n): ", end="")
    choice = input().strip().lower()
    if choice == "y":
        print("  推送到 GitHub...")
        os.system(
            'git add baokeng-rank.html market_cap.json st_scores.json && '
            'git commit -m "data: 更新市值数据（真实）" && '
            'git push origin main'
        )
        print("  ✅ 已推送")
        print(f"\n🌐 在线页面: https://zsheng007.github.io/baokeng-ranking/")
    else:
        print(f"\n📂 本地文件已就绪: {os.path.join(BASE, 'baokeng-rank.html')}")
        print("  用浏览器打开即可查看（需在同一目录有 market_cap.json）")

    print("\n✅ 全部完成！")
    print(f"   市值数据: {len(market_data)} 只")
    if market_data:
        print("\n前10只市值预览:")
        for code in list(market_data.keys())[:10]:
            print(f"  {code} {name_map.get(code,'')}: {market_data[code]:.1f}亿")


if __name__ == "__main__":
    main()
