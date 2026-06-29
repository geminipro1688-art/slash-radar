#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑真實 OKX/CoinGecko 數據，驗證評分引擎輸出。"""
import json, os
import scoring

b = scoring.build_board(enrich_top=10)
print("更新時間戳:", b["updated"], "| 入榜幣數:", len(b["coins"]))
print("恐懼貪婪:", b["market"]["fear_greed"])

for grp, zh in [("bullish", "偏多方結構"), ("bearish", "偏空方結構"), ("candidate", "分歧/候選")]:
    items = b["groups"][grp]
    print(f"\n========== {zh}（{len(items)}）==========")
    for x in items[:6]:
        print(f"{x['symbol']:9} score={x['score']:+4d}  {x['grade']}  | {x['scenario']} | {x['bias']} | 標籤={x['flags']}")
        for f in x["factors"]:
            print(f"      - {f['key']}: {f['detail']} ({f['points']:+})")

out = os.path.join(os.path.dirname(__file__), "..", "data", "sample_board.json")
json.dump(b, open(out, "w"), ensure_ascii=False, indent=1)
print("\n已存樣本榜單 ->", os.path.abspath(out))
