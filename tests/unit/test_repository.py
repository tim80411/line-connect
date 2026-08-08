"""Repository tests against a real SQLite file (plan §7.4)."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from line_connect.storage.db import Database, utc_cutoff_iso
from line_connect.storage.repository import Repository


def claim(repo: Repository, key: str = "evt-1", chat: str = "user:U1") -> int | None:
    return repo.try_claim_event(
        dedup_key=key,
        chat_key=chat,
        event_type="message",
        message_type="text",
        event_json="{}",
        reply_token="rt-1",
        event_ts_ms=1_700_000_000_000,
    )


class TestDatabase:
    def test_wal_mode_active(self, db: Database) -> None:
        assert db.journal_mode() == "wal"

    def test_migrations_idempotent(self, tmp_path: Path) -> None:
        path = str(tmp_path / "m.db")
        first = Database(path)
        first.connect()
        first.close()
        second = Database(path)
        second.connect()
        with second.locked() as conn:
            versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations")]
        second.close()
        assert versions == [1, 2]


class TestDedup:
    def test_same_key_inserted_once(self, repo: Repository) -> None:
        assert claim(repo) is not None
        assert claim(repo) is None

    def test_concurrent_claims_single_winner(self, repo: Repository) -> None:
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(lambda _: claim(repo, key="race"), range(16)))
        winners = [r for r in results if r is not None]
        assert len(winners) == 1

    def test_distinct_keys_both_insert(self, repo: Repository) -> None:
        assert claim(repo, key="a") is not None
        assert claim(repo, key="b") is not None


class TestConversation:
    def test_cid_roundtrip(self, repo: Repository) -> None:
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", "Tim")
        assert repo.get_cid("user:U1") is None
        repo.set_cid("user:U1", "cid-123")
        assert repo.get_cid("user:U1") == "cid-123"
        repo.clear_cid("user:U1")
        assert repo.get_cid("user:U1") is None

    def test_clear_cid_keeps_admin_meta(self, repo: Repository) -> None:
        """/clear drops the Dify conversation, never the admin's annotations."""
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", "Tim")
        repo.set_cid("user:U1", "cid-123")
        with repo._db.locked() as conn:
            conn.execute(
                "UPDATE conversations SET custom_name = 'VIP', notes = 'call back',"
                " tags = '[\"vip\"]', starred = 1 WHERE chat_key = 'user:U1'"
            )
        repo.clear_cid("user:U1")
        assert repo.get_cid("user:U1") is None
        with repo._db.locked() as conn:
            row = conn.execute(
                "SELECT custom_name, notes, tags, starred FROM conversations"
                " WHERE chat_key = 'user:U1'"
            ).fetchone()
        assert (row["custom_name"], row["notes"], row["tags"], row["starred"]) == (
            "VIP", "call back", '["vip"]', 1,
        )

    def test_get_custom_name(self, repo: Repository) -> None:
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", "Tim")
        assert repo.get_custom_name("user:U1") is None
        assert repo.get_custom_name("user:missing") is None
        with repo._db.locked() as conn:
            conn.execute("UPDATE conversations SET custom_name = 'VIP'")
        assert repo.get_custom_name("user:U1") == "VIP"

    def test_upsert_preserves_picture_url_when_null(self, repo: Repository) -> None:
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", "Tim", "http://p/1")
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", "Tim", None)
        with repo._db.locked() as conn:
            row = conn.execute(
                "SELECT picture_url FROM conversations WHERE chat_key = 'user:U1'"
            ).fetchone()
        assert row["picture_url"] == "http://p/1"

    def test_upsert_preserves_display_name_when_null(self, repo: Repository) -> None:
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", "Tim")
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", None)
        with repo._db.locked() as conn:
            row = conn.execute(
                "SELECT display_name FROM conversations WHERE chat_key = 'user:U1'"
            ).fetchone()
        assert row["display_name"] == "Tim"

    def test_get_cid_unknown_chat(self, repo: Repository) -> None:
        assert repo.get_cid("user:unknown") is None


class TestJobLifecycle:
    def test_processing_increments_attempts(self, repo: Repository) -> None:
        row_id = claim(repo)
        assert row_id is not None
        repo.mark_processing(row_id)
        job = repo.get_job(row_id)
        assert job is not None and job.attempts == 1
        repo.mark_done(row_id)
        assert repo.count_by_status() == {"done": 1}

    def test_mark_failed_stores_error(self, repo: Repository) -> None:
        row_id = claim(repo)
        assert row_id is not None
        repo.mark_failed(row_id, "boom" * 1000)
        with repo._db.locked() as conn:
            row = conn.execute("SELECT * FROM inbox WHERE id = ?", (row_id,)).fetchone()
        assert row["status"] == "failed"
        assert len(row["last_error"]) <= 2000


