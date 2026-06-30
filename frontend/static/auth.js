/* slash-radar 軟性登入閘（靜態站）
 * ─────────────────────────────────────────────────────────────
 * ⚠️ 這是「示意級」門檻：靜態站原始碼可見，等同競品 tony/tony 的軟門檻，
 *    用來做「產品感 / 會員入口」，不是高強度防護。要真正鎖內容請改後端驗證。
 *
 * 預設帳密：  帳號 slash   密碼 slash2026
 * 要改 / 加帳號：把下面 ACCOUNTS 換成新的 SHA-256("帳號:密碼")。產生雜湊：
 *    printf '%s' "你的帳號:你的密碼" | shasum -a 256
 */
const ACCOUNTS = [
  "b41df7fb8c156d5c5e0295ceedd8cde6756a84802d6a6328a3ca562935076dfd", // slash : slash2026
  "da4b5aa0a91d48f401154998d494e611762baa123f483d795c8ce10f3704cd26", // tony  : tony （沿用熟悉帳密，可刪）
];

async function _sha256(t) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t));
  return [...new Uint8Array(buf)].map(x => x.toString(16).padStart(2, "0")).join("");
}
async function slashLogin(user, pass) {
  const h = await _sha256(`${(user || "").trim()}:${pass || ""}`);
  if (ACCOUNTS.includes(h)) {
    sessionStorage.setItem("slash_auth", "1");
    sessionStorage.setItem("slash_user", (user || "").trim());
    return true;
  }
  return false;
}
function slashAuthed() { return sessionStorage.getItem("slash_auth") === "1"; }
function slashUser() { return sessionStorage.getItem("slash_user") || ""; }
function slashLogout() {
  sessionStorage.removeItem("slash_auth");
  sessionStorage.removeItem("slash_user");
  location.href = "index.html";
}
/* 在「需登入」頁面最上面呼叫：未登入就踢回著陸頁，並記住目的頁。 */
function slashRequire() {
  if (!slashAuthed()) {
    const next = location.pathname.split("/").pop() || "app.html";
    location.replace("index.html?next=" + encodeURIComponent(next) + "#login");
  }
}
