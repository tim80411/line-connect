from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from line_connect.storage.db import Database
from line_connect.storage.repository import Repository


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(str(tmp_path / "test.db"))
    database.connect()
    yield database
    database.close()


@pytest.fixture
def repo(db: Database) -> Repository:
    return Repository(db)


class RecordingLogger:
    """Stand-in for a module's structlog `log`, swapped in with monkeypatch.

    structlog.testing.capture_logs is unreliable here: setup_logging() turns on
    cache_logger_on_first_use, so which loggers it sees depends on test order.
    """

    def __init__(self) -> None:
        self.records: list[tuple[str, str, dict[str, Any]]] = []

    def _record(self, level: str) -> Callable[..., None]:
        def emit(event: str, **kw: Any) -> None:
            self.records.append((level, event, kw))

        return emit

    def __getattr__(self, level: str) -> Callable[..., None]:
        return self._record(level)

    def events(self, name: str) -> list[dict[str, Any]]:
        return [kw for _, event, kw in self.records if event == name]


@pytest.fixture
def record_logs(monkeypatch: pytest.MonkeyPatch) -> Callable[[Any], RecordingLogger]:
    """record_logs(module) → RecordingLogger replacing that module's `log`."""

    def install(module: Any) -> RecordingLogger:
        recorder = RecordingLogger()
        monkeypatch.setattr(module, "log", recorder)
        return recorder

    return install
