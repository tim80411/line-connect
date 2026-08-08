# DEPLOYMENT.md — 部署操作手冊（供 LLM agent 使用）

> 本文件的讀者是操作部署的 LLM agent 或工程師。所有命令可直接執行；
> 每個操作段落都附驗證命令——**執行後必須驗證，不可只看命令有沒有報錯**。

## 系統一覽

```
LINE OA ──webhook──> line-connect.zhiri.app (Cloudflare proxied)
                        └─> OCI k8s (namespace: line-connect, 單 pod)
                              ├─ SQLite @ PVC /data（對話狀態，唯一有狀態資源）
                              └──> Dify Cloud chat-messages API
```

| 資源 | 位置 |
|---|---|
| 程式碼 repo | `github.com/tim80411/line-connect`（private） |
| Image | `ghcr.io/tim80411/line-connect:<X.Y.Z>`（arm64，private） |
| 部署 manifests | `github.com/tim80411/k8s-apps` → `apps/line-connect/` |
| GitOps | ArgoCD app-of-apps，push 到 k8s-apps `main` 即自動 sync |
| Cluster 存取 | 本機無法直連；一律 `ssh oci-cp "kubectl …"` |

## 正規發版流程（唯一正道）

**推 `vX.Y.Z` tag 就是部署**。不要手動 docker push、不要手動改 cluster。

```bash
# 1. 確定 main 是綠的（CI: test job）且工作樹乾淨
cd ~/self/products/line-connect
git status --short          # 應為空
gh run list --limit 1       # 最新 run 應 success

# 2. 版本號：pyproject.toml 的 version 與 tag 一致（去掉 v 前綴）
#    先改 pyproject.toml [project] version 與 src/line_connect/__init__.py
#    的 __version__，commit + push

# 3. 推 tag（這一步觸發部署）
git tag vX.Y.Z && git push origin vX.Y.Z
#    （`gh release create vX.Y.Z --generate-notes` 也會建同名 tag，同樣觸發，
#      想留 release notes 時用這個。）
```

自動化鏈路（`.github/workflows/docker.yml`）：

```
push tag vX.Y.Z
  → test job（ruff + mypy + pytest，紅了就全停）
  → build job（QEMU arm64 → push ghcr.io/tim80411/line-connect:X.Y.Z）
  → deploy job（用 K8S_APPS_DEPLOY_KEY 把 k8s-apps 的
      apps/line-connect/deployment.yaml image tag 改成 X.Y.Z，
      commit + push main）
  → ArgoCD 偵測到 main 變更 → Recreate pod（舊停新起，中斷數秒）
```

### 發版後驗證（必做，全部通過才算部署完成）

```bash
# a. workflow 三個 job 全綠
gh run watch --exit-status "$(gh run list --workflow=docker.yml --limit 1 --json databaseId -q '.[0].databaseId')"

# b. k8s-apps 出現部署 commit
gh api repos/tim80411/k8s-apps/commits/main -q '.commit.message' | head -1
#    預期含 "chore(line-connect): deploy vX.Y.Z"

# c. pod 換版且 Ready（ArgoCD sync 最多 ~3 分鐘）
ssh oci-cp "kubectl get pods -n line-connect -o jsonpath='{.items[0].spec.containers[0].image} {.items[0].status.phase}'"
#    預期：ghcr.io/tim80411/line-connect:X.Y.Z Running

# d. 對外健康 + 驗簽牆
curl -s -o /dev/null -w '%{http_code}\n' https://line-connect.zhiri.app/healthz            # 200
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://line-connect.zhiri.app/line/webhook -d '{}'  # 400（無簽章必拒）

# e. 對話延續（issue #1 迴歸）：pod 剛重啟過，向 OA 發訊息
#    問「我剛剛問你什麼」——答得出來 = SQLite cid 存活 ✅
```

## Rollback

```bash
# 找上一版
gh release list --repo tim80411/line-connect --limit 5
# 直接改 k8s-apps 的 image tag 回舊版（image 都還在 ghcr）
cd ~/self/infra/k8s-apps && git pull --ff-only origin main
sed -i '' -E 's|(image: ghcr.io/tim80411/line-connect:).*|\1<舊版號>|' apps/line-connect/deployment.yaml
git add apps/line-connect/deployment.yaml && git commit -m "revert(line-connect): rollback to <舊版號>" && git push origin main
```

資料相容注意：若新版加過 DB migration（`storage/migrations/`），舊程式碼讀新 schema
通常可行（migration 只增不改），但 rollback 跨 migration 前先確認該檔案內容。

## Secret 輪替

三個 secret：`LINE_CHANNEL_SECRET` / `LINE_CHANNEL_ACCESS_TOKEN` / `DIFY_API_KEY`。

