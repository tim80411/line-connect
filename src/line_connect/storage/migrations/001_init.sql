CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- 對話延續：一個 chat_key 對一個 Dify conversation_id
CREATE TABLE IF NOT EXISTS conversations (
    chat_key         TEXT PRIMARY KEY,        -- 'user:U…' / 'group:G…' / 'room:R…'
    source_type      TEXT NOT NULL,           -- user | group | room
    source_id        TEXT NOT NULL,
    conversation_id  TEXT,                    -- Dify cid；NULL = 尚未建立
    dify_user        TEXT,                    -- 送給 Dify 的 user 識別
    display_name     TEXT,
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- inbox：同時扮演「dedup 表」與「durable job queue」
CREATE TABLE IF NOT EXISTS inbox (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key      TEXT    NOT NULL UNIQUE,   -- webhookEventId，退化時用 'msg:<message_id>'
    chat_key       TEXT    NOT NULL,
    event_type     TEXT    NOT NULL,          -- message | follow
    message_type   TEXT,                      -- text | image | video | audio | file | …
    event_json     TEXT    NOT NULL,          -- 原始 event，重啟後可重播
    reply_token    TEXT,
    event_ts_ms    INTEGER,                   -- LINE event.timestamp，判斷 reply token 是否過期
    status         TEXT    NOT NULL DEFAULT 'pending',   -- pending|processing|done|failed|abandoned
    attempts       INTEGER NOT NULL DEFAULT 0,
    reply_sent_at  TEXT,                      -- 已送出回覆 → 重啟時不可重跑
    last_error     TEXT,
    enqueued_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    started_at     TEXT,
    finished_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_inbox_status      ON inbox(status, id);
CREATE INDEX IF NOT EXISTS idx_inbox_enqueued_at ON inbox(enqueued_at);

-- 訊息紀錄（本期不做瀏覽 UI，但寫入，schema 先定好）
CREATE TABLE IF NOT EXISTS messages (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_key         TEXT NOT NULL,
    role             TEXT NOT NULL,           -- user | bot
    msg_type         TEXT NOT NULL DEFAULT 'text',
    text             TEXT,
    line_message_id  TEXT,
    conversation_id  TEXT,
    display_name     TEXT,
    latency_ms       INTEGER,                 -- bot 列才有：Dify 回應耗時
    created_at       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_chat_created ON messages(chat_key, created_at);

INSERT OR IGNORE INTO schema_migrations(version) VALUES (1);
