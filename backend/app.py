#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""slash-radar 後端 Flask app：服務前端 + 提供評分榜 API。"""
import os, time, threading
from flask import Flask, jsonify, send_from_directory
import scoring

FRONT = os.path.join(os.path.dirname(__file__), "..", "frontend")
app = Flask(__name__, static_folder=None)

_board = {"t": 0.0, "data": None}
_lock = threading.Lock()

def get_board(ttl=60):
    now = time.time()
    with _lock:
        if _board["data"] and now - _board["t"] < ttl:
            return _board["data"]
    data = scoring.build_board(enrich_top=30)
    with _lock:
        _board["data"], _board["t"] = data, now
    return data

@app.route("/")
def home():
    return send_from_directory(FRONT, "index.html")

@app.route("/api/board")
def api_board():
    return jsonify(get_board())

@app.route("/static/<path:p>")
def static_files(p):
    return send_from_directory(os.path.join(FRONT, "static"), p)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8088, debug=False)
