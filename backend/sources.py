#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slash-radar 數據源層
全部使用「公開」API：OKX 公開行情/合約 + CoinGecko 免費版。
不搬任何競品程式碼；資料來源人人可取。
"""
import requests, time

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
OKX = "https://www.okx.com"
GECKO = "https://api.coingecko.com/api/v3"

_cache = {}  # 簡易記憶體快取，降低對上游的請求頻率（對標競品的 *-cache 端點）

def _get(url, ttl=20, params=None):
    key = url + "|" + str(params)
    now = time.time()
    if key in _cache and now - _cache[key][0] < ttl:
        return _cache[key][1]
    r = requests.get(url, params=params, headers=UA, timeout=20)
    r.raise_for_status()
    j = r.json()
    _cache[key] = (now, j)
    return j

# ---------- OKX 永續合約（USDT 本位） ----------
def okx_tickers():
    """全市場 USDT 永續即時行情。一次請求拿全部。"""
    j = _get(OKX + "/api/v5/market/tickers", ttl=15, params={"instType": "SWAP"})
    out = {}
    for d in j.get("data", []):
        iid = d["instId"]
        if not iid.endswith("-USDT-SWAP"):
            continue
        sym = iid[:-10]  # 去掉 -USDT-SWAP
        try:
            last = float(d["last"]); op = float(d["open24h"])
            out[sym] = {
                "last": last,
                "open24h": op,
                "high24h": float(d["high24h"]),
                "low24h": float(d["low24h"]),
                "vol_usdt_24h": float(d["volCcy24h"]),          # 24h 成交額（USDT）
                "chg_24h_pct": (last / op - 1) * 100 if op else 0.0,
            }
        except (KeyError, ValueError):
            pass
    return out

def okx_oi():
    """全市場 USDT 永續未平倉（OI）。一次請求拿全部。"""
    j = _get(OKX + "/api/v5/public/open-interest", ttl=15, params={"instType": "SWAP"})
    out = {}
    for d in j.get("data", []):
        iid = d["instId"]
        if not iid.endswith("-USDT-SWAP"):
            continue
        sym = iid[:-10]
        try:
            oi_usd = d.get("oiUsd")
            out[sym] = float(oi_usd) if oi_usd not in (None, "") else float(d.get("oiCcy", 0))
        except (KeyError, ValueError):
            pass
    return out

def okx_funding(sym):
    """單一幣資金費率（逐 instId，給 top 異動幣補資料用）。"""
    try:
        j = _get(OKX + "/api/v5/public/funding-rate", ttl=60,
                 params={"instId": f"{sym}-USDT-SWAP"})
        d = j.get("data", [{}])[0]
        return float(d.get("fundingRate", 0)) * 100  # 轉成 %
    except Exception:
        return None

def okx_lsr(sym):
    """單一幣多空帳戶比（最新值）。"""
    try:
        j = _get(OKX + "/api/v5/rubik/stat/contracts/long-short-account-ratio",
                 ttl=120, params={"ccy": sym, "period": "5m"})
        data = j.get("data", [])
        return float(data[0][1]) if data else None
    except Exception:
        return None

def okx_oi_history(sym):
    """單一幣 OI 時序（用來算 1h OI 變化，給 top 異動幣補資料用）。"""
    try:
        j = _get(OKX + "/api/v5/rubik/stat/contracts/open-interest-volume",
                 ttl=120, params={"ccy": sym, "period": "5m"})
        data = j.get("data", [])  # [[ts, oi, vol], ...] 新→舊
        if len(data) >= 13:
            now_oi = float(data[0][1]); ago_oi = float(data[12][1])  # 12*5m=1h 前
            return (now_oi / ago_oi - 1) * 100 if ago_oi else 0.0
    except Exception:
        pass
    return None

def okx_taker_cvd(sym):
    """單一幣 1h 主動買賣量差（CVD 代理：主動買量-主動賣量）。"""
    try:
        j = _get(OKX + "/api/v5/rubik/stat/taker-volume", ttl=120,
                 params={"ccy": sym, "instType": "CONTRACTS", "period": "5m"})
        data = j.get("data", [])  # [[ts, sellVol, buyVol], ...]
        buy = sum(float(r[2]) for r in data[:12])
        sell = sum(float(r[1]) for r in data[:12])
        return buy - sell
    except Exception:
        return None

# ---------- CoinGecko（市值、1h 動能、幣 logo） ----------
def gecko_markets(pages=1, per_page=250):
    """市值排行 + 多週期漲跌幅 + logo。symbol 去重取市值最大者。"""
    out = {}
    for pg in range(1, pages + 1):
        j = _get(GECKO + "/coins/markets", ttl=60, params={
            "vs_currency": "usd", "order": "market_cap_desc",
            "per_page": per_page, "page": pg,
            "price_change_percentage": "1h,24h",
        })
        for d in j:
            sym = (d.get("symbol") or "").upper()
            if not sym:
                continue
            prev = out.get(sym)
            if prev and (prev.get("market_cap") or 0) >= (d.get("market_cap") or 0):
                continue
            out[sym] = {
                "name": d.get("name"), "image": d.get("image"),
                "market_cap": d.get("market_cap"),
                "market_cap_rank": d.get("market_cap_rank"),
                "chg_1h_pct": d.get("price_change_percentage_1h_in_currency"),
                "chg_24h_pct": d.get("price_change_percentage_24h_in_currency"),
                "price": d.get("current_price"),
            }
    return out

# ---------- 幣安永續合約（USDT 本位） ----------
BINANCE = "https://fapi.binance.com"

def _bsym(s):
    """BTCUSDT -> BTC（對齊 OKX 命名）。"""
    return s[:-4] if s.endswith("USDT") else s

def binance_tickers():
    """全市場 USDT 永續行情。一次請求拿全部。"""
    j = _get(BINANCE + "/fapi/v1/ticker/24hr", ttl=15)
    out = {}
    for d in j:
        s = d.get("symbol", "")
        if not s.endswith("USDT"):
            continue
        try:
            out[_bsym(s)] = {
                "last": float(d["lastPrice"]),
                "chg_24h_pct": float(d["priceChangePercent"]),
                "vol_usdt_24h": float(d["quoteVolume"]),
            }
        except (KeyError, ValueError):
            pass
    return out

def binance_funding_all():
    """全市場資金費率（批量！一次拿全部，OKX 做不到）。回 dict[sym]=費率%。"""
    j = _get(BINANCE + "/fapi/v1/premiumIndex", ttl=60)
    out = {}
    for d in j:
        s = d.get("symbol", "")
        if not s.endswith("USDT"):
            continue
        try:
            out[_bsym(s)] = float(d["lastFundingRate"]) * 100
        except (KeyError, ValueError):
            pass
    return out

def binance_oi(sym):
    """單一幣 OI（USD）與 1h 變化。回 (oi_usd, oi_chg_1h%)。"""
    try:
        j = _get(BINANCE + "/futures/data/openInterestHist", ttl=120,
                 params={"symbol": sym + "USDT", "period": "5m", "limit": 13})
        if len(j) >= 13:
            now = float(j[-1]["sumOpenInterestValue"])
            ago = float(j[0]["sumOpenInterestValue"])
            return now, ((now / ago - 1) * 100 if ago else 0.0)
    except Exception:
        pass
    return None, None

def binance_lsr(sym):
    """單一幣多空帳戶比（最新值）。"""
    try:
        j = _get(BINANCE + "/futures/data/globalLongShortAccountRatio", ttl=120,
                 params={"symbol": sym + "USDT", "period": "5m", "limit": 1})
        return float(j[-1]["longShortRatio"]) if j else None
    except Exception:
        return None

# ---------- 市場情緒 ----------
def fear_greed():
    """恐懼貪婪指數（alternative.me 公開）。"""
    try:
        j = _get("https://api.alternative.me/fng/", ttl=600, params={"limit": 1})
        d = j.get("data", [{}])[0]
        return {"value": int(d.get("value", 0)), "label": d.get("value_classification", "")}
    except Exception:
        return None

if __name__ == "__main__":
    import json
    t = okx_tickers(); oi = okx_oi(); g = gecko_markets(pages=1)
    print("OKX swap 幣數:", len(t), "| OI 幣數:", len(oi), "| Gecko 幣數:", len(g))
    print("BTC ticker:", json.dumps(t.get("BTC"), ensure_ascii=False))
    print("BTC OI(USD):", oi.get("BTC"))
    print("BTC funding%:", okx_funding("BTC"), "| LSR:", okx_lsr("BTC"),
          "| OI 1h%:", okx_oi_history("BTC"))
    print("FnG:", fear_greed())