```bash
# 1. 填模板（勿 commit 明文）
cp ~/self/infra/k8s-apps/docs/line-connect-secret.template.yaml /tmp/lc-secret.yaml
$EDITOR /tmp/lc-secret.yaml
# 2. 加密 → 覆蓋 sealed-secret.yaml → 刪明文
cd ~/self/infra/k8s-apps
kubeseal --cert sealed-secrets-cert.pem --format yaml < /tmp/lc-secret.yaml > apps/line-connect/sealed-secret.yaml
rm /tmp/lc-secret.yaml
git add apps/line-connect/sealed-secret.yaml && git commit -m "chore(line-connect): rotate secrets" && git push origin main
# 3. reloader 會自動重啟 pod（deployment 有 reloader.stakater.com/auto）；驗證同上 c/d
```

## 不可變的基礎設施約束（改了就會壞，禁止「優化」）

| 約束 | 原因 |
|---|---|
| `replicas: 1` | in-memory sharded queue + SQLite 單寫入者；兩個 pod = 對話分叉 + DB 損毀 |
| `strategy: Recreate` | RWO PVC 不能同時掛兩 pod |
| `nodeSelector: cp` | local-path PVC 是節點本地的，pod 必須跟著資料走 |
| `terminationGracePeriodSeconds: 40` | > app 內 DRAIN(5)+GRACE(25) 與 uvicorn 35s 收尾 |
| liveness 不碰 DB/Dify | 外部依賴故障不該重啟 pod |
| image 一律精確版號 | 禁 `latest`；ArgoCD 以 manifest 為準 |

## Troubleshooting 對照表

| 症狀 | 原因 | 處置 |
|---|---|---|
| pod `ErrImagePull` | ghcr pull secret 失效/缺 | `cd ~/self/infra/k8s-apps && bash scripts/apply-ghcr-secret.sh`（需 gh token 有 `read:packages`；卡住＝在等互動授權，先 `gh auth refresh -s read:packages`） |
| pod `CreateContainerConfigError` | `line-connect-secret` 不存在/缺 key | 檢查 SealedSecret 是否 sync：`ssh oci-cp "kubectl get sealedsecret,secret -n line-connect"`；重做 Secret 輪替流程 |
| 對外 503 | pod 未 ready | `ssh oci-cp "kubectl get pods -n line-connect"`，看上面兩列 |
| 憑證錯誤/過期 | cert-manager 挑戰失敗 | `ssh oci-cp "kubectl get certificate,challenge -n line-connect"`；確認 Cloudflare DNS `line-connect` 記錄存在 |
| 使用者說「對話又重置了」 | 看 log 找 `cid_invalidated`（正常路徑）vs 異常 | `ssh oci-cp "kubectl logs -n line-connect -l app=line-connect --tail=200"` 以 `chat_key` 過濾整條鏈路 |
| LINE console Verify 失敗 | 多半是 400 vs 200 判定 | 空 events 應回 200：`curl` 帶合法簽章驗證；無簽章 400 是預期 |
| deploy job 推 k8s-apps 失敗 | main 併發推擠（retry 5 次仍輸）| 重跑 deploy job：`gh run rerun <run-id> --job <deploy-job-id>`，或手動照 Rollback 一節的 sed+push |
| webhook 收 403（app 沒收到） | Cloudflare WAF 擋非瀏覽器 UA 的測試請求 | LINE 官方流量不受影響；自測用 `curl`（見發版驗證 d） |

## 觀測

```bash
# 結構化 log（json）；單一訊息全鏈路用 chat_key / dedup_key / job_id 串
ssh oci-cp "kubectl logs -n line-connect -l app=line-connect --tail=100" | grep '<chat_key>'
# 佇列深度：housekeeping 每分鐘 log 一次 queue_depth（非零才印）
# DB 狀態
ssh oci-cp "kubectl exec -n line-connect deploy/line-connect -- python -c \"import sqlite3;c=sqlite3.connect('/data/line-connect.db');print(c.execute('select status,count(*) from inbox group by status').fetchall())\""
```

## 首次建置紀錄（僅供考古，日常操作用不到）

2026-08-08 初次部署。當時的一次性動作：namespace 預建、`apply-ghcr-secret.sh`
建 pull secret、Cloudflare 加 `line-connect` A 記錄（proxied）、
`security/public-ingress-allowlist.yaml` 登記 app-level-auth 例外（HMAC 驗簽為牆）、
deploy key `line-connect release deploy (Actions)`（k8s-apps 寫入權）配對
line-connect repo 的 Actions secret `K8S_APPS_DEPLOY_KEY`。
