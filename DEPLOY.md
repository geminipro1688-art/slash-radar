# slash-radar 上線指南（Render + radar.slash-invest.com）

零框架 Python 服務（stdlib `http.server` + requests），用 Docker 部署到 Render 免費方案，綁 slash-invest 子網域。

## 1. 推上 GitHub
```bash
cd "~/Downloads/claude agent/slash-radar"
git init && git add -A && git commit -m "slash-radar 初版"
git remote add origin <你的 GitHub repo URL>
git push -u origin main
```

## 2. Render 建立服務（讀 render.yaml 自動設定）
1. 登入 [render.com](https://render.com) → **New → Blueprint**
2. 連到 slash-radar 的 GitHub repo
3. Render 讀 `render.yaml` 自動建一個 Docker web service（free 方案）
4. 等 build 完成 → 得到 `https://slash-radar-xxxx.onrender.com`
5. 開該網址確認儀表板正常（首次 build 後 board 約 20 秒算完）

## 3. 綁定子網域 radar.slash-invest.com
1. Render → 服務 → **Settings → Custom Domains → 新增** `radar.slash-invest.com`
2. Render 會給你一個 CNAME 目標（例：`slash-radar-xxxx.onrender.com`）
3. 到 slash-invest 的 DNS 後台（Cloudflare 或主機商）新增：
   | 類型 | 名稱 | 值 |
   |---|---|---|
   | CNAME | `radar` | `<Render 給的目標>` |
   - 若用 Cloudflare：Proxy 狀態先設「僅 DNS（灰雲）」，等 Render 簽好憑證再決定是否開橘雲
4. 等 DNS 生效（數分鐘~數小時）→ Render 自動簽發 HTTPS

## 4. SEO 收錄（打對手空門的關鍵）
對手 DataHunterX 全站在登入牆後、Google 進不去；我們相反，要主動讓它收錄：
1. [Google Search Console](https://search.google.com/search-console) 新增資源 `radar.slash-invest.com`
2. 提交 sitemap：`https://radar.slash-invest.com/sitemap.xml`
3. 從 slash-invest 既有高權重文章（量化集群、交易所返佣文）**內鏈**到 radar 三頁，傳權重、加速收錄
4. 用 `submit_indexing.py`（你既有的 Indexing API 工具）送三個網址

## 5. 免費方案注意事項
- **Render free 會休眠**：閒置一段時間後首次訪問慢 ~30 秒。要常駐：升 $7/月，或用排程每 10 分鐘 ping `https://radar.slash-invest.com/healthz` 保活。
- `signals_log.json` 在容器內，服務重啟會清空（會自動重新累積，不影響）。

## 6. 選配：AI 訊號解讀升級
Render → Environment → 新增 `ANTHROPIC_API_KEY` → 訊號解讀自動從規則模板升級為 Claude 生成（claude-haiku-4-5）。

## 本機開發
```bash
cd backend && python3 serve.py   # → http://127.0.0.1:8088
```