class TestOrphanRecovery:
    def _seed(
        self,
        repo: Repository,
        key: str,
        status: str,
        attempts: int = 0,
        reply_sent: bool = False,
        age_seconds: float = 0,
    ) -> int:
        row_id = claim(repo, key=key, chat=f"user:{key}")
        assert row_id is not None
        with repo._db.locked() as conn:
            conn.execute(
                "UPDATE inbox SET status = ?, attempts = ? WHERE id = ?",
                (status, attempts, row_id),
            )
            if reply_sent:
                conn.execute(
                    "UPDATE inbox SET reply_sent_at = enqueued_at WHERE id = ?", (row_id,)
                )
            if age_seconds:
                conn.execute(
                    "UPDATE inbox SET enqueued_at = ? WHERE id = ?",
                    (utc_cutoff_iso(age_seconds), row_id),
                )
        return row_id

    def test_three_branches(self, repo: Repository) -> None:
        replied = self._seed(repo, "replied", "processing", attempts=1, reply_sent=True)
        exhausted = self._seed(repo, "exhausted", "pending", attempts=2)
        stale = self._seed(repo, "stale", "processing", attempts=1, age_seconds=999)
        fresh = self._seed(repo, "fresh", "processing", attempts=1)

        recovered = repo.recover_orphans(max_age_seconds=120, max_attempts=2)

        assert [j.id for j in recovered] == [fresh]
        statuses = {
            row_id: self._status(repo, row_id)
            for row_id in (replied, exhausted, stale, fresh)
        }
        assert statuses[replied] == "done"
        assert statuses[exhausted] == "abandoned"
        assert statuses[stale] == "abandoned"
        assert statuses[fresh] == "pending"

    def test_done_rows_untouched(self, repo: Repository) -> None:
        row_id = claim(repo)
        assert row_id is not None
        repo.mark_done(row_id)
        assert repo.recover_orphans(max_age_seconds=120) == []
        assert self._status(repo, row_id) == "done"

    @staticmethod
    def _status(repo: Repository, row_id: int) -> str:
        with repo._db.locked() as conn:
            row = conn.execute("SELECT status FROM inbox WHERE id = ?", (row_id,)).fetchone()
        return str(row["status"])


class TestRetention:
    def test_purge_only_expired_finished_rows(self, repo: Repository) -> None:
        old_done = claim(repo, key="old-done")
        fresh_done = claim(repo, key="fresh-done")
        old_pending = claim(repo, key="old-pending")
        assert old_done and fresh_done and old_pending
        repo.mark_done(old_done)
        repo.mark_done(fresh_done)
        old_ts = utc_cutoff_iso(10 * 86400)
        with repo._db.locked() as conn:
            conn.execute(
                "UPDATE inbox SET enqueued_at = ? WHERE id IN (?, ?)",
                (old_ts, old_done, old_pending),
            )

        repo.log_message("user:U1", "user", "old msg")
        repo.log_message("user:U1", "user", "fresh msg")
        with repo._db.locked() as conn:
            conn.execute(
                "UPDATE messages SET created_at = ? WHERE text = 'old msg'", (old_ts,)
            )

        purged_inbox, purged_msgs = repo.purge_expired(
            dedup_retention_days=3, message_retention_days=3
        )

        assert purged_inbox == 1  # old_done only; old_pending is not finished
        assert purged_msgs == 1
        remaining = repo.count_by_status()
        assert remaining == {"done": 1, "pending": 1}


class TestDenormalization:
    """log_message keeps conversations' inbox-list columns current (§3)."""

    def _row(self, repo: Repository) -> Any:
        with repo._db.locked() as conn:
            return conn.execute(
                "SELECT last_message_at, last_message_text, message_count"
                " FROM conversations WHERE chat_key = 'user:U1'"
            ).fetchone()

    def test_user_message_bumps_last_message(self, repo: Repository) -> None:
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", "Tim")
        repo.log_message("user:U1", "user", "hello there")
        row = self._row(repo)
        assert row["last_message_text"] == "hello there"
        assert row["message_count"] == 1
        with repo._db.locked() as conn:
            msg_ts = conn.execute("SELECT created_at FROM messages").fetchone()[0]
        assert row["last_message_at"] == msg_ts

    def test_bot_message_counts_but_does_not_bump(self, repo: Repository) -> None:
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", "Tim")
        repo.log_message("user:U1", "user", "question")
        before = self._row(repo)["last_message_at"]
        repo.log_message("user:U1", "bot", "answer", latency_ms=1200)
        row = self._row(repo)
        assert row["message_count"] == 2
        assert row["last_message_at"] == before
        assert row["last_message_text"] == "question"

    def test_preview_truncated_to_80_chars(self, repo: Repository) -> None:
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", None)
        repo.log_message("user:U1", "user", "x" * 200)
        assert self._row(repo)["last_message_text"] == "x" * 80

    def test_media_message_previews_its_type(self, repo: Repository) -> None:
        repo.ensure_conversation("user:U1", "user", "U1", "line-U1", None)
        repo.log_message("user:U1", "user", "[image]", msg_type="image")
        assert self._row(repo)["last_message_text"] == "[image]"

    def test_orphan_chat_key_does_not_raise(self, repo: Repository) -> None:
        repo.log_message("user:nobody", "user", "hi")  # no conversations row
        with repo._db.locked() as conn:
            assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 1


class TestReadOnlyConnection:
    def test_reads_see_committed_writes(self, tmp_path: Path) -> None:
        db = Database(str(tmp_path / "ro.db"))
        db.connect()
        db.connect_read()
        try:
            Repository(db).ensure_conversation("user:U1", "user", "U1", "u", "Tim")
            with db.locked_ro() as conn:
                row = conn.execute(
                    "SELECT display_name FROM conversations WHERE chat_key = 'user:U1'"
                ).fetchone()
            assert row["display_name"] == "Tim"
        finally:
            db.close()

    def test_writes_are_rejected(self, tmp_path: Path) -> None:
        db = Database(str(tmp_path / "ro.db"))
        db.connect()
        db.connect_read()
        try:
            with (
                pytest.raises(sqlite3.OperationalError, match="readonly"),
                db.locked_ro() as conn,
            ):
                conn.execute("DELETE FROM conversations")
        finally:
            db.close()

    def test_falls_back_to_write_connection(self, db: Database) -> None:
        """connect_read() is an optimization, not a precondition."""
        with db.locked_ro() as conn:
            assert conn.execute("SELECT 1").fetchone()[0] == 1
