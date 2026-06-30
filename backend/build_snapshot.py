#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
離線快照批次 —— 由 GitHub Actions 定時在雲端執行。
把重運算（整盤 enrich + 評分 + 訊號偵測）算好，寫成靜態 JSON 給 GitHub Pages 直接讀。

為什麼這樣設計（解決「不穩定 + 太慢」）：
  - 重活搬離使用者請求路徑：訪客只讀「算好的 JSON」→ 秒開、零冷啟動。
  - 失敗容錯：build 失敗 / 幣數過少時【保留上一份好快照】，使用者永遠看不到半殘。
  - enrich_top 提高到 80（離線沒人在等）→ 更多幣有真實 OI 結構 = 更準更完整。

產出：
  frontend/data/board.json     市場整盤快照（市場指標 + 全幣評分卡 + 分組）
  frontend/data/signals.json   訊號流（每條附中立解讀）
  並把 top 樣本注入 frontend/index.html 的 <!--SNAPSHOT--> 區（爬蟲拿得到內容 = 吃 SEO）
"""
import json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring, signals  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONT = os.path.join(ROOT, "frontend")
DATA = os.path.join(FRONT, "data")


def _build_with_retry():
    enrich = int(os.environ.get("SNAPSHOT_ENRICH", "80"))
    err = None
    for attempt in range(3):
        try:
            b = scoring.build_board(enrich_top=enrich)
            if b and b.get("coins") and len(b["coins"]) >= 50:
                return b
            err = f"coins too few ({len(b.get('coins', [])) if b else 0})"
        except Exception as e:
            err = e
        print(f"[snapshot] build attempt {attempt + 1} failed: {err}")
        time.sleep(3 * (attempt + 1))
    return None


def _attach_explain(board):
    """給已 enrich（有 oi_chg）的幣加一句中立數據解讀，dashboard 卡片直接顯示（門檻低、體感升級大）。"""
    for c in board.get("coins", []):
        if c.get("oi_chg") is not None and c.get("score") is not None:
            try:
                c["explain"] = signals._template_explain(c)
            except Exception:
                pass


def _render_sample_rows(board, n=8):
    """渲染 top 樣本為靜態 HTML（注入著陸頁，給爬蟲讀 = SEO）。中立呈現、無操作建議。"""
    coins = sorted(board.get("coins", []), key=lambda x: abs(x.get("score", 0)), reverse=True)[:n]
    rows = []
    for c in coins:
        sc = c.get("score", 0)
        cls = "up" if sc >= 20 else "down" if sc <= -20 else "neu"
        sign = "+" if sc > 0 else ""
        rows.append(
            f'<tr><td class="s">{c.get("symbol","")}</td>'
            f'<td>{c.get("sector","")}</td>'
            f'<td class="{cls}">{sign}{sc}</td>'
            f'<td>{c.get("scenario","")}</td>'
            f'<td class="{cls}">{c.get("level","")}</td></tr>')
    upd = time.strftime("%Y-%m-%d %H:%M", time.gmtime(board.get("updated", time.time()))) + " UTC"
    m = board.get("market", {})
    head = (f'<p class="snapshot-meta">最近更新 {upd}　·　掃描 {m.get("total_coins","–")} 幣　·　'
            f'偏多 {m.get("bull_n","–")}／偏空 {m.get("bear_n","–")}　·　恐懼貪婪 '
            f'{(m.get("fear_greed") or {}).get("value","–")}</p>')
    table = ('<table class="snapshot-table"><thead><tr>'
             '<th>幣種</th><th>板塊</th><th>數據評分</th><th>情境</th><th>結構</th>'
             '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>')
    return head + table


def _inject_landing(board):
    idx = os.path.join(FRONT, "index.html")
    if not os.path.exists(idx):
        return
    src = open(idx, encoding="utf-8").read()
    a, b = "<!--SNAPSHOT_START-->", "<!--SNAPSHOT_END-->"
    i, j = src.find(a), src.find(b)
    if i == -1 or j == -1:
        return
    new = src[:i + len(a)] + "\n" + _render_sample_rows(board) + "\n" + src[j:]
    open(idx, "w", encoding="utf-8").write(new)
    print("[snapshot] index.html sample injected (SEO)")


def _write_seo():
    """產生靜態 robots.txt / sitemap.xml（Pages 無後端路由）。SITE_BASE 換自訂網域只改這個環境變數。"""
    base = os.environ.get("SITE_BASE", "https://geminipro1688-art.github.io/slash-radar").rstrip("/")
    pub = ["/", "/calculator.html", "/learning.html"]   # 只放公開（吃 SEO）頁
    robots = (f"User-agent: *\nAllow: /\nDisallow: /app.html\nDisallow: /signals.html\n"
              f"Sitemap: {base}/sitemap.xml\n")
    urls = "".join(f"<url><loc>{base}{p}</loc><changefreq>hourly</changefreq></url>" for p in pub)
    sitemap = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + "</urlset>")
    open(os.path.join(FRONT, "robots.txt"), "w", encoding="utf-8").write(robots)
    open(os.path.join(FRONT, "sitemap.xml"), "w", encoding="utf-8").write(sitemap)
    print(f"[snapshot] robots.txt / sitemap.xml written (base={base})")


def main():
    os.makedirs(DATA, exist_ok=True)
    _write_seo()
    board = _build_with_retry()
    bpath = os.path.join(DATA, "board.json")
    if board is None:
        print("[snapshot] build failed; keeping previous board.json")
        if not os.path.exists(bpath):
            sys.exit(1)   # 連種子都沒有才算硬失敗
        return
    _attach_explain(board)
    json.dump(board, open(bpath, "w", encoding="utf-8"), ensure_ascii=False)
    m = board["market"]
    print(f"[snapshot] board.json OK: {len(board['coins'])} coins | "
          f"{m['bull_n']}↑/{m['bear_n']}↓ | breadth {m.get('breadth')} | altseason {m.get('altseason')}")
    try:
        signals.record(board)
        json.dump(signals.latest(120), open(os.path.join(DATA, "signals.json"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        print(f"[snapshot] signals.json OK: {len(signals.latest(120))} signals")
    except Exception as e:
        print(f"[snapshot] signals skipped: {e}")
    _inject_landing(board)


if __name__ == "__main__":
    main()
