#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slash-radar 評分引擎（中立合規版）
========================================
把合約盤面數據（價格動能 × OI 結構 × 資金費率 × 多空比 × 主動買賣量）
編碼成一個「數據結構強度分數」與「情境標籤」。

🔴 法遵設計（台灣《投信投顧法》）：
  - 分數代表「合約數據偏多方/偏空方結構的強度」，是對【已發生數據】的統計描述，
    不是、也不得被解讀為「買進/賣出/做多/做空」的操作建議。
  - 全程不輸出 進場價 / 止損 / 止盈 / 目標價 / 明牌。
  - 每張卡強制附免責。
這正是我們相對競品的差異化：用合規的「中立數據呈現」吃它的 SEO 空門。
"""
import time

# ---- 可調權重 ----
W_OI = 30      # OI×價 結構（最重）
W_MOM = 20     # 價格動能
W_FUND = 15    # 資金費率
W_CVD = 12     # 主動買賣量差（CVD 代理）
W_LSR = 8      # 多空比
DISCLAIMER = "本卡為合約市場數據統計，僅供研究參考，非投資建議。"

def _clamp(x, lo, hi):
    return max(lo, min(hi, x))

def score_coin(c, oi_chg=None, funding=None, lsr=None, cvd=None):
    """
    c: {symbol, price, chg_1h, chg_24h, oi_usd, market_cap, vol_usdt_24h}
    oi_chg/funding/lsr/cvd: enrich 後的補充數據（可為 None）
    回傳：中立評分卡 dict
    """
    score = 0.0
    factors = []   # 每個維度的貢獻（透明可解釋）
    flags = []     # 風險/結構標籤

    pc1 = c.get("chg_1h") or 0.0
    pc24 = c.get("chg_24h") or 0.0
    oi_usd = c.get("oi_usd") or 0.0
    mcap = c.get("market_cap") or 0.0
    vol = c.get("vol_usdt_24h") or 0.0

    # 1) 價格動能（1h）：±5% 約對應滿分
    mom = _clamp(pc1 * (W_MOM / 5.0), -W_MOM, W_MOM)
    score += mom
    factors.append({"key": "動能", "detail": f"1h {pc1:+.2f}%", "points": round(mom, 1)})

    # 2) OI × 價 結構（需 oi_chg）
    scenario = "動能上行" if pc1 >= 0 else "動能下行"
    if oi_chg is not None:
        mag = _clamp((abs(pc1) + abs(oi_chg)) * 2.5, 0, W_OI)
        if pc1 >= 0 and oi_chg >= 0:
            s, scenario = +mag, "增倉上行"          # 資金主動進場、偏多結構
        elif pc1 < 0 and oi_chg >= 0:
            s, scenario = -mag, "增倉下行"          # 空方增倉、偏空結構
        elif pc1 >= 0 and oi_chg < 0:
            s, scenario = +mag * 0.4, "減倉反彈"     # 空頭回補、輕倉上行
        else:
            s, scenario = -mag * 0.4, "減倉下行"     # 多頭離場、拋壓衰減
        score += s
        factors.append({"key": "OI 結構",
                        "detail": f"OI 1h {oi_chg:+.2f}%（{scenario}）",
                        "points": round(s, 1)})

    # 3) 資金費率：負費率（空頭擁擠）偏多分、正費率（多頭擁擠）偏空分
    if funding is not None:
        fs = _clamp(-funding * 3.0, -W_FUND, W_FUND)
        score += fs
        factors.append({"key": "資金費率", "detail": f"{funding:+.4f}%", "points": round(fs, 1)})
        if abs(funding) >= 1.0:
            flags.append("費率背離")

    # 4) 主動買賣量差（CVD 代理）
    if cvd is not None:
        cs = W_CVD if cvd > 0 else -W_CVD
        score += cs
        factors.append({"key": "主動買賣", "detail": ("買壓" if cvd > 0 else "賣壓"),
                        "points": cs})
        # 量價背離 → 覆寫情境（對標競品的「衰竭 / 吸收」）
        if pc1 > 0 and cvd < 0:
            scenario = "動能衰減（價漲量縮）"
        elif pc1 < 0 and cvd > 0:
            scenario = "下方吸籌（價跌買增）"

    # 5) 多空比：極端 → 反向小幅修正
    if lsr is not None:
        if lsr >= 2.0:
            score -= W_LSR; flags.append("多方擁擠")
        elif lsr <= 0.6:
            score += W_LSR; flags.append("空方擁擠")

    # 6) 槓桿擁擠（OI/市值比）→ 純風險標籤，不計分方向
    oi_mcap = (oi_usd / mcap) if mcap else 0.0
    if oi_mcap >= 0.05:
        flags.append("槓桿擁擠")

    score = round(_clamp(score, -100, 100))
    a = abs(score)
    high_liq = vol >= 5e7
    if a >= 50 and high_liq:
        grade = "重點關注"
    elif a >= 25:
        grade = "候選觀察"
    else:
        grade = "一般異動"

    if score >= 8:
        bias = "合約數據偏多方結構"
    elif score <= -8:
        bias = "合約數據偏空方結構"
    else:
        bias = "多空分歧 / 中性"

    return {
        "symbol": c.get("symbol"), "name": c.get("name"), "exchanges": c.get("exchanges", []),
        "image": c.get("image"), "price": c.get("price") or c.get("last"),
        "chg_1h": round(pc1, 2), "chg_24h": round(pc24, 2),
        "score": score, "grade": grade, "scenario": scenario,
        "bias": bias, "factors": factors, "flags": flags,
        "oi_usd": round(oi_usd), "oi_chg": (round(oi_chg, 2) if oi_chg is not None else None),
        "oi_mcap_ratio": round(oi_mcap, 4),
        "vol_usdt_24h": round(vol), "disclaimer": DISCLAIMER,
    }


def build_board(enrich_top=12, min_vol=2e6):
    """
    組裝整個選幣榜：批量數據 → 初評 → 對 top 異動幣 enrich 合約數據 → 重評 → 分組。
    回傳 {updated, market, coins, groups}
    """
    try:
        from . import sources as S  # 套件內相對匯入
    except ImportError:
        import sources as S         # 直接執行時
    def _safe(fn, default):                # 任一上游失敗（限速/被擋/逾時）都不該拖垮整個看板
        try:
            return fn()
        except Exception:
            return default
    okx_t = _safe(S.okx_tickers, {}); okx_oi_map = _safe(S.okx_oi, {})
    bn_t = _safe(S.binance_tickers, {}); bn_fund = _safe(S.binance_funding_all, {})
    g = _safe(lambda: S.gecko_markets(pages=1), {})

    base = []
    for sym in (set(okx_t) | set(bn_t)):
        ot, bt = okx_t.get(sym), bn_t.get(sym)
        vol = (ot["vol_usdt_24h"] if ot else 0.0) + (bt["vol_usdt_24h"] if bt else 0.0)
        if vol < min_vol:
            continue
        gk = g.get(sym, {})
        ref = ot or bt
        exch = (["OKX"] if ot else []) + (["幣安"] if bt else [])
        c = {
            "symbol": sym, "name": gk.get("name") or sym, "image": gk.get("image"),
            "price": ref["last"], "last": ref["last"],
            "chg_1h": gk.get("chg_1h_pct"), "chg_24h": ref["chg_24h_pct"],
            "oi_usd": okx_oi_map.get(sym) or 0.0,        # 幣安 OI 於 enrich 階段加總
            "market_cap": gk.get("market_cap"), "vol_usdt_24h": vol,
            "exchanges": exch, "funding": bn_fund.get(sym),   # 幣安批量費率（全幣即時可得）
        }
        base.append((c, score_coin(c, funding=c["funding"])))

    # 依「初評強度 + 24h 異動」挑 top 去 enrich（補兩所 OI 變化 / CVD）
    base.sort(key=lambda x: (abs(x[1]["score"]), abs(x[0].get("chg_24h") or 0)), reverse=True)
    core, rest = [], []
    for i, (c, _) in enumerate(base):
        if i < enrich_top:
            sym = c["symbol"]
            oi_chg = S.okx_oi_history(sym); time.sleep(0.08)
            bn_oi_usd, oi_chg_bn = S.binance_oi(sym); time.sleep(0.08)
            if oi_chg_bn is not None:                  # 幣安 OI 為 USD 計價，優先採用
                oi_chg = oi_chg_bn
            if bn_oi_usd:
                c["oi_usd"] = (c["oi_usd"] or 0.0) + bn_oi_usd   # 聚合兩所 OI
            cvd = S.okx_taker_cvd(sym); time.sleep(0.08)
            lsr = None
            if i < 14:                                  # 核心幣再補多空比
                lsr = S.okx_lsr(sym); time.sleep(0.08)
            core.append(score_coin(c, oi_chg=oi_chg, funding=c["funding"], lsr=lsr, cvd=cvd))
        else:
            rest.append(score_coin(c, funding=c["funding"]))

    core.sort(key=lambda x: x["score"], reverse=True)
    bull = [x for x in core if x["score"] >= 20]
    bear = sorted([x for x in core if x["score"] <= -20], key=lambda x: x["score"])
    cand = [x for x in core if -20 < x["score"] < 20]
    return {
        "updated": int(time.time()),
        "market": {"fear_greed": S.fear_greed(), "scored": len(core),
                   "bull_n": len(bull), "bear_n": len(bear),
                   "total_coins": len(core) + len(rest),
                   "sources": ["OKX", "幣安", "CoinGecko"]},
        "coins": core + rest,
        "groups": {"bullish": bull[:24], "bearish": bear[:24], "candidate": cand[:24]},
    }
