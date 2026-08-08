"""MediaStore: on-disk storage, the two eviction caps, path containment."""

from pathlib import Path

import pytest

from line_connect.admin.media_store import MediaStore, safe_name
from line_connect.storage.db import Database


@pytest.fixture
def store(db: Database, tmp_path: Path) -> MediaStore:
    from tests.integration.conftest import make_settings

    settings = make_settings(
        tmp_path,
        media_dir=str(tmp_path / "media"),
        media_store_max_count=3,
        media_store_max_mb=1,
    )
    media = MediaStore(settings, db)
    media.ensure_root()
    return media


class TestSafeName:
    def test_extension_from_content_type(self) -> None:
        assert safe_name("12345", "image/jpeg") == "12345.jpg"
        assert safe_name("12345", "image/png; charset=binary") == "12345.png"

    def test_unknown_type_falls_back(self) -> None:
        assert safe_name("12345", "application/x-weird") == "12345.bin"

    def test_path_separators_are_stripped(self) -> None:
        assert safe_name("../../etc/passwd", "image/jpeg") == "etcpasswd.jpg"

    def test_empty_id_still_yields_a_name(self) -> None:
        assert safe_name("///", "image/jpeg") == "unknown.jpg"


class TestSaveAndResolve:
    def test_roundtrip(self, store: MediaStore) -> None:
        store._save("user:U1", "m-1", b"JPEGDATA", "image/jpeg")
        found = store.resolve("m-1")
        assert found is not None
        path, content_type = found
        assert path.read_bytes() == b"JPEGDATA"
        assert content_type == "image/jpeg"
        assert store.stats() == (1, 8)

    def test_unknown_id(self, store: MediaStore) -> None:
        assert store.resolve("nope") is None

    def test_missing_file_is_not_served(self, store: MediaStore) -> None:
        store._save("user:U1", "m-1", b"X", "image/jpeg")
        found = store.resolve("m-1")
        assert found is not None
        found[0].unlink()
        assert store.resolve("m-1") is None

    def test_row_pointing_outside_root_is_refused(self, store: MediaStore) -> None:
        store._save("user:U1", "m-1", b"X", "image/jpeg")
        with store._db.locked() as conn:
            conn.execute("UPDATE media SET file_path = '../escaped.jpg'")
        assert store.resolve("m-1") is None


class TestEviction:
    def test_count_cap_drops_oldest(self, store: MediaStore) -> None:
        for i in range(5):
            store._save("user:U1", f"m-{i}", b"X", "image/jpeg")
        assert store.stats()[0] == 3
        assert store.resolve("m-0") is None
        assert store.resolve("m-1") is None
        assert store.resolve("m-4") is not None

    def test_size_cap_drops_oldest(self, store: MediaStore) -> None:
        half_mb = b"X" * (512 * 1024)
        store._save("user:U1", "old", half_mb, "image/jpeg")
        store._save("user:U1", "mid", half_mb, "image/jpeg")
        assert store.stats()[0] == 2
        store._save("user:U1", "new", half_mb, "image/jpeg")
        # 3 x 512KB exceeds the 1MB cap, so the oldest goes.
        assert store.stats() == (2, 1024 * 1024)
        assert store.resolve("old") is None
        assert store.resolve("new") is not None

    def test_evicted_files_are_deleted_from_disk(self, store: MediaStore) -> None:
        for i in range(5):
            store._save("user:U1", f"m-{i}", b"X", "image/jpeg")
        on_disk = {p.name for p in store.root.iterdir()}
        assert on_disk == {"m-2.jpg", "m-3.jpg", "m-4.jpg"}

    def test_resave_replaces_rather_than_duplicates(self, store: MediaStore) -> None:
        store._save("user:U1", "m-1", b"AAA", "image/jpeg")
        store._save("user:U1", "m-1", b"BBBB", "image/jpeg")
        assert store.stats() == (1, 4)


class TestUnlink:
    def test_unlink_many(self, store: MediaStore) -> None:
        store._save("user:U1", "m-1", b"X", "image/jpeg")
        store._save("user:U1", "m-2", b"X", "image/jpeg")
        store.unlink_many(["m-1.jpg", "m-2.jpg", "gone.jpg"])
        assert list(store.root.iterdir()) == []

    def test_unlink_refuses_to_escape_root(self, store: MediaStore, tmp_path: Path) -> None:
        outside = tmp_path / "precious.txt"
        outside.write_text("keep")
        store.unlink("../precious.txt")
        assert outside.exists()
