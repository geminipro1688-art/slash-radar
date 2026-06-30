# slash-radar 交接文件（給 Cowork：修 bug + 優化）— 自包含版

> Cowork 只能收檔案、無法讀本機專案，故本文件自包含：讀這份 + 解壓附上的 zip 就能完整修改。
> 更新：2026-06-30。「✅已確認」=工具客觀驗證過；「🔎讀碼推斷」=從程式碼邏輯判斷。
> 定位以「特徵字串 / grep 關鍵字」為準（行號僅供大略）。

---

## ★ 修復進度

| 項 | 狀態 | 說明 |
|---|---|---|
| **P0-1 index.html 雙 body** | ✅ **已修** | 刪除頭部舊版殘留，現單套（驗證 body_count=1）。修復腳本見 §9。 |
| **P0-2 serve.py build 移出鎖** | ✅ **已修** | `get_board` 改 stale-while-revalidate + `_building` 驚群保護；build 不在 `_lock` 內。完整碼見 §11，已驗證 py_compile 通過。 |
| P1 enrich 並行化（10–25s→2–3s） | ⏳ 待 Cowork | §10 附可直接貼用的替換碼。 |
| P2 其餘（孤兒檔 / signals 解讀移鎖 / 雙所 OI 單位 / app·serve 收斂） | ⏳ 待 Cowork | §4-4、§4-5、§5。 |

> **Cowork 起手式**：解壓 zip（P0 已修的完整快照）→ 從 §10（P1）做起，P0 不必再動 → 每改一項照 §8 自測。

---

## 0. 一句話定位

合約數據雷達。聚合 **OKX + 幣安**雙所永續合約公開數據（價格動能 / OI / 資金費率 / 多空比 / 主動買賣量），編碼成**中立合規的「數據結構強度分數」+ 情境標籤**，吃競品 DataHunterX「登入牆後、零 SEO、給買賣點踩台灣投信投顧法」的空門，用免費 SEO 層導流交易所返佣。核心差異化＝中立 + 透明 factors + 不發幣 + **不給進出場/止損/止盈/目標價**（法遵紅線見 §7）。

## 1. 怎麼跑 / 部署

- 本機：`cd backend && python3 serve.py` → http://127.0.0.1:8088
- 依賴 `requirements.txt`＝`requests`,`flask`（serve.py 只需 requests；flask 給備用版 app.py）
- 容器 `Dockerfile`：python:3.12-slim，`WORKDIR /app/backend`，`CMD ["python","serve.py"]`，`HOST=0.0.0.0`，EXPOSE 8088
- 部署 `render.yaml`：Render docker、free plan、healthCheck `/healthz`、`SITE_DOMAIN=https://radar.slash-invest.com`
- 防休眠 `.github/workflows/keep-alive.yml`：GitHub Actions cron 定時 ping
- 自測：API `/api/board`、`/api/signals`、`/healthz`；離線 `python3 backend/test_engine.py`（印「✅ 方向分類正確」）。✅後端 6 檔 py_compile 全通過。

## 2. 檔案樹 + 逐檔作用

```
backend/
  serve.py        主伺服器(stdlib,正式跑這支)。路由 / /signals /calculator /api/board /api/signals /robots.txt /sitemap.xml /healthz /static/*;背景daemon每120s採集訊號
  scoring.py      評分引擎(護城河)。權重OI30/動能20/費率15/CVD12/多空比8;score_coin打分+情境+factors+flags+免責;build_board批量初評→top30 enrich→重評→分組
  sources.py      數據源層。OKX(tickers/oi/funding/lsr/oi_history/taker_cvd)+幣安(tickers/funding_all批量/oi/lsr)+CoinGecko(markets)+alternative.me(fear_greed);記憶體快取
  signals.py      訊號偵測+中立解讀。detect(|score|>=25 anomaly/衰減吸籌 divergence);record去重寫signals_log.json;explain有ANTHROPIC_API_KEY用Claude否則模板
  app.py          Flask備用版(與serve等價路由,目前部署不走這支)
  test_engine.py  離線冒煙測試
frontend/
  index.html      市場儀表板(✅P0-1已修單套)。strip+搜尋+tabs(偏多/偏空/分歧/全部/OI異動/板塊輪動)+卡片;REF返佣連結單一真相源;SECTORS板塊映射寫死
  signals.html    訊號專區(✅正常)
  calculator.html 倉位計算機(✅正常)
data/
  sample_board.json(308K) 🟠孤兒檔,無引用(§4-4)
  signals_log.json(188K)  訊號流持久化
demo-shots/ 8張demo截圖
Dockerfile / render.yaml / requirements.txt / DEPLOY.md / .gitignore / .github/workflows/keep-alive.yml
```

