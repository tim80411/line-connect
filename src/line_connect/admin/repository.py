"""Data access for the dashboard.

Split from storage.repository on purpose: every read here goes through the
read-only connection (`locked_ro`), so a dashboard poll or an analytics scan
never queues behind — or ahead of — a webhook's write. Writes are all
point-updates on a chat the operator is looking at, so they take the write lock
for microseconds.

Methods are synchronous like the rest of the storage layer; async callers wrap
them in asyncio.to_thread.
"""

import json
import sqlite3
import uuid
from typing import Any

import structlog

from line_connect.storage.db import Database, utc_now_iso

log = structlog.get_logger(__name__)

#: An inbox row older than this is not evidence of an in-flight reply — it is a
#: crashed job that startup recovery has not swept yet.
TYPING_MAX_AGE_SECONDS = 120.0

CHAT_COLUMNS = (
    "chat_key, source_type, source_id, display_name, custom_name, picture_url,"
    " starred, tags, last_message_at, last_message_text, message_count"
)


def _tags_of(raw: str | None) -> list[str]:
    """conversations.tags is a JSON array string. Never let a malformed value
    take down the whole chat list."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return [str(t) for t in parsed] if isinstance(parsed, list) else []


def chat_row_to_json(row: sqlite3.Row) -> dict[str, Any]:
    """Map a conversations row onto the field names app.js expects."""
    original = row["display_name"] or row["chat_key"]
    custom = row["custom_name"] or ""
    entry: dict[str, Any] = {
        "id": row["chat_key"],
        "name": custom or original,
        "original_name": original,
        "custom_name": custom,
        "type": row["source_type"],
        "source_id": row["source_id"],
        "last_active": row["last_message_at"] or "",
        "last_message": row["last_message_text"] or "",
        # Phase B (per-chat bot switch) is not ported; the UI reads this field.
        "disabled": False,
        "mc": row["message_count"],
        "starred": bool(row["starred"]),
        "tags": _tags_of(row["tags"]),
    }
    if row["picture_url"]:
        entry["pic"] = row["picture_url"]
    return entry


def message_row_to_json(row: sqlite3.Row) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "r": row["role"],
        "t": row["text"] or "",
        "ts": row["created_at"],
    }
    if row["display_name"]:
        entry["n"] = row["display_name"]
    # `tp` marks *inbound* media only. A bot reply to an image is logged with
    # msg_type='image' too (it is the answer about that image), and tagging it
    # would make the UI render "Sent an image" in place of the actual answer:
    # msgHtml treats any tp=='image' row as a picture (app.js:1832). Upstream
    # only ever set this field on user entries (storage.py:414-418).
    if row["role"] == "user" and row["msg_type"] and row["msg_type"] != "text":
        entry["tp"] = row["msg_type"]
    if row["line_message_id"]:
        entry["mid"] = row["line_message_id"]
    return entry


class AdminRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def db(self) -> Database:
        """Exposed so sibling read-model classes (analytics, media) can share
        the same connection pair instead of opening their own."""
        return self._db

    # ── session tokens ─────────────────────────────────────────────

    def create_token(
        self, token_hash: str, expires_at: str, created_at: str, keep: int
    ) -> None:
        with self._db.locked() as conn:
            conn.execute("DELETE FROM admin_tokens WHERE expires_at <= ?", (created_at,))
            conn.execute(
                "INSERT OR REPLACE INTO admin_tokens(token_hash, expires_at, created_at)"
                " VALUES (?, ?, ?)",
                (token_hash, expires_at, created_at),
            )
            conn.execute(
                "DELETE FROM admin_tokens WHERE token_hash NOT IN"
                " (SELECT token_hash FROM admin_tokens"
                "  ORDER BY created_at DESC, rowid DESC LIMIT ?)",
                (keep,),
            )

    def token_is_valid(self, token_hash: str, now: str) -> bool:
        with self._db.locked_ro() as conn:
            row = conn.execute(
                "SELECT 1 FROM admin_tokens WHERE token_hash = ? AND expires_at > ?",
                (token_hash, now),
            ).fetchone()
        return row is not None

    def revoke_token(self, token_hash: str) -> None:
        with self._db.locked() as conn:
            conn.execute("DELETE FROM admin_tokens WHERE token_hash = ?", (token_hash,))

    # ── chats ──────────────────────────────────────────────────────

    def list_chats(self) -> list[dict[str, Any]]:
        """Chats that have ever received a user message, newest first.

        The NULL filter is what makes clear_all_chats work: it blanks
        last_message_at so a chat leaves the list, while the row (and with it
        the Dify conversation id) survives.
        """
        with self._db.locked_ro() as conn:
            rows = conn.execute(
                f"SELECT {CHAT_COLUMNS} FROM conversations"  # noqa: S608 - fixed column list
                " WHERE last_message_at IS NOT NULL"
                " ORDER BY last_message_at DESC"
            ).fetchall()
        return [chat_row_to_json(r) for r in rows]

    def get_conversation(self, chat_key: str) -> sqlite3.Row | None:
        with self._db.locked_ro() as conn:
            row: sqlite3.Row | None = conn.execute(
                "SELECT chat_key, source_type, source_id, display_name, custom_name"
                " FROM conversations WHERE chat_key = ?",
                (chat_key,),
            ).fetchone()
        return row

    def get_history(self, chat_key: str, limit: int) -> list[dict[str, Any]]:
        with self._db.locked_ro() as conn:
            rows = conn.execute(
                "SELECT role, msg_type, text, line_message_id, display_name, created_at"
                " FROM messages WHERE chat_key = ? ORDER BY id DESC LIMIT ?",
                (chat_key, limit),
            ).fetchall()
        return [message_row_to_json(r) for r in reversed(rows)]

    def is_typing(self, chat_key: str, cutoff: str) -> bool:
        """Derived, never written: an unfinished inbox row *is* the bot thinking.

        Upstream maintained this with 15 explicit set/clear calls scattered
        through the request path, each one a chance to leak a stuck indicator.
        """
        with self._db.locked_ro() as conn:
            row = conn.execute(
                "SELECT 1 FROM inbox WHERE chat_key = ?"
                " AND status IN ('pending', 'processing') AND enqueued_at >= ? LIMIT 1",
                (chat_key, cutoff),
            ).fetchone()
        return row is not None

    def get_chat_meta(self, chat_key: str) -> dict[str, Any]:
        with self._db.locked_ro() as conn:
            row = conn.execute(
                "SELECT custom_name, notes, starred, tags FROM conversations"
                " WHERE chat_key = ?",
                (chat_key,),
            ).fetchone()
        if row is None:
            return {}
        return {
            "custom_name": row["custom_name"] or "",
            "notes": row["notes"] or "",
            "starred": bool(row["starred"]),
            "tags": _tags_of(row["tags"]),
        }

    def update_chat_meta(self, chat_key: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Update only the keys present in `fields`; returns the new meta."""
        assignments: list[str] = []
        values: list[Any] = []
        if "custom_name" in fields:
            assignments.append("custom_name = ?")
            values.append(str(fields["custom_name"] or "") or None)
        if "notes" in fields:
            assignments.append("notes = ?")
            values.append(str(fields["notes"] or "") or None)
        if "starred" in fields:
            assignments.append("starred = ?")
            values.append(1 if fields["starred"] else 0)
        if "tags" in fields:
            raw = fields["tags"]
            tags = [str(t) for t in raw] if isinstance(raw, list) else []
            assignments.append("tags = ?")
            values.append(json.dumps(tags, ensure_ascii=False))
        if assignments:
            assignments.append("updated_at = ?")
            values.append(utc_now_iso())
            values.append(chat_key)
            with self._db.locked() as conn:
                conn.execute(
                    # assignments are code-literal fragments; every value is bound
                    f"UPDATE conversations SET {', '.join(assignments)} WHERE chat_key = ?",  # noqa: S608
                    values,
                )
        return self.get_chat_meta(chat_key)

    def log_admin_message(self, chat_key: str, text: str) -> None:
        """Record an operator's outbound message in the same log as the bot's.

        Deliberately does not touch last_message_at: that column drives the
        dashboard's unread marker, and a chat the operator just answered is by
        definition read.
        """
        with self._db.locked() as conn:
            conn.execute(
                "INSERT INTO messages(chat_key, role, msg_type, text, display_name,"
                " created_at) VALUES (?, 'admin', 'text', ?, 'Admin', ?)",
                (chat_key, text, utc_now_iso()),
            )
            conn.execute(
                "UPDATE conversations SET message_count = message_count + 1"
                " WHERE chat_key = ?",
                (chat_key,),
            )

    # ── destructive ────────────────────────────────────────────────

    def clear_history(self, chat_key: str) -> list[str]:
        """Delete one chat's messages and media index rows.

        The conversations row stays: dropping it would take the Dify
        conversation id and the operator's own annotations with it. Returns the
        media file paths the caller should unlink.
        """
        with self._db.locked() as conn:
            paths = [
                r["file_path"]
                for r in conn.execute(
                    "SELECT file_path FROM media WHERE chat_key = ?", (chat_key,)
                )
            ]
            conn.execute("DELETE FROM messages WHERE chat_key = ?", (chat_key,))
            conn.execute("DELETE FROM media WHERE chat_key = ?", (chat_key,))
            conn.execute(
                "UPDATE conversations SET last_message_at = NULL,"
                " last_message_text = NULL WHERE chat_key = ?",
                (chat_key,),
            )
        return paths

    def clear_all_chats(self) -> tuple[int, list[str]]:
        """Wipe every message log. Returns (chats affected, media paths)."""
        with self._db.locked() as conn:
            paths = [r["file_path"] for r in conn.execute("SELECT file_path FROM media")]
            cur = conn.execute(
                "UPDATE conversations SET last_message_at = NULL, last_message_text = NULL"
                " WHERE last_message_at IS NOT NULL"
            )
            count = cur.rowcount
            conn.execute("DELETE FROM messages")
            conn.execute("DELETE FROM media")
        return count, paths

    # ── export ─────────────────────────────────────────────────────

    def export_history(self, chat_key: str, max_rows: int) -> list[dict[str, Any]]:
        """Oldest-first, capped by ADMIN_EXPORT_MAX_ROWS.

        Unlike upstream — whose "export" serialized whatever the browser had
        already loaded, at most 100 messages — this reads the whole log.
        """
        with self._db.locked_ro() as conn:
            rows = conn.execute(
                "SELECT role, msg_type, text, line_message_id, display_name, created_at"
                " FROM messages WHERE chat_key = ? ORDER BY id LIMIT ?",
                (chat_key, max_rows),
            ).fetchall()
        return [message_row_to_json(r) for r in rows]

    # ── tags ───────────────────────────────────────────────────────

    def list_tags(self) -> list[str]:
        with self._db.locked_ro() as conn:
            rows = conn.execute(
                "SELECT name FROM admin_tags ORDER BY created_at, name"
            ).fetchall()
        return [r["name"] for r in rows]

    def add_tag(self, name: str) -> None:
        with self._db.locked() as conn:
            # INSERT OR IGNORE rather than an upsert: "already exists" is a
            # success for this action, and this stays portable SQL.
            conn.execute(
                "INSERT OR IGNORE INTO admin_tags(name, created_at) VALUES (?, ?)",
                (name, utc_now_iso()),
            )

    def remove_tag(self, name: str) -> None:
        with self._db.locked() as conn:
            conn.execute("DELETE FROM admin_tags WHERE name = ?", (name,))
        self._rewrite_chat_tags({name: None})

    def rename_tag(self, old: str, new: str) -> None:
        with self._db.locked() as conn:
            conn.execute(
                "UPDATE admin_tags SET name = ? WHERE name = ?", (new, old)
            )
        self._rewrite_chat_tags({old: new})

    def _rewrite_chat_tags(self, mapping: dict[str, str | None]) -> None:
        """Apply a rename (value) or removal (None) across conversations.tags.

        JSON surgery happens in Python, not SQL: SQLite's json1 functions have
        no portable equivalent, and the candidate set is tiny.
        """
        like_terms = [f'%"{old}"%' for old in mapping]
        clause = " OR ".join(["tags LIKE ?"] * len(like_terms))
        with self._db.locked() as conn:
            rows = conn.execute(
                f"SELECT chat_key, tags FROM conversations WHERE {clause}",  # noqa: S608
                like_terms,
            ).fetchall()
            for row in rows:
                current = _tags_of(row["tags"])
                updated: list[str] = []
                for tag in current:
                    replacement = mapping.get(tag, tag)
                    if replacement is not None and replacement not in updated:
                        updated.append(replacement)
                if updated != current:
                    conn.execute(
                        "UPDATE conversations SET tags = ? WHERE chat_key = ?",
                        (json.dumps(updated, ensure_ascii=False), row["chat_key"]),
                    )

    # ── templates ──────────────────────────────────────────────────

    def list_templates(self) -> list[dict[str, Any]]:
        with self._db.locked_ro() as conn:
            rows = conn.execute(
                "SELECT id, title, body, created_at, updated_at FROM admin_templates"
                " ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def add_template(self, title: str, body: str) -> dict[str, Any]:
        template = {
            "id": uuid.uuid4().hex[:8],  # upstream id shape, kept for the UI
            "title": title,
            "body": body,
            "created_at": utc_now_iso(),
            "updated_at": None,
        }
        with self._db.locked() as conn:
            conn.execute(
                "INSERT INTO admin_templates(id, title, body, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    template["id"],
                    template["title"],
                    template["body"],
                    template["created_at"],
                    None,
                ),
            )
        return template

    def update_template(self, template_id: str, title: str, body: str) -> bool:
        with self._db.locked() as conn:
            cur = conn.execute(
                "UPDATE admin_templates SET title = ?, body = ?, updated_at = ?"
                " WHERE id = ?",
                (title, body, utc_now_iso(), template_id),
            )
        return cur.rowcount > 0

    def delete_template(self, template_id: str) -> bool:
        with self._db.locked() as conn:
            cur = conn.execute(
                "DELETE FROM admin_templates WHERE id = ?", (template_id,)
            )
        return cur.rowcount > 0
