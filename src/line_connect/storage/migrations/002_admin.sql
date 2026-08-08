-- Admin dashboard (Phase A). Portable SQL only: constant-default ADD COLUMN,
-- no SQLite-specific functions. created_at values come from Python's
-- utc_now_iso() so they stay lexicographically sortable with 001's defaults.

-- conversations: admin-managed chat meta + denormalized inbox-list columns
ALTER TABLE conversations ADD COLUMN custom_name TEXT;
ALTER TABLE conversations ADD COLUMN notes TEXT;
ALTER TABLE conversations ADD COLUMN starred INTEGER NOT NULL DEFAULT 0;
ALTER TABLE conversations ADD COLUMN tags TEXT NOT NULL DEFAULT '[]';  -- JSON array string
ALTER TABLE conversations ADD COLUMN picture_url TEXT;
ALTER TABLE conversations ADD COLUMN last_message_at TEXT;    -- bumped on role='user' only
ALTER TABLE conversations ADD COLUMN last_message_text TEXT;  -- first 80 chars
ALTER TABLE conversations ADD COLUMN message_count INTEGER NOT NULL DEFAULT 0;  -- lifetime, never decremented

-- list_chats is polled every 5s and orders by this
CREATE INDEX IF NOT EXISTS idx_conversations_last_msg ON conversations(last_message_at);

-- analytics aggregates scan by time range
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

-- typing indicator: derived from inbox, queried every 3s per open chat
CREATE INDEX IF NOT EXISTS idx_inbox_chat_status ON inbox(chat_key, status);

-- Admin sessions. Only the sha256 of the token is stored; DB-backed so a
-- restart does not log the operator out.
CREATE TABLE IF NOT EXISTS admin_tokens (
    token_hash  TEXT PRIMARY KEY,
    expires_at  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_tags (
    name        TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_templates (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT
);

-- Media library: file bytes live under MEDIA_DIR, this table is the index.
CREATE TABLE IF NOT EXISTS media (
    line_message_id  TEXT PRIMARY KEY,
    chat_key         TEXT NOT NULL,
    content_type     TEXT NOT NULL,
    size_bytes       INTEGER NOT NULL,
    file_path        TEXT NOT NULL,   -- relative to MEDIA_DIR
    created_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_media_created ON media(created_at);
CREATE INDEX IF NOT EXISTS idx_media_chat ON media(chat_key);

-- Backfill the denormalized columns from the message log so chats that
-- existed before this migration are visible in the dashboard immediately
-- instead of only after their next inbound message.
UPDATE conversations SET
    message_count = (
        SELECT COUNT(*) FROM messages m WHERE m.chat_key = conversations.chat_key
    ),
    last_message_at = (
        SELECT MAX(m.created_at) FROM messages m
        WHERE m.chat_key = conversations.chat_key AND m.role = 'user'
    ),
    last_message_text = (
        SELECT substr(m.text, 1, 80) FROM messages m
        WHERE m.chat_key = conversations.chat_key AND m.role = 'user'
        ORDER BY m.created_at DESC, m.id DESC LIMIT 1
    );

INSERT OR IGNORE INTO schema_migrations(version) VALUES (2);
