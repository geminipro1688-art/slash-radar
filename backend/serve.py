#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""slash-radar server（stdlib）+ 背景訊號採集 + SEO(robots/sitemap)。
   本機: python serve.py → http://127.0.0.1:8088
   PaaS: 讀環境變數 PORT；容器內 HOST=0.0.0.0（Dockerfile 已設）。"""
import json, os, time, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import scoring, signals

FRONT = os.path.join(os.path.dirname(__file__), "..", "frontend")
DOMAIN = os.environ.get("SITE_DOMAIN", "https://radar.slash-invest.com")
_board = {"t": 0.0, "data": None}
_lock = threading.Lock()
_building = threading.Lock()   # P0-2: 同一時間只允許一個執行緒重建看板（驚群保護），且 build 不在 _lock 內

ROBOTS = (f"User-agent: *\nAllow: /\nDisallow: /app.html\nDisallow: /signals.html\n"
          f"Sitemap: {DOMAIN}/sitemap.xml\n")   # app/signals 為登入後內容，不收錄
def _sitemap():
    pages = ["/", "/calculator.html", "/learning.html"]   # 只放公開（吃 SEO）頁
    urls = "".join(f"<url><loc>{DOMAIN}{p}</loc><changefreq>hourly</changefreq></url>" for p in pages)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + "</urlset>")

def get_board(ttl=60):
    now = time.time()
    with _lock:  # read cache briefly
        cached = _board["data"]
        if cached and now - _board["t"] < ttl:
            return cached
    # P0-2: build moved OUT of _lock so a 10-25s rebuild won't block other requests
    if _building.acquire(blocking=False):  # only one thread rebuilds; others serve stale
        try:
            data = scoring.build_board(enrich_top=30)
            with _lock:
                _board["data"], _board["t"] = data, time.time()
            return data
        finally:
            _building.release()
    # stale-while-revalidate; first boot with no cache falls back to a sync build
    return cached if cached else scoring.build_board(enrich_top=30)

def _bg_collector():
    """背景每 120 秒掃描一次，讓訊號流持續累積。"""
    while True:
        try: signals.record(get_board())
        except Exception: pass
        time.sleep(120)

def _safe_file(base, rel):
    """防目錄穿越：解析後必須仍在 base 內。"""
    fp = os.path.normpath(os.path.join(base, rel))
    return fp if os.path.abspath(fp).startswith(os.path.abspath(base)) and os.path.isfile(fp) else None

_CT = {".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "application/javascript",
       ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png"}
def _ctype(fp):
    return _CT.get(os.path.splitext(fp)[1], "application/octet-stream")

class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        if isinstance(body, str): body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path == "/":
                fp = os.path.join(FRONT, "index.html")
                with open(fp, "rb") as f: self._send(200, f.read(), "text/html; charset=utf-8")
            elif path == "/api/board":     # 本機即時模式（Pages 上前端改讀 data/board.json）
                self._send(200, json.dumps(get_board(), ensure_ascii=False), "application/json; charset=utf-8")
            elif path == "/api/signals":
                self._send(200, json.dumps(signals.latest(), ensure_ascii=False), "application/json; charset=utf-8")
            elif path == "/robots.txt":
                self._send(200, ROBOTS, "text/plain; charset=utf-8")
            elif path == "/sitemap.xml":
                self._send(200, _sitemap(), "application/xml; charset=utf-8")
            elif path == "/healthz":
                self._send(200, "ok", "text/plain")
            else:
                # 服務 frontend/ 下的 .html / static/ / data/ 等靜態檔（與 Pages 同構）
                fp = _safe_file(FRONT, path.lstrip("/"))
                if fp:
                    with open(fp, "rb") as f: self._send(200, f.read(), _ctype(fp))
                else:
                    self._send(404, "not found", "text/plain")
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}), "application/json; charset=utf-8")

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8088"))
    host = os.environ.get("HOST", "127.0.0.1")  # PaaS/容器設 0.0.0.0
    threading.Thread(target=_bg_collector, daemon=True).start()
    print(f"slash-radar serving on http://{host}:{port}")
    ThreadingHTTPServer((host, port), H).serve_forever()
