from collections.abc import Iterator
from pathlib import Path

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
