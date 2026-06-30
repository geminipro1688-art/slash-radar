# slash-radar 派工單（給 Cowork）

> 建立 2026-06-30。本檔是「分工/驗收」視角；**技術細節、完整替換碼、Bug 根因**全在同目錄 `HANDOFF-cowork-bugfix.md`，本檔只引用它的章節（§x）。
> 兩份一起讀：先讀本派工單認領任務 → 跳 HANDOFF 對應 § 拿碼與細節。

---

## 0. 怎麼拿程式碼 / 怎麼交回（重要 — repo 是私有）

- **拿**：解壓附上的 `slash-radar-snapshot.zip`（= GitHub `main` 最新快照，含本派工單 + HANDOFF + 全部程式碼）。
  - ⚠️ repo 為 **私有**，Cowork 環境無 GitHub 認證 → **無法直接 `git clone`**，一律以這份 zip 為準。
- **跑**：`cd backend && python3 serve.py` → http://127.0.0.1:8088 （只需 `requests`）。
- **交回**：Cowork **不能 push 私有 repo**。改完後把「改動過的檔案」（或整包）交回給 Tony →
  由 **Claude Code 在本機** 重新 `git clone` GitHub → 套用 Cowork 改動 → `commit` + `push`。
  - 每個任務包交回時請附：①改了哪些檔 ②§8 三項自測結果 ③有無偏離原設計。

## 🔴 動工前必讀：法遵紅線（HANDOFF §7）— 是護城河不是限制

全站只做「對已發生數據的**中立統計呈現**」。
**絕不**輸出：進場價 / 止損 / 止盈 / 目標價 / 勝率 / 明牌 /「可買進 / 該做多做空」。
任何讓評分、訊號、AI 解讀、文案「給操作建議」的改動都會**摧毀差異化**，不可做。
`scoring.py`、`signals.py` 開頭與 `index.html` footer 的此註解請**保留**。

---

## 1. 任務分工表（按優先級）

| 包 | 優先 | 任務 | 改哪些檔 | 參考 | 狀態 |
|---|---|---|---|---|---|
| **A** | 🥇 P1 | enrich 並行化（首屏 10–25s → 2–3s） | `backend/scoring.py` | HANDOFF §10（**附完整替換碼**）、§4-3 | ⏳ |
| **B** | 🥈 P2 | signals 解讀移出同步路徑（加時限/並發上限） | `backend/signals.py`、`backend/serve.py` | HANDOFF §4-5 | ⏳ |
| **C** | 🥉 P2 | 正確性 + 清理（OI 單位 / 孤兒檔 / 雙檔收斂 / 板塊寫死） | `backend/sources.py`、`backend/serve.py`、`backend/app.py`、`frontend/index.html`、`data/` | HANDOFF §4-4、§5 | ⏳ |
| **D** | ⭐ 戰略 | SEO/GEO：HTML 內預置快照 / SSR（爬蟲拿得到內容） | `backend/serve.py`、`frontend/index.html` | HANDOFF §6-2 | ⏳ |

> P0（index.html 雙 body、serve.py build 移出鎖）**已修完**，不必再動（HANDOFF §4-1、§4-2）。
> **建議順序 A → D → B → C**：A 體感最強、D 是整站存在目的（吃 SEO 空門）優先級高，B/C 為穩定性與清理。各包互相獨立、可分開認領與交回。

---

## 2. 各任務包驗收標準

### 包 A — enrich 並行化
- [ ] `backend/scoring.py` 依 HANDOFF §10 用 `ThreadPoolExecutor(max_workers=8)` 取代「top30 序列 enrich + `sleep(0.08)`」。
- [ ] `/api/board` 首次回應從 10–25s 降到數秒；前 30 名 `oi_chg` / `factors` 欄位完整。
- [ ] 偶發 OKX 429 時：`max_workers` 降到 5，或 `sources._get` 加「429 退避重試一次」。
- [ ] 通過 §8 三項自測。

### 包 B — signals 解讀移鎖
- [ ] `record` 不再對每條新訊號**同步**呼叫 `_ai_explain`；移到背景佇列 / 鎖外。
- [ ] 設了 `ANTHROPIC_API_KEY` 也要有總時限 + 並發上限；未設走模板（已支援）。
- [ ] 背景採集不阻塞 `/api/signals`。
- [ ] 通過 §8 三項自測。

### 包 C — 正確性 + 清理
- [ ] **OI 單位**：`sources.okx_oi()` 缺 `oiUsd` 時**不要** fallback 到 `oiCcy`（幣本位），統一 USD、缺值跳過（HANDOFF §5）。
- [ ] **孤兒檔** `data/sample_board.json`（308K）：擇一 → 刪除，或改成「上游全掛時 fallback 讀它」讓它被用到（§4-4）。
- [ ] **雙檔收斂**：`app.py` / `serve.py` 擇一為單一真相源（目前部署走 serve.py）；或明確標註 app.py 為備用、凍結。
- [ ] **前端板塊**：`index.html` 的 `SECTORS` 寫死 → 新幣全歸「其他」，改動態映射。
- [ ] 通過 §8 三項自測（尤其 `test_engine.py` 印「✅ 方向分類正確」）。

### 包 D — SEO/GEO（戰略）
- [ ] `curl http://127.0.0.1:8088/`（不執行 JS）能看到實際榜單內容與關鍵字，而非空殼。
- [ ] 作法：serve.py 在回 `/` 時把最近一次 board 快照預置進 HTML，或加 SSR。
- [ ] 不破壞前端互動（strip / 搜尋 / tabs / 卡片）。
- [ ] 維持法遵紅線（預置內容同樣不得含操作建議）。

---

## 3. 共用自測（每包交回前都要跑）— HANDOFF §8

1. `python3 backend/test_engine.py` → 印「✅ 方向分類正確」。
2. `python3 backend/serve.py` 起得來；`/healthz` 回 ok；`/api/board` 回含 `market`+`coins` 的 JSON；`/` 頁面只有一套 UI。
3. 改過的 `.py` 各跑 `python3 -c "import py_compile;py_compile.compile('檔名',doraise=True)"` 無錯。

---

## 4. 部署備忘（Cowork 不需操作，交回後由 Claude Code 處理）

- 容器 `Dockerfile`（python:3.12-slim，跑 `backend/serve.py`）；`render.yaml`（Render free plan，healthCheck `/healthz`）。
- 防休眠 `.github/workflows/keep-alive.yml`（GitHub Actions cron 定時 ping）。
- push 回 GitHub `main` 後 Render 自動 rebuild。
