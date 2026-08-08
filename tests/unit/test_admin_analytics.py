"""Analytics aggregation tests: exact numbers from seeded rows, not just
"is non-empty" (A3). Every SQL aggregation in analytics.py is exercised
against a real SQLite file, same approach as test_repository.py.

Timestamps are built relative to the real UTC "now" rather than a fixed
calendar date, because get_analytics/get_performance always resolve their
window against datetime.now(UTC).date() — there is no clock injection point.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from line_connect.admin.analytics import AnalyticsRepository
from line_connect.storage.db import Database
from line_connect.storage.repository import Repository


@pytest.fixture
def analytics(db: Database) -> AnalyticsRepository:
    return AnalyticsRepository(db)


def _seed_message(
    repo: Repository,
    db: Database,
    chat_key: str,
    role: str,
    created_at: str,
    msg_type: str = "text",
    latency_ms: int | None = None,
) -> None:
    """Insert via the real write path, then pin created_at like
    test_repository.py::TestRetention does — log_message always stamps "now",
    so the explicit timestamp has to be applied after the fact."""
    repo.log_message(chat_key, role, text="msg", msg_type=msg_type, latency_ms=latency_ms)
    with db.locked() as conn:
        row_id = conn.execute(
            "SELECT id FROM messages WHERE chat_key = ? ORDER BY id DESC LIMIT 1", (chat_key,)
        ).fetchone()[0]
        conn.execute("UPDATE messages SET created_at = ? WHERE id = ?", (created_at, row_id))


def _seed_conversation(
    repo: Repository, db: Database, chat_key: str, created_at: str
) -> None:
    repo.ensure_conversation(chat_key, "user", chat_key, dify_user=chat_key)
    with db.locked() as conn:
        conn.execute(
            "UPDATE conversations SET created_at = ? WHERE chat_key = ?", (created_at, chat_key)
        )


def _today() -> Any:
    return datetime.now(UTC).date()


class TestGetAnalyticsBucketing:
    def test_day_and_hour_bucketing_across_boundary(
        self, db: Database, repo: Repository, analytics: AnalyticsRepository
    ) -> None:
        today = _today()
        yesterday = today - timedelta(days=1)
        _seed_message(repo, db, "user:U1", "user", f"{yesterday.isoformat()}T23:59:59.999Z")
        _seed_message(repo, db, "user:U1", "user", f"{today.isoformat()}T00:00:00.001Z")

        data = analytics.get_analytics(2)
        daily = {d["date"]: d for d in data["daily"]}

        assert daily[yesterday.isoformat()]["hourly"][23]["messages_in"] == 1
        assert daily[yesterday.isoformat()]["hourly"][22]["messages_in"] == 0
        assert daily[yesterday.isoformat()]["messages_in"] == 1
        assert daily[today.isoformat()]["hourly"][0]["messages_in"] == 1
        assert daily[today.isoformat()]["messages_in"] == 1

    def test_zero_fill_for_idle_day(
        self, db: Database, repo: Repository, analytics: AnalyticsRepository
    ) -> None:
        today = _today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)
        _seed_message(repo, db, "user:U1", "user", f"{two_days_ago.isoformat()}T10:00:00.000Z")
        _seed_message(repo, db, "user:U1", "user", f"{today.isoformat()}T10:00:00.000Z")

        data = analytics.get_analytics(3)
        dates = [d["date"] for d in data["daily"]]
        assert dates == [two_days_ago.isoformat(), yesterday.isoformat(), today.isoformat()]

        idle = next(d for d in data["daily"] if d["date"] == yesterday.isoformat())
        assert idle["messages_in"] == 0
        assert idle["messages_out"] == 0
        assert idle["unique_users"] == 0
        assert idle["new_users"] == 0
        assert idle["images"] == 0
        assert idle["avg_response_time"] == 0
        assert idle["hourly"] == [{"messages_in": 0, "messages_out": 0} for _ in range(24)]


class TestUniqueAndNewUsers:
    def test_unique_users_distinct_per_day(
        self, db: Database, repo: Repository, analytics: AnalyticsRepository
    ) -> None:
        ts = f"{_today().isoformat()}T10:00:00.000Z"
        _seed_message(repo, db, "user:A", "user", ts)
        _seed_message(repo, db, "user:A", "user", ts)  # same user, second message
        _seed_message(repo, db, "user:B", "user", ts)

        data = analytics.get_analytics(1)
        assert data["daily"][0]["unique_users"] == 2
        assert data["daily"][0]["messages_in"] == 3  # not deduped, unlike unique_users

    def test_new_users_from_conversations_created_at(
        self, db: Database, repo: Repository, analytics: AnalyticsRepository
    ) -> None:
        today = _today()
        yesterday = today - timedelta(days=1)
        _seed_conversation(repo, db, "user:A", f"{yesterday.isoformat()}T09:00:00.000Z")
        _seed_conversation(repo, db, "user:B", f"{today.isoformat()}T09:00:00.000Z")
        _seed_conversation(repo, db, "user:C", f"{today.isoformat()}T10:00:00.000Z")

        data = analytics.get_analytics(2)
        daily = {d["date"]: d for d in data["daily"]}
        assert daily[yesterday.isoformat()]["new_users"] == 1
        assert daily[today.isoformat()]["new_users"] == 2


class TestResponseTimeBuckets:
    def test_bucket_boundaries(
        self, db: Database, repo: Repository, analytics: AnalyticsRepository
    ) -> None:
        ts = f"{_today().isoformat()}T10:00:00.000Z"
        # boundary values named in the task brief: 999/1000/2999/3000/9999/10000
        latencies = [999, 1000, 2999, 3000, 9999, 10000]
        for i, ms in enumerate(latencies):
            _seed_message(repo, db, f"user:U{i}", "bot", ts, latency_ms=ms)

        data = analytics.get_analytics(1)
        assert data["response_times"] == {
            "<1s": 1,  # 999
            "1-3s": 2,  # 1000, 2999
            "3-5s": 1,  # 3000
            "5-10s": 1,  # 9999
            ">10s": 1,  # 10000
        }

    def test_bot_row_without_latency_is_excluded_not_miscounted(
        self, db: Database, repo: Repository, analytics: AnalyticsRepository
    ) -> None:
        """A bot row with no recorded latency must not fall into the ">10s"
        ELSE bucket by accident (latency_ms IS NOT NULL guard in the query)."""
        ts = f"{_today().isoformat()}T10:00:00.000Z"
        _seed_message(repo, db, "user:U1", "bot", ts, latency_ms=None)

        data = analytics.get_analytics(1)
        assert data["response_times"] == {"<1s": 0, "1-3s": 0, "3-5s": 0, "5-10s": 0, ">10s": 0}
        # still counted as a bot message for messages_out
        assert data["daily"][0]["messages_out"] == 1
        # but contributes nothing to the average (rt_n stays 0)
        assert data["daily"][0]["avg_response_time"] == 0


class TestGetAnalyticsRealtime:
    def test_today_and_all_time(
        self, db: Database, repo: Repository, analytics: AnalyticsRepository
    ) -> None:
        today = _today()
        yesterday = today - timedelta(days=1)
        _seed_conversation(repo, db, "user:A", f"{yesterday.isoformat()}T09:00:00.000Z")
        _seed_conversation(repo, db, "user:B", f"{today.isoformat()}T09:00:00.000Z")
        _seed_message(repo, db, "user:A", "user", f"{yesterday.isoformat()}T09:05:00.000Z")
        _seed_message(repo, db, "user:B", "user", f"{today.isoformat()}T09:05:00.000Z")
        _seed_message(
            repo, db, "user:B", "bot", f"{today.isoformat()}T09:05:01.000Z", latency_ms=1500
        )

        data = analytics.get_analytics_realtime()

        assert data["today"]["date"] == today.isoformat()
        assert data["today"]["messages_in"] == 1
        assert data["today"]["messages_out"] == 1
        assert data["today"]["unique_users"] == 1
        assert data["today"]["avg_response_time"] == 1.5
        assert len(data["today"]["hourly"]) == 24

        # all_time.total_users counts every conversation ever seen, unaffected
        # by message retention — includes yesterday's chat too.
        assert data["all_time"]["total_users"] == 2
        assert data["all_time"]["total_in"] == 2
        assert data["all_time"]["total_out"] == 1


class TestGetPerformance:
    def test_previous_period_comparison(
        self, db: Database, repo: Repository, analytics: AnalyticsRepository
    ) -> None:
        today = _today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        # current window (days=1 -> today only)
        _seed_message(repo, db, "user:U1", "user", f"{today.isoformat()}T10:00:00.000Z")
        _seed_message(
            repo, db, "user:U1", "bot", f"{today.isoformat()}T10:00:01.000Z", latency_ms=2000
        )
        # previous window (yesterday only, same length as current)
        _seed_message(repo, db, "user:U2", "user", f"{yesterday.isoformat()}T10:00:00.000Z")
        _seed_message(repo, db, "user:U2", "user", f"{yesterday.isoformat()}T11:00:00.000Z")
        # outside both windows - must not leak into either total
        _seed_message(repo, db, "user:U3", "user", f"{two_days_ago.isoformat()}T10:00:00.000Z")

        data = analytics.get_performance(1)

        assert data["totals"]["queries"] == 1
        assert data["totals"]["errors"] == 0
        assert data["totals"]["success_rate"] == 100.0
        assert data["totals"]["avg_response_time"] == 2.0

        assert data["prev_totals"]["queries"] == 2
        assert data["prev_totals"]["errors"] == 2
        assert data["prev_totals"]["success_rate"] == 0.0
        assert "avg_response_time" not in data["prev_totals"]  # matches upstream's shape

    def test_success_rate_and_errors_when_no_messages(
        self, analytics: AnalyticsRepository
    ) -> None:
        """in == 0 must not raise ZeroDivisionError, and must not report the
        upstream 100%-success fallback for an empty window (see analytics.py
        comment on _window_totals)."""
        data = analytics.get_performance(1)
        assert data["totals"] == {
            "queries": 0,
            "success_rate": 0,
            "avg_response_time": 0,
            "errors": 0,
        }


class TestGetStorageInfo:
    def test_media_and_chat_counts(
        self, db: Database, repo: Repository, analytics: AnalyticsRepository
    ) -> None:
        _seed_conversation(repo, db, "user:A", "2026-01-01T00:00:00.000Z")
        _seed_conversation(repo, db, "user:B", "2026-01-01T00:00:00.000Z")
        with db.locked() as conn:
            conn.execute(
                "INSERT INTO media(line_message_id, chat_key, content_type, size_bytes,"
                " file_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("m1", "user:A", "image/png", 1_048_576, "a/m1.png", "2026-01-01T00:00:00.000Z"),
            )
            conn.execute(
                "INSERT INTO media(line_message_id, chat_key, content_type, size_bytes,"
                " file_path, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("m2", "user:B", "image/png", 524_288, "b/m2.png", "2026-01-01T00:00:00.000Z"),
            )

        data = analytics.get_storage_info()

        assert data["media_count"] == 2
        assert data["media_size_bytes"] == 1_572_864
        assert data["media_size_mb"] == 1.5
        assert data["chat_count"] == 2

    def test_empty_storage(self, analytics: AnalyticsRepository) -> None:
        assert analytics.get_storage_info() == {
            "media_count": 0,
            "media_size_bytes": 0,
            "media_size_mb": 0,
            "chat_count": 0,
        }


class TestExportAnalytics:
    def test_csv_rows_match_daily_aggregate(
        self, db: Database, repo: Repository, analytics: AnalyticsRepository
    ) -> None:
        ts = f"{_today().isoformat()}T10:00:00.000Z"
        _seed_message(repo, db, "user:U1", "user", ts, msg_type="image")
        _seed_message(repo, db, "user:U1", "bot", ts, latency_ms=1200)

        rows = analytics.export_analytics(1)

        assert rows[0] == ["date", "messages", "user_messages", "bot_messages", "images"]
        assert rows[1] == [_today().isoformat(), 2, 1, 1, 1]


class TestActionRegistration:
    def test_actions_registered_with_auth_required(self) -> None:
        import line_connect.admin.actions_analytics  # noqa: F401 - side effect: registers actions
        from line_connect.admin.actions import REGISTRY

        for name in (
            "get_analytics",
            "get_analytics_realtime",
            "get_performance",
            "get_storage_info",
            "export_analytics",
        ):
            assert name in REGISTRY
            assert REGISTRY[name].requires_auth is True


class TestDaysClamping:
    @pytest.mark.parametrize(
        ("body", "expected"),
        [
            ({}, 7),
            ({"days": 30}, 30),
            ({"days": 0}, 1),
            ({"days": -5}, 1),
            ({"days": 9999}, 365),
            ({"days": "not-a-number"}, 7),
            ({"days": None}, 7),
        ],
    )
    def test_clamped_default(self, body: dict[str, Any], expected: int) -> None:
        from line_connect.admin.actions_analytics import _days

        assert _days(body) == expected
