# line-connect

自架的 LINE Official Account ↔ Dify 橋接伺服器（FastAPI）。改寫自
[DomT00T/line-connect](https://github.com/DomT00T/line-connect)（Dify endpoint
plugin v0.9.7），脫離 Dify Cloud plugin 執行環境自行維運，並根治上游
issue #1（對話重置成開場白／request timeout）。

## 上游 issue #1 的根治

上游症狀是四個獨立缺陷疊加，本專案逐一處理：

| # | 上游缺陷 | 本專案對策 |
|---|---|---|
| 1 | webhook 同步等 Dify 回完才回 200 → LINE timeout 重送 | webhook 只做驗簽＋dedup＋落地 SQLite，立即回 200；實際處理交給常駐 worker |
| 2 | conversation_id 等 Dify 整段回完才寫入 → 中斷即孤兒對話 | SSE 第一個帶 cid 的 chunk 就立刻寫 DB（`on_conversation_id` callback） |
| 3 | 任何錯誤重試兩次就丟 cid 開新對話 → 一次網路抖動＝永久重置 | 錯誤三分類：transient 換 blocking 傳輸重試但 cid 不動；只有 Dify 明確回報 conversation 不存在才清 cid |
| 4 | dedup 用 KV list（read-modify-write race） | SQLite `UNIQUE` constraint，資料庫層解決競爭 |

## 架構

- **Sharded queue**：`crc32(chat_key) % WORKER_COUNT` 分片，同一 chat 永遠同一個
  worker → 嚴格 per-chat FIFO（防止連發訊息各自開新對話），免鎖。
- **inbox 一表兩用**：`dedup_key UNIQUE` 同時是 dedup 與 durable job queue；
  重啟後回收孤兒 job（已回覆的不重跑、超齡的放棄）。
- **回覆策略**：Reply API（免費）優先，token 預判過期或已用直接走 Push。
  整批被 LINE 拒絕時退回純文字重送一次。
- **Media debounce**：asyncio timer，buffer 依 `(chat_key, kind)` 分開
  （image 與 file 不互相污染）。
- **Graceful shutdown**：readyz 先轉紅 → drain → 未完成 job 留 DB 下次啟動回收。

## 管理後台（Admin Dashboard）

移植自上游 plugin 的營運後台（vanilla JS SPA，無 build step）。**預設不存在**：
`ADMIN_PASSWORD` 沒設就完全不掛載路由，`/admin` 回 404。

設定密碼後 `GET /admin` 出頁面、`POST /admin` 收 action（單一端點 + `action` 欄位
分派，沿用上游形態，所以 UI 的 API 層零改動）。

**功能**：對話清單／歷史／typing、chat meta（自訂名稱、備註、星號、標籤）、
主動發訊、Analytics（活躍度／回應時間分布／使用者成長）、標籤與範本管理、
CSV／JSON 匯出、媒體庫。

**未移植（Phase B）**：per-chat bot 開關、營業時間排程、自動回覆、廣播。
對應的 UI 區塊已從 app.js 移除。

### 與上游的行為差異（刻意）

| 項目 | 上游 | 本專案 |
|---|---|---|
| 密碼比對 | `!=`（時序可測） | `hmac.compare_digest` |
| token 驗證失敗 | **退回接受原始密碼**（等於 token 沒有意義） | 無 fallback，只有 `login` 會看密碼 |
| `custom_name` 影響範圍 | 連 Dify end-user id 一起改 → 改名等於 fork 該使用者的 Dify 對話 | 只覆蓋 `inputs.displayName`；`dify_user` 不變、對話延續 |
| `/clear` 指令 | 只刪 cid | 同樣只刪 cid（**不可**整列刪除，否則 admin meta 全失） |
| 匯出 | 前端組 CSV，只有已載入的 ≤100 則 | 後端全量（上限 `ADMIN_EXPORT_MAX_ROWS`） |
| typing indicator | 15 個散落的 set/clear 呼叫點 | 零寫入，由 `inbox` 未完成的 job 推導 |
| Analytics | 每則訊息 6–8 次 KV 計數器讀寫 | 零採集，全部從 `messages` 表 SQL 聚合 |

### 已知取捨

- `get_bot_info` 免認證（登入頁要顯示 OA 名稱與頭像，沿用上游）。
- `clear_history` 會回頭改變 Analytics 數字——兩者同一個資料來源。
- Analytics 的日／時分桶依 **UTC** 日切（與上游一致）。
- `errors` 沿用上游 `in − out` 近似值。改用 inbox 精確計數會被 3 天 dedup
  retention 截斷，7／30 天區間反而低報。
- 頁面依賴外部 CDN（Google Fonts、Chart.js、Lucide），離線環境會退化。
- rate limit 存在記憶體：重啟歸零、多副本無效——但 SQLite 架構本來就綁定單副本。

## 開發

```bash
uv sync                 # 安裝依賴（Python 3.12）
cp .env.example .env    # 填入三個必填值
make run                # uvicorn --reload :8000
make check              # ruff + mypy(strict) + pytest
```

測試分兩層：`tests/unit`（純邏輯，無 mock）與 `tests/integration`
（ASGITransport + 真 SQLite + respx mock LINE/Dify）。

## 設定

全部走環境變數，完整清單見 [.env.example](.env.example)。必填：

| 變數 | 說明 |
|---|---|
| `LINE_CHANNEL_SECRET` | LINE Developers → channel → Basic settings |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Developers → Messaging API → long-lived token |
| `DIFY_API_KEY` | Dify app → API Access（`app-…`） |

值得注意的行為開關：

| 變數 | 預設 | 說明 |
|---|---|---|
| `MEDIA_SUPPORT_ENABLED` | `false` | 圖片／影音／檔案上傳到 Dify |
| `MEDIA_DEBOUNCE_SECONDS` | `0` | >0 時連發媒體合併為一次 Dify 呼叫 |
| `FLEX_MESSAGE_ENABLED` | `false` | Markdown 轉 LINE Flex Message |
| `DIFY_CONVERSATION_ERROR_MARKERS` | `Conversation Not Exists,…` | 判定「對話不存在」的 4xx body 子字串（可調，不用改程式） |
| `ADMIN_PASSWORD` | 空 | 空＝後台整組不掛載（`/admin` 回 404）。設了才有後台 |
| `MEDIA_STORE_ENABLED` | `false` | 把收到的媒體存到 `MEDIA_DIR` 供後台瀏覽 |
| `DEBUG_MODE` | `false` | **會把 traceback 送進 LINE 對話，正式環境務必關閉** |

## LINE Developers 設定

1. 建立（或沿用）Messaging API channel。
2. Webhook URL 填 `https://<你的網域>/line/webhook`，開啟 **Use webhook**。
3. 建議開啟 **Webhook redelivery**（單 replica 部署間隙的保險）。
4. 關閉「自動回應訊息」（Auto-reply messages），否則會跟 bot 回覆重複。
5. 按 **Verify** 應顯示 Success（本服務對空 events 回 200）。

## 部署

正規流程是推 `vX.Y.Z` tag 讓 CI 建置並更新 manifests（見
[DEPLOYMENT.md](DEPLOYMENT.md)）。手動建置只用於本機驗證：

```bash
docker build -t ghcr.io/tim80411/line-connect:<X.Y.Z> .
```

k8s manifests 在 [k8s-apps](https://github.com/tim80411/k8s-apps) repo 的
`apps/line-connect/`（ArgoCD app-of-apps 自動部署）。**硬性約束**（in-memory
queue + SQLite 單寫入者）：

- `replicas: 1` + `strategy: Recreate`（不可 RollingUpdate）
- PVC 掛 `/data`（RWO），`fsGroup: 10001`
- `terminationGracePeriodSeconds: 40` > `DRAIN_DELAY(5) + SHUTDOWN_GRACE(25)`
- liveness `/healthz`（不碰 DB/Dify）、readiness `/readyz`（只查 DB 可寫與 draining）

Secrets 走 Sealed Secrets：填 `apps/line-connect/secret.template.yaml` 後用
`kubeseal` 加密，只 commit sealed 版本。

## 驗收（部署後人工）

1. 對話 3 輪，確認上下文延續。
2. `kubectl rollout restart deploy/line-connect -n line-connect` 後問「我剛剛問你什麼」→ 答得出來（cid 持久化）。
3. Dify 端故意報錯 → 收到錯誤通知，且下一則訊息仍在同一對話（cid 未被清）。
4. 連發 5 則 → 5 則回覆，順序正確無重複。
5. `/clear` → 確認訊息，之後開新對話。

後台（有設 `ADMIN_PASSWORD` 才做）：

6. 手機發訊 → dashboard inbox 即時出現；開對話看得到歷史與 typing。
7. 改 custom_name → 下一則 Dify 回覆稱呼改變，但**對話不重開**（cid 不變）。
8. composer 發訊 → 手機收到，歷史多一列 admin。
9. `/clear` → 對話重開，但備註／標籤／星號**還在**。
10. Analytics 數字與 `messages` 表手動 SQL 聚合一致。
11. 匯出 CSV 超過 100 則（證明是全量，不是前端已載入的那份）。
12. 錯密碼 5 次 → 鎖 5 分鐘；無 token 打 action → 401。

## License

上游為 MIT（見 upstream repo）；本專案沿用。
