"""SQLite connection management and the migration runner.

Design (plan §6.1): stdlib sqlite3, one shared connection, every repository
call serialized by a threading.Lock and dispatched via asyncio.to_thread from
async code. aiosqlite would buy nothing — it is the same thread trick — and
sync repository functions keep unit tests free of an event loop.
"""

import asyncio
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def utc_now_iso() -> str:
    """UTC timestamp in the exact format SQLite's strftime('%Y-%m-%dT%H:%M:%fZ') emits.

    Millisecond precision, so Python- and SQLite-generated values sort together
    lexicographically.
    """
    now = datetime.now(UTC)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def utc_cutoff_iso(age_seconds: float) -> str:
    cutoff = datetime.now(UTC) - timedelta(seconds=age_seconds)
    return cutoff.strftime("%Y-%m-%dT%H:%M:%S.") + f"{cutoff.microsecond // 1000:03d}Z"


class Database:
    """Owns the write connection (`locked()`) and a second read-only connection
    (`locked_ro()`).

    The read-only connection exists for the admin dashboard: under WAL a reader
    never blocks the writer, so an analytics scan over the whole `messages`
    table cannot stall a webhook's inbox INSERT. It has its own lock, so admin
    reads and pipeline writes are only serialized against their own kind.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._ro_conn: sqlite3.Connection | None = None
        self._ro_lock = threading.Lock()

    def connect(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            self.path,
            check_same_thread=False,  # guarded by self._lock
            isolation_level=None,  # autocommit; explicit BEGIN where needed
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        self._conn = conn
        self._migrate()

    def connect_read(self) -> None:
        """Open the read-only connection. Call after connect() — the file and
        its schema must already exist, and mode=ro refuses to create either."""
        conn = sqlite3.connect(
            f"file:{self.path}?mode=ro",
            uri=True,
            check_same_thread=False,  # guarded by self._ro_lock
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        self._ro_conn = conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self._ro_conn is not None:
            self._ro_conn.close()
            self._ro_conn = None

    @contextmanager
    def locked(self) -> Iterator[sqlite3.Connection]:
        if self._conn is None:
            raise RuntimeError("Database not connected")
        with self._lock:
            yield self._conn

    @contextmanager
    def locked_ro(self) -> Iterator[sqlite3.Connection]:
        """Read-only connection if one is open, else the write connection.

        The fallback keeps unit tests (which only call connect()) working and
        makes connect_read() an optimization rather than a precondition.
        """
        if self._ro_conn is None:
            with self.locked() as conn:
                yield conn
            return
        with self._ro_lock:
            yield self._ro_conn

    async def ping(self) -> None:
        """Readiness check: prove the DB file is still reachable and writable."""

        def _ping() -> None:
            with self.locked() as conn:
                conn.execute("SELECT 1").fetchone()

        await asyncio.to_thread(_ping)

    def journal_mode(self) -> str:
        with self.locked() as conn:
            row = conn.execute("PRAGMA journal_mode").fetchone()
            return str(row[0])

    def _migrate(self) -> None:
        assert self._conn is not None
        conn = self._conn
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY,"
            " applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
        )
        applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = int(sql_file.name.split("_", 1)[0])
            if version in applied:
                continue
            log.info("applying_migration", version=version, file=sql_file.name)
            conn.executescript(sql_file.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (version,)
            )