## 3. 資料流

```
/api/board → serve.get_board(60s cache) → scoring.build_board(enrich_top=30)
  → sources批量(okx_tickers/okx_oi+binance_tickers/binance_funding_all+gecko_markets)
  → 初評 → 挑top30逐一enrich(okx_oi_history/binance_oi/okx_taker_cvd/okx_lsr,序列+sleep0.08) → 重評 → 分組
背景每120s:_bg_collector→signals.record→detect→去重→explain→寫signals_log.json → /api/signals
```

## 4. Bug 清單

### 4-1【P0 ✅已修】index.html 雙 body
原 `<body>`/`<style>` 各 2 個（舊版三欄骨架#bull/#bear/#cand 與新版#grid疊加，頂部卡轉不停的骨架）。已刪前半舊版殘留，保留新版單套。腳本見 §9。

### 4-2【P0 ✅已修】serve.py build 在鎖內 → 重建時阻塞所有請求
原 `get_board` 把 10–25s 的 build 包在 `_lock` 內。已改 stale-while-revalidate + `_building` 驚群保護（§11）。

### 4-3【P1 ⏳】首次 /api/board 要 10–25s（enrich 序列+sleep）
top30 逐一序列呼叫 4 API+`sleep(0.08)`≈9.6s純sleep+120次序列往返。**修法見 §10 完整碼**（ThreadPoolExecutor 並行，降到 2–3s）。

### 4-4【P2 ✅已確認】data/sample_board.json(308K) 孤兒死檔
`grep -rl sample_board backend frontend` 無引用。確認非離線 demo 用途後刪除；或在 serve.py 加「上游全掛時 fallback 讀它」讓它被用到。

### 4-5【P2 🔎】signals 解讀同步呼叫 Claude，可能長時間佔資源
`record` 對每條新訊號同步呼叫 `_ai_explain`(Claude,timeout15s)。修法：解讀移背景佇列/鎖外；未設 `ANTHROPIC_API_KEY` 走模板(已支援)，設了也加總時限與並發上限。

## 5. 潛在風險

- **雙所 OI 單位**：`okx_oi()` 在 `oiUsd` 缺值時 fallback 到 `oiCcy`(幣本位數量,非USD)，可能污染 `oi_mcap_ratio` 與聚合 OI。建議統一 USD，缺值跳過。
- **app.py / serve.py 雙維護**：路由要手動同步，有漂移風險。擇一為單一真相源。
- **flask 多裝**：serve.py 不需 flask。無害可精簡。
- **前端 SECTORS 寫死**：新幣全歸「其他」，稀釋板塊輪動。
- **CORS 全開 `*`**：公開唯讀數據可接受；要防白嫖可限 origin / rate-limit。

## 6. 優化建議

1. P1（§10）最有感（首屏 10–25s→2–3s）。
2. **SEO/GEO**：目前純前端渲染，爬蟲拿不到內容。加 SSR 或 HTML 內預置最近快照——這是整站戰略目的（吃 SEO 空門），優先級高。
3. 上游全掛 fallback（接 4-4）。
4. serve.py `log_message` 全靜音，加最小存取日誌 / build 耗時計。

## 7. 🔴 法遵紅線（修改時絕對不可違反 — 是護城河不是限制）

依台灣《投信投顧法》，全站**只做「對已發生數據的中立統計呈現」**：
- ❌ 絕不輸出：進場價/止損/止盈/目標價/勝率/明牌/「可買進/該做多做空」。
- ✅ 只描述：已發生數據現象(OI增減、費率正負、量價背離)，每張卡/每條訊號強制附免責。
- 競品 DataHunterX、TokenMetrics 正因「給買賣點」在台踩線；我們用合規中立呈現吃它 SEO 空門。**任何讓 AI 解讀/文案「給操作建議」的修改都會摧毀差異化，不可做。**
- `scoring.py`、`signals.py` 開頭與 index.html footer 都有此註解，請保留。

## 8. 修復順序 + 驗證

