"""Data access for conversations / inbox / messages.

All methods are synchronous on purpose: unit tests call them directly with no
event loop, and async callers wrap them in asyncio.to_thread. Serialization is
handled by Database.locked().
"""

from dataclasses import dataclass

import structlog

from line_connect.storage.db import Database, utc_cutoff_iso, utc_now_iso

log = structlog.get_logger(__name__)

MAX_STORED_ERROR_LEN = 2000
LAST_MESSAGE_PREVIEW_LEN = 80


@dataclass(frozen=True)
class InboxJob:
    id: int
    dedup_key: str
    chat_key: str
    event_type: str
    message_type: str | None
    event_json: str
    reply_token: str | None
    event_ts_ms: int | None
    attempts: int
    reply_sent_at: str | None


class Repository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ── conversations ──────────────────────────────────────────────

    def ensure_conversation(
        self,
        chat_key: str,
        source_type: str,
        source_id: str,
        dify_user: str,
        display_name: str | None = None,
        picture_url: str | None = None,
    ) -> None:
        now = utc_now_iso()
        with self._db.locked() as conn:
            conn.execute(
                """
                INSERT INTO conversations(chat_key, source_type, source_id, dify_user,
                                          display_name, picture_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_key) DO UPDATE SET
                    dify_user = excluded.dify_user,
                    display_name = COALESCE(excluded.display_name, display_name),
                    picture_url = COALESCE(excluded.picture_url, picture_url),
                    updated_at = excluded.updated_at
                """,
                (
                    chat_key,
                    source_type,
                    source_id,
                    dify_user,
                    display_name,
                    picture_url,
                    now,
                    now,
                ),
            )

    def get_custom_name(self, chat_key: str) -> str | None:
        """Admin-assigned display name override. Primary-key lookup on the hot
        path — read via the read-only connection so it never waits on a write."""
        with self._db.locked_ro() as conn:
            row = conn.execute(
                "SELECT custom_name FROM conversations WHERE chat_key = ?", (chat_key,)
            ).fetchone()
        return row["custom_name"] if row else None

    def get_cid(self, chat_key: str) -> str | None:
        with self._db.locked() as conn:
            row = conn.execute(
                "SELECT conversation_id FROM conversations WHERE chat_key = ?", (chat_key,)
            ).fetchone()
        return row["conversation_id"] if row else None

    def set_cid(self, chat_key: str, cid: str) -> None:
        with self._db.locked() as conn:
            conn.execute(
                "UPDATE conversations SET conversation_id = ?, updated_at = ? WHERE chat_key = ?",
                (cid, utc_now_iso(), chat_key),
            )

    def clear_cid(self, chat_key: str) -> None:
        with self._db.locked() as conn:
            conn.execute(
                "UPDATE conversations SET conversation_id = NULL, updated_at = ?"
                " WHERE chat_key = ?",
                (utc_now_iso(), chat_key),
            )

    # NOTE: there is deliberately no delete_conversation(). The /clear command
    # calls clear_cid() instead — dropping the row would also drop the admin
    # meta (custom_name / notes / tags / starred) an operator set on that chat.

    # ── inbox: dedup + durable job queue ───────────────────────────

    def try_claim_event(
        self,
        dedup_key: str,
        chat_key: str,
        event_type: str,
        message_type: str | None,
        event_json: str,
        reply_token: str | None,
        event_ts_ms: int | None,
    ) -> int | None:
        """Insert the event; return its row id, or None if dedup_key already seen.

        The UNIQUE constraint *is* the dedup mechanism — no read-modify-write
        race is possible (upstream defect #4).
        """
        with self._db.locked() as conn:
            cur = conn.execute(
                """
                INSERT INTO inbox(dedup_key, chat_key, event_type, message_type,
                                  event_json, reply_token, event_ts_ms, enqueued_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(dedup_key) DO NOTHING
                """,
                (
                    dedup_key,
                    chat_key,
                    event_type,
                    message_type,
                    event_json,
                    reply_token,
                    event_ts_ms,
                    utc_now_iso(),
                ),
            )
            if cur.rowcount == 0:
                return None
            return int(cur.lastrowid)  # type: ignore[arg-type]

    def get_job(self, row_id: int) -> InboxJob | None:
        with self._db.locked() as conn:
            row = conn.execute("SELECT * FROM inbox WHERE id = ?", (row_id,)).fetchone()
        if row is None:
            return None
        return InboxJob(
            id=row["id"],
            dedup_key=row["dedup_key"],
            chat_key=row["chat_key"],
            event_type=row["event_type"],
            message_type=row["message_type"],
            event_json=row["event_json"],
            reply_token=row["reply_token"],
            event_ts_ms=row["event_ts_ms"],
            attempts=row["attempts"],
            reply_sent_at=row["reply_sent_at"],
        )

    def mark_processing(self, row_id: int) -> None:
        with self._db.locked() as conn:
            conn.execute(
                "UPDATE inbox SET status = 'processing', attempts = attempts + 1,"
                " started_at = ? WHERE id = ?",
                (utc_now_iso(), row_id),
            )

    def mark_done(self, row_id: int) -> None:
        with self._db.locked() as conn:
            conn.execute(
                "UPDATE inbox SET status = 'done', finished_at = ? WHERE id = ?",
                (utc_now_iso(), row_id),
            )

    def mark_failed(self, row_id: int, error: str) -> None:
        with self._db.locked() as conn:
            conn.execute(
                "UPDATE inbox SET status = 'failed', finished_at = ?, last_error = ?"
                " WHERE id = ?",
                (utc_now_iso(), error[:MAX_STORED_ERROR_LEN], row_id),
            )

    def mark_reply_sent(self, row_id: int) -> None:
        with self._db.locked() as conn:
            conn.execute(
                "UPDATE inbox SET reply_sent_at = ? WHERE id = ?", (utc_now_iso(), row_id)
            )

    def recover_orphans(
        self, max_age_seconds: float, max_attempts: int = 2
    ) -> list[InboxJob]:
        """Startup recovery of jobs left 'pending'/'processing' by a crash or drain.

        - reply already sent      → mark done (re-running would double-reply)
        - too many attempts / too old → mark abandoned (answering a ten-minute-old
          question now only confuses the user)
        - otherwise               → reset to pending and return for re-enqueue
        """
        cutoff = utc_cutoff_iso(max_age_seconds)
        recovered: list[InboxJob] = []
        with self._db.locked() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                rows = conn.execute(
                    "SELECT * FROM inbox WHERE status IN ('pending', 'processing')"
                    " ORDER BY id"
                ).fetchall()
                for row in rows:
                    if row["reply_sent_at"] is not None:
                        conn.execute(
                            "UPDATE inbox SET status = 'done', finished_at = ? WHERE id = ?",
                            (utc_now_iso(), row["id"]),
                        )
                    elif row["attempts"] >= max_attempts or row["enqueued_at"] < cutoff:
                        conn.execute(
                            "UPDATE inbox SET status = 'abandoned', finished_at = ?"
                            " WHERE id = ?",
                            (utc_now_iso(), row["id"]),
                        )
                    else:
                        conn.execute(
                            "UPDATE inbox SET status = 'pending' WHERE id = ?", (row["id"],)
                        )
                        recovered.append(
                            InboxJob(
                                id=row["id"],
                                dedup_key=row["dedup_key"],
                                chat_key=row["chat_key"],
                                event_type=row["event_type"],
                                message_type=row["message_type"],
                                event_json=row["event_json"],
                                reply_token=row["reply_token"],
                                event_ts_ms=row["event_ts_ms"],
                                attempts=row["attempts"],
                                reply_sent_at=row["reply_sent_at"],
                            )
                        )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        if recovered:
            log.info("orphans_recovered", count=len(recovered))
        return recovered

    def list_pending(self) -> list[tuple[int, str]]:
        """(id, chat_key) of rows waiting for a worker, oldest first."""
        with self._db.locked() as conn:
            rows = conn.execute(
                "SELECT id, chat_key FROM inbox WHERE status = 'pending' ORDER BY id"
            ).fetchall()
        return [(row["id"], row["chat_key"]) for row in rows]

    def count_by_status(self) -> dict[str, int]:
        with self._db.locked() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM inbox GROUP BY status"
            ).fetchall()
        return {row["status"]: row["n"] for row in rows}

    def purge_expired(
        self, dedup_retention_days: int, message_retention_days: int
    ) -> tuple[int, int]:
        """Delete finished inbox rows and old message logs. Returns (inbox, messages) counts."""
        inbox_cutoff = utc_cutoff_iso(dedup_retention_days * 86400)
        msg_cutoff = utc_cutoff_iso(message_retention_days * 86400)
        with self._db.locked() as conn:
            cur1 = conn.execute(
                "DELETE FROM inbox WHERE status IN ('done', 'failed', 'abandoned')"
                " AND enqueued_at < ?",
                (inbox_cutoff,),
            )
            cur2 = conn.execute(
                "DELETE FROM messages WHERE created_at < ?", (msg_cutoff,)
            )
        return cur1.rowcount, cur2.rowcount

    # ── messages ───────────────────────────────────────────────────

    def log_message(
        self,
        chat_key: str,
        role: str,
        text: str | None,
        msg_type: str = "text",
        line_message_id: str | None = None,
        conversation_id: str | None = None,
        display_name: str | None = None,
        latency_ms: int | None = None,
    ) -> None:
        now = utc_now_iso()
        with self._db.locked() as conn:
            conn.execute(
                """
                INSERT INTO messages(chat_key, role, msg_type, text, line_message_id,
                                     conversation_id, display_name, latency_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    chat_key,
                    role,
                    msg_type,
                    text,
                    line_message_id,
                    conversation_id,
                    display_name,
                    latency_ms,
                    now,
                ),
            )
            # Denormalize into conversations so the 5s-polled inbox list is a
            # single index scan instead of a per-chat correlated subquery over
            # messages. Same lock, same transaction-less autocommit step.
            if role == "user":
                # Only user messages bump last_message_*: the dashboard compares
                # it against a per-chat "last read" marker, and a bot reply
                # bumping it would make every answered chat look unread again.
                conn.execute(
                    "UPDATE conversations SET message_count = message_count + 1,"
                    " last_message_at = ?, last_message_text = ? WHERE chat_key = ?",
                    (now, (text or "")[:LAST_MESSAGE_PREVIEW_LEN], chat_key),
                )
            else:
                conn.execute(
                    "UPDATE conversations SET message_count = message_count + 1"
                    " WHERE chat_key = ?",
                    (chat_key,),
                )
