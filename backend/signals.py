#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
slash-radar 訊號引擎（中立合規版）
- 從評分榜偵測「數據異動」與「OI/動能背離」訊號，持續累積成訊號流。
- 每條訊號附【中立數據解讀】：規則模板；若設了 ANTHROPIC_API_KEY 則自動改用 Claude 生成。
🔴 法遵：只描述【已發生】的數據現象，不輸出 做多/做空/進場/止損/止盈/目標價。
"""
import json, os, time

LOG = os.path.join(os.path.dirname(__file__), "..", "data", "signals_log.json")
_MAX = 300
DISCLAIMER = "本內容為合約數據統計，非投資建議。"

def _load():
    try:
        return json.load(open(LOG, encoding="utf-8"))
    except Exception:
        return []

def _save(sigs):
    json.dump(sigs[-_MAX:], open(LOG, "w", encoding="utf-8"), ensure_ascii=False)

# ---------- 中立數據解讀 ----------
def _template_explain(s):
    sym, sc = s["symbol"], s["scenario"]
    base = {
        "增倉上行": f"{sym} 近 1 小時價格與未平倉同步走高，資金主動增倉、主動買盤佔優，屬偏多方數據結構。",
        "增倉下行": f"{sym} 價格走低但未平倉增加，呈空方增倉跡象，屬偏空方數據結構。",
        "減倉反彈": f"{sym} 價格回升伴隨未平倉下降，偏向空頭回補的輕倉反彈。",
        "減倉下行": f"{sym} 價格與未平倉同步收斂，多頭離場、拋壓衰減中。",
        "動能衰減（價漲量縮）": f"{sym} 價格仍上行但主動買量轉弱，上行動能在數據上走弱。",
        "下方吸籌（價跌買增）": f"{sym} 價格下跌但主動買盤增加，出現下方承接的數據跡象。",
    }
    txt = base.get(sc, f"{sym} 出現合約數據異動（{sc}）。")
    extra = []
    if s.get("oi_chg") is not None: extra.append(f"OI 1h {s['oi_chg']:+.1f}%")
    if s.get("chg_1h") is not None: extra.append(f"價格 1h {s['chg_1h']:+.1f}%")
    tail = "（" + "、".join(extra) + "）" if extra else ""
    return txt + tail + " " + DISCLAIMER

def _ai_explain(s, key):
    """有 ANTHROPIC_API_KEY 時用 Claude 生成更自然的中立解讀。"""
    try:
        import urllib.request
        body = json.dumps({
            "model": "claude-haiku-4-5-20251001", "max_tokens": 180,
            "messages": [{"role": "user", "content":
                "你是中立的加密合約數據分析助手。根據以下數據，用繁體中文寫 2 句『中立的數據現象描述』，"
                "嚴禁任何買賣／做多做空／進場／止損／目標價／預測建議，只描述已發生的數據事實。\n"
                f"幣:{s['symbol']} 情境:{s['scenario']} 評分:{s['score']} "
                f"OI_1h:{s.get('oi_chg')}% 價格_1h:{s.get('chg_1h')}%"}]
        }).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=15).read())
        return d["content"][0]["text"].strip() + "（" + DISCLAIMER + "）"
    except Exception:
        return None

def explain(s):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        ai = _ai_explain(s, key)
        if ai:
            return ai
    return _template_explain(s)

# ---------- 偵測 ----------
def detect(board):
    out = []
    for c in board.get("coins", []):
        if c.get("oi_chg") is None:        # 只對有完整合約數據(已 enrich)的幣發訊號
            continue
        sc, scen = c["score"], c["scenario"]
        if abs(sc) >= 25:
            typ = "anomaly"
        elif ("衰減" in scen) or ("吸籌" in scen):
            typ = "divergence"
        else:
            continue
        out.append({
            "ts": int(time.time()), "symbol": c["symbol"], "type": typ,
            "scenario": scen, "score": sc, "grade": c["grade"],
            "chg_1h": c.get("chg_1h"), "oi_chg": c.get("oi_chg"),
            "exchanges": c.get("exchanges", []), "price": c.get("price"), "image": c.get("image"),
        })
    return out

def record(board):
    """偵測 + 30 分鐘內同幣同情境去重 + 寫 log。回全部訊號。"""
    sigs = _load()
    now = time.time()
    recent = {(s["symbol"], s["scenario"]) for s in sigs if now - s["ts"] < 1800}
    new = [s for s in detect(board) if (s["symbol"], s["scenario"]) not in recent]
    for s in new:
        s["explain"] = explain(s)
    if new:
        sigs += new
        _save(sigs)
    return sigs

def latest(n=80):
    return sorted(_load(), key=lambda s: s["ts"], reverse=True)[:n]
