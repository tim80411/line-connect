"""On-disk media library for the dashboard.

Bytes live under MEDIA_DIR (the same PVC as the SQLite file, so k8s needs no
new volume); the `media` table is the index. Eviction is bounded by *both* a
file count and a total size — a count alone lets 500 videos fill the disk, a
size alone lets thousands of thumbnails bloat the table.

Off by default (MEDIA_STORE_ENABLED): storing user-sent images is a data
retention decision, not a default.
"""

import asyncio
import re
import sqlite3
from pathlib import Path

import structlog

from line_connect.config import Settings
from line_connect.storage.db import Database, utc_now_iso

log = structlog.get_logger(__name__)

EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
}
DEFAULT_EXTENSION = ".bin"
_SAFE_ID = re.compile(r"[^A-Za-z0-9_-]")


def safe_name(message_id: str, content_type: str) -> str:
    """Filename from a LINE message id. The id is server-generated and numeric
    in practice, but it reaches us from the network, so it is sanitized before
    it ever becomes a path segment."""
    stem = _SAFE_ID.sub("", message_id)[:64] or "unknown"
    base = content_type.split(";")[0].strip().lower()
    return stem + EXTENSIONS.get(base, DEFAULT_EXTENSION)


class MediaStore:
    def __init__(self, settings: Settings, db: Database) -> None:
        self._settings = settings
        self._db = db
        self.root = Path(settings.media_dir).resolve()

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    # ── write path (called from the pipeline) ──────────────────────

    async def save(
        self, chat_key: str, message_id: str, data: bytes, content_type: str
    ) -> None:
        """Best-effort: a failure here must never cost the user their reply."""
        try:
            await asyncio.to_thread(self._save, chat_key, message_id, data, content_type)
        except Exception as exc:
            log.warning("media_store_failed", chat_key=chat_key, error=str(exc)[:200])

    def _save(
        self, chat_key: str, message_id: str, data: bytes, content_type: str
    ) -> None:
        self.ensure_root()
        name = safe_name(message_id, content_type)
        (self.root / name).write_bytes(data)
        with self._db.locked() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO media(line_message_id, chat_key, content_type,"
                " size_bytes, file_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (message_id, chat_key, content_type, len(data), name, utc_now_iso()),
            )
            evicted = self._evict(conn)
        for path in evicted:
            self.unlink(path)
        if evicted:
            log.info("media_evicted", count=len(evicted))

    def _evict(self, conn: sqlite3.Connection) -> list[str]:
        """Drop the oldest rows until both caps hold. Returns their paths."""
        rows = conn.execute(
            "SELECT line_message_id, file_path, size_bytes FROM media"
            " ORDER BY created_at DESC, rowid DESC"
        ).fetchall()
        max_count = self._settings.media_store_max_count
        max_bytes = self._settings.media_store_max_bytes
        kept = 0
        total = 0
        doomed: list[sqlite3.Row] = []
        for row in rows:
            if doomed or kept + 1 > max_count or total + row["size_bytes"] > max_bytes:
                doomed.append(row)
                continue
            kept += 1
            total += row["size_bytes"]
        for row in doomed:
            conn.execute(
                "DELETE FROM media WHERE line_message_id = ?", (row["line_message_id"],)
            )
        return [r["file_path"] for r in doomed]

    # ── read path (called from an action) ──────────────────────────

    def resolve(self, message_id: str) -> tuple[Path, str] | None:
        """(absolute path, content type) if the file is still on disk."""
        with self._db.locked_ro() as conn:
            row = conn.execute(
                "SELECT file_path, content_type FROM media WHERE line_message_id = ?",
                (message_id,),
            ).fetchone()
        if row is None:
            return None
        path = (self.root / row["file_path"]).resolve()
        # Defence in depth: file_path is written by _save, but a stray relative
        # segment must never let a request read outside MEDIA_DIR.
        if not path.is_relative_to(self.root) or not path.is_file():
            return None
        return path, row["content_type"]

    def stats(self) -> tuple[int, int]:
        with self._db.locked_ro() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes), 0) AS b FROM media"
            ).fetchone()
        return int(row["n"]), int(row["b"])

    # ── cleanup ────────────────────────────────────────────────────

    def unlink(self, relative_path: str) -> None:
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root):
            return
        path.unlink(missing_ok=True)

    def unlink_many(self, relative_paths: list[str]) -> None:
        for rel in relative_paths:
            self.unlink(rel)
