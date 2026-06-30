# slash-radar 上線指南（GitHub Pages + Actions）

**架構**：GitHub Actions 每 15 分鐘在雲端跑引擎算好整盤 → 寫成靜態 JSON 快照 →
GitHub Pages 出純靜態站讀快照。使用者只讀「算好的結果」→ **秒開、零冷啟動、上游限速不會半殘**。
登入採「混合」：公開著陸頁/學習頁/計算機吃 SEO，完整雷達（app/signals）在軟性登入後。

```
GitHub Actions (cron 15min)
  └─ python backend/build_snapshot.py
       ├─ scoring.build_board(enrich_top=80)   雙所聚合 + 並行 enrich
       ├─ 寫 frontend/data/board.json / signals.json
       └─ 注入 frontend/index.html 的 <!--SNAPSHOT--> 樣本（SEO）
  └─ upload-pages-artifact(frontend) → deploy-pages   ← Pages 永遠是最新快照
```

## 1. 首次設定（一次性）
1. **repo 設公開**（免費版 Pages 需要）：`gh repo edit <owner>/slash-radar --visibility public`
2. **Pages 來源設為 Actions**：repo → Settings → Pages → Build and deployment → Source = **GitHub Actions**
   （或 `gh api -X POST repos/<owner>/slash-radar/pages -f build_type=workflow`）
3. push 後 `build-and-deploy` 會自動跑，完成後網址：`https://<owner>.github.io/slash-radar/`

## 2. 日常更新
- 改碼 → `git push origin main` → Actions 自動 build + deploy。
- 資料每 15 分鐘自動刷新（cron），不需手動。可在 repo → Actions → 手動 `Run workflow` 立即更新。

## 3. 綁自訂網域（選配）radar.slash-invest.com
1. repo → Settings → Pages → Custom domain 填 `radar.slash-invest.com`
2. DNS 新增 `CNAME radar → <owner>.github.io`
3. 等憑證簽發（Pages 自動 HTTPS）。綁好後把各 .html 的 canonical/og 網域對齊即可。

## 4. SEO 收錄（打對手空門的關鍵）
對手整站在登入牆後、Google 進不去；我們相反——公開層要主動讓它收錄：
1. Google Search Console 新增資源（github.io 子路徑或自訂網域）
2. 提交 `…/sitemap.xml`（只含 `/`、`/calculator.html`、`/learning.html` 公開頁）
3. 從 slash-invest 高權重文章內鏈到著陸頁/學習頁，傳權重、加速收錄
4. `app.html`、`signals.html` 已設 `noindex`（登入後內容不收錄）

## 5. 改登入帳密
`frontend/static/auth.js` 的 `ACCOUNTS` 換成新的 `SHA-256("帳號:密碼")`：
```bash
printf '%s' "你的帳號:你的密碼" | shasum -a 256
```
預設：`slash / slash2026`（另留 `tony / tony` 可刪）。⚠️ 靜態站軟門檻、原始碼可見，等同競品 tony/tony，非高強度防護。

## 6. 選配：AI 訊號解讀升級
在 workflow 加 secret `ANTHROPIC_API_KEY`（repo → Settings → Secrets → Actions），
並在 deploy-pages.yml 的 build 步驟 env 帶入 → 訊號解讀從規則模板升級為 Claude 生成。
未設則走中立模板（已內建，合規）。

## 本機開發 / 預覽
```bash
cd backend && SNAPSHOT_ENRICH=40 python3 build_snapshot.py   # 先產一份本機快照
python3 serve.py                                              # → http://127.0.0.1:8088
```
serve.py 與 Pages 同構：服務 frontend/ 下的 .html / static/ / data/。

## 備用部署（Render，非主路）
`Dockerfile` / `render.yaml` / `backend/serve.py` 仍可用即時後端方式部署到 Render，
但會有免費版冷啟動 + 上游限速即時反映的問題，已非主路線，保留供需要常駐後端時參考。