| 序 | 項目 | 檔案 | 狀態 |
|---|---|---|---|
| 1 | index.html 雙 body | frontend/index.html | ✅已修 |
| 2 | serve.py build 移出鎖 | backend/serve.py | ✅已修 |
| 3 | enrich 並行化(§10) | backend/scoring.py | ⏳ |
| 4 | signals 解讀移鎖/加時限 | backend/signals.py、serve.py | ⏳ |
| 5 | sample_board 孤兒檔 | data/ | ⏳ |
| 6 | OI 單位、app/serve 收斂、§5/§6 | — | ⏳ |

**每改一項至少驗證**：① `python3 backend/test_engine.py` 通過；② `python3 backend/serve.py` 起得來、`/healthz` 回 ok、`/api/board` 回含 `market`+`coins` JSON、`/` 頁面只有一套 UI；③ 改 .py 後 `python3 -c "import py_compile;py_compile.compile('檔案',doraise=True)"` 無錯。

---

## 9. 附：index.html P0-1 修復腳本（已執行成功，供複查）

> 邏輯：保留＝[檔頭~第一個`<style>`前]+[第二個`<style>...</style>`]+`</head>`+[第二個`<body>`~檔尾]；刪除＝第一套 CSS+第一段 body。**已跑成功，現檔已單套(body_count=1)，無需重跑。**

```python
IDX="frontend/index.html"
src=open(IDX,encoding="utf-8").read()
if src.count("<style>")<2 or src.count("<body>")<2: raise SystemExit("已單套,不動作")
i_s1=src.find("<style>"); i_s2=src.find("<style>",i_s1+1)
i_s2e=src.find("</style>",i_s2)+len("</style>")
i_b1=src.find("<body>"); i_b2=src.find("<body>",i_b1+1)
result=src[:i_s1].rstrip()+"\n"+src[i_s2:i_s2e]+"\n</head>\n"+src[i_b2:]
assert result.count("<body>")==1 and result.count("<style>")==1 and 'id="grid"' in result and "<script" in result
open(IDX,"w",encoding="utf-8").write(result)
```

---

## 10. 附：P1 enrich 並行化 — 可直接貼上的替換碼

**目標**：把 `scoring.build_board` 裡「top30 逐一序列 enrich + sleep」改成 `ThreadPoolExecutor` 並行，首屏 10–25s→2–3s。OKX rubik 端點有限速，並發設 8、保留各 source 的 try 退避。

**改 `backend/scoring.py`**：檔頭 import 區加 `from concurrent.futures import ThreadPoolExecutor`，把 build_board 中「挑 top 去 enrich 的整段 for 迴圈」（`core, rest = [], []` 到 `rest.append(...)`）替換為：

```python
    core, rest = [], []
    head = base[:enrich_top]
    tail = base[enrich_top:]

    def _enrich(idx_c):
        i, (c, _) = idx_c
        sym = c["symbol"]
        oi_chg = S.okx_oi_history(sym)
        bn_oi_usd, oi_chg_bn = S.binance_oi(sym)
        if oi_chg_bn is not None:                 # 幣安 OI 為 USD 計價,優先
            oi_chg = oi_chg_bn
        if bn_oi_usd:
            c["oi_usd"] = (c["oi_usd"] or 0.0) + bn_oi_usd   # 聚合兩所 OI
        cvd = S.okx_taker_cvd(sym)
        lsr = S.okx_lsr(sym) if i < 14 else None  # 核心幣再補多空比
        return score_coin(c, oi_chg=oi_chg, funding=c["funding"], lsr=lsr, cvd=cvd)

    with ThreadPoolExecutor(max_workers=8) as ex:   # 並行 enrich,取代序列+sleep
        core = list(ex.map(_enrich, list(enumerate(head))))
    rest = [score_coin(c, funding=c["funding"]) for (c, _) in tail]
```

> 原本每個 source 呼叫後的 `time.sleep(0.08)` 一併移除。若並行後偶發 OKX 限速(429)，把 max_workers 降到 5，或在 `sources._get` 加「429 退避重試一次」。`_enrich` 內所有 `S.xxx` 失敗各自回 None，不會拖垮。
> 驗證：跑起來打 `/api/board`，首次回應從 10–25s 降到數秒；前 30 名應有 `oi_chg`/`factors` 完整欄位。

---

## 11. 附：serve.py P0-2 修改後的 get_board（已套用並 py_compile 通過）

```python
_board = {"t": 0.0, "data": None}
_lock = threading.Lock()
_building = threading.Lock()   # 同時只允許一個執行緒重建看板(驚群保護),且 build 不在 _lock 內

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
```
