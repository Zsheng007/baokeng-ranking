#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_market_cap.py
本地运行（需要网络）：获取188家ST公司真实市值，
写入 market_cap.json + 更新 st_scores.json
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
    """逐只查询东方财富 API，返回 {code: mv_yi, ...}"""
    results = {}
    total = len(codes)
    for i, code in enumerate(codes):
        secid = "0." + code if code.startswith(("6", "9")) else "1." + code
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
            print(f"  {code} fail: {e}")
        if (i + 1) % 20 == 0:
            print(f"  progress: {i+1}/{total}")
        time.sleep(delay)
    return results


def main():
    print("=" * 50)
    print("  BaoKeng - Market Cap Fetcher (local only)")
    print("=" * 50)

    # 1. Load ST list
    names_path = os.path.join(BASE, "st_names.json")
    if not os.path.exists(names_path):
        print(f"[ERROR] Cannot find {names_path}")
        return
    with open(names_path, encoding="utf-8") as f:
        name_map = json.load(f)
    st_codes = sorted(name_map.keys())
    print(f"[1/4] Loaded ST list: {len(st_codes)} stocks")

    # 2. Fetch market cap
    print("[2/4] Fetching from East Money (one by one, ~30s)...")
    market_data = fetch_market_cap(st_codes)
    print(f"  [OK] Got {len(market_data)}/{len(st_codes)}")

    failed = [c for c in st_codes if c not in market_data]
    if failed:
        print(f"  [WARN] Missing: {failed[:10]}{'...' if len(failed)>10 else ''}")

    # 3. Write market_cap.json
    print("[3/4] Writing market_cap.json...")
    mkt_file = os.path.join(BASE, "market_cap.json")
    with open(mkt_file, "w", encoding="utf-8") as f:
        json.dump(market_data, f, ensure_ascii=False, indent=1)
    print(f"  [OK] Written to {mkt_file}")

    # 4. Update st_scores.json
    print("[4/4] Updating st_scores.json...")
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
    print(f"  [OK] Updated {updated} entries")

    # 5. Re-generate HTML (optional)
    print("\nRe-generate baokeng-rank.html? (y/n): ", end="")
    choice = input().strip().lower()
    if choice == "y":
        gen_path = os.path.join(BASE, "generate_html.py")
        ret = os.system(f'"{sys.executable}" "{gen_path}"')
        if ret == 0:
            print("  [OK] HTML regenerated")
        else:
            print("  [FAIL] HTML regeneration failed")

    # 6. Push to GitHub (optional)
    print("\nPush to GitHub Pages? (y/n): ", end="")
    choice = input().strip().lower()
    if choice == "y":
        print("  Pushing to GitHub...")
        os.system(
            'git add baokeng-rank.html market_cap.json st_scores.json && '
            'git commit -m "data: update market cap (real)" && '
            'git push origin main'
        )
        print("  [OK] Pushed")
        print("\n  Online: https://zsheng007.github.io/baokeng-ranking/")
    else:
        print(f"\n  Local file ready: {os.path.join(BASE, 'baokeng-rank.html')}")
        print("  Open in browser (needs market_cap.json in same dir)")

    print("\n[OK] All done!")
    print(f"   Market cap data: {len(market_data)} stocks")
    if market_data:
        print("\nTop 10 preview:")
        for code in list(market_data.keys())[:10]:
            print(f"  {code} {name_map.get(code,'')}: {market_data[code]:.1f} Yi")


if __name__ == "__main__":
    main()
