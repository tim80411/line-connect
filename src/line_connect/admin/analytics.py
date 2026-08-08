"""Dashboard analytics: every number here is derived by querying `messages`
and `conversations` on demand, instead of being maintained as counters.

Upstream kept 6-8 KV writes per message (day bucket, hour bucket, a running
response-time sample list, per-namespace summary counters, ...). None of that
exists here — the message log is the only record, so a scan replaces a write.
That trades a few extra milliseconds per dashboard poll for one thing that
cannot happen: a counter drifting from what the log actually contains.

All reads go through the read-only connection (`Database.locked_ro`), so an
analytics scan over the whole table never contends with the webhook's writer.
Every method is synchronous, like the rest of the storage layer; callers wrap
them in `asyncio.to_thread`.
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from line_connect.storage.db import Database

#: Bucket order is significant: it is the order the UI's doughnut-chart legend
#: renders in, and it is the order upstream's own bucket dict used.
_RESPONSE_BUCKETS: tuple[str, ...] = ("<1s", "1-3s", "3-5s", "5-10s", ">10s")

# created_at is fixed-width UTC text ("2026-08-09T12:34:56.789Z"), so these
# substr() offsets are stable and index-friendly (idx_messages_created).
_MAIN_QUERY = """
    SELECT
        substr(created_at, 1, 10) AS day,
        substr(created_at, 12, 2) AS hour,
        SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS mi,
        SUM(CASE WHEN role = 'bot' THEN 1 ELSE 0 END) AS mo,
        SUM(CASE WHEN role = 'user' AND msg_type = 'image' THEN 1 ELSE 0 END) AS img,
        SUM(CASE WHEN role = 'bot' THEN latency_ms END) AS rt_sum,
        COUNT(CASE WHEN role = 'bot' THEN latency_ms END) AS rt_n
    FROM messages
    WHERE created_at >= ? AND created_at < ?
    GROUP BY day, hour
"""

_UNIQUE_USERS_QUERY = """
    SELECT substr(created_at, 1, 10) AS day, COUNT(DISTINCT chat_key) AS n
    FROM messages
    WHERE role = 'user' AND created_at >= ? AND created_at < ?
    GROUP BY day
"""

_NEW_USERS_QUERY = """
    SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n
    FROM conversations
    WHERE created_at >= ? AND created_at < ?
    GROUP BY day
"""

# NULL-safe on latency_ms: a bot row that never recorded a latency (e.g. an
# error reply) must not silently fall through to the ">10s" ELSE bucket.
_RESPONSE_BUCKET_QUERY = """
    SELECT
        CASE
            WHEN latency_ms < 1000 THEN '<1s'
            WHEN latency_ms < 3000 THEN '1-3s'
            WHEN latency_ms < 5000 THEN '3-5s'
            WHEN latency_ms < 10000 THEN '5-10s'
            ELSE '>10s'
        END AS bucket,
        COUNT(*) AS n
    FROM messages
    WHERE role = 'bot' AND latency_ms IS NOT NULL
        AND created_at >= ? AND created_at < ?
    GROUP BY bucket
"""

_WINDOW_TOTALS_QUERY = """
    SELECT
        SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) AS mi,
        SUM(CASE WHEN role = 'bot' THEN 1 ELSE 0 END) AS mo,
        SUM(CASE WHEN role = 'bot' THEN latency_ms END) AS rt_sum,
        COUNT(CASE WHEN role = 'bot' THEN latency_ms END) AS rt_n
    FROM messages
    WHERE created_at >= ? AND created_at < ?
"""


def _iso_bounds(start_d: date, end_d: date) -> tuple[str, str]:
    """Half-open [start_iso, end_iso) covering the UTC calendar days
    [start_d, end_d] inclusive.

    Comparing against plain TEXT with >= / < (no SQLite date functions) keeps
    the query portable and lets it use idx_messages_created as a range scan.
    """
    start_iso = f"{start_d.isoformat()}T00:00:00.000Z"
    end_iso = f"{(end_d + timedelta(days=1)).isoformat()}T00:00:00.000Z"
    return start_iso, end_iso


@dataclass
class _DayAgg:
    mi: int = 0
    mo: int = 0
    img: int = 0
    rt_sum: float = 0.0
    rt_n: int = 0
    hourly: list[dict[str, int]] = field(
        default_factory=lambda: [{"messages_in": 0, "messages_out": 0} for _ in range(24)]
    )


def _fold_daily(
    start_d: date,
    end_d: date,
    main_rows: list[sqlite3.Row],
    unique_rows: list[sqlite3.Row],
    new_rows: list[sqlite3.Row],
) -> list[dict[str, Any]]:
    """Combine the three range-scoped queries into one entry per day.

    Every day in [start_d, end_d] gets an entry even if the query returned no
    rows for it (zero-filled), so a chart spanning an idle stretch does not
    show a gap.
    """
    aggs: dict[str, _DayAgg] = {}
    d = start_d
    while d <= end_d:
        aggs[d.isoformat()] = _DayAgg()
        d += timedelta(days=1)

    for row in main_rows:
        agg = aggs.get(row["day"])
        if agg is None:
            continue  # defensive only: the query is already range-bounded
        hour_idx = int(row["hour"])
        mi, mo, img = row["mi"], row["mo"], row["img"]
        agg.hourly[hour_idx] = {"messages_in": mi, "messages_out": mo}
        agg.mi += mi
        agg.mo += mo
        agg.img += img
        agg.rt_sum += row["rt_sum"] or 0
        agg.rt_n += row["rt_n"] or 0

    unique_by_day = {row["day"]: row["n"] for row in unique_rows}
    new_by_day = {row["day"]: row["n"] for row in new_rows}

    daily: list[dict[str, Any]] = []
    d = start_d
    while d <= end_d:
        ds = d.isoformat()
        agg = aggs[ds]
        # rt_n (bot rows with a recorded latency), not agg.mo (all bot rows):
        # dividing by mo would silently understate the average whenever a bot
        # row exists without a latency_ms value.
        avg_rt = round(agg.rt_sum / agg.rt_n / 1000, 3) if agg.rt_n else 0
        daily.append(
            {
                "date": ds,
                "messages_in": agg.mi,
                "messages_out": agg.mo,
                "unique_users": unique_by_day.get(ds, 0),
                "new_users": new_by_day.get(ds, 0),
                "images": agg.img,
                "avg_response_time": avg_rt,
                "hourly": agg.hourly,
            }
        )
        d += timedelta(days=1)
    return daily


class AnalyticsRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    # ── internal helpers ──────────────────────────────────────────

    def _daily_rows(self, start_d: date, end_d: date) -> list[dict[str, Any]]:
        start_iso, end_iso = _iso_bounds(start_d, end_d)
        with self._db.locked_ro() as conn:
            main_rows = conn.execute(_MAIN_QUERY, (start_iso, end_iso)).fetchall()
            unique_rows = conn.execute(_UNIQUE_USERS_QUERY, (start_iso, end_iso)).fetchall()
            new_rows = conn.execute(_NEW_USERS_QUERY, (start_iso, end_iso)).fetchall()
        return _fold_daily(start_d, end_d, main_rows, unique_rows, new_rows)

    def _response_time_buckets(self, start_d: date, end_d: date) -> dict[str, int]:
        start_iso, end_iso = _iso_bounds(start_d, end_d)
        with self._db.locked_ro() as conn:
            rows = conn.execute(_RESPONSE_BUCKET_QUERY, (start_iso, end_iso)).fetchall()
        buckets = dict.fromkeys(_RESPONSE_BUCKETS, 0)
        for row in rows:
            buckets[row["bucket"]] = row["n"]
        return buckets

    def _window_totals(self, start_d: date, end_d: date) -> dict[str, Any]:
        start_iso, end_iso = _iso_bounds(start_d, end_d)
        with self._db.locked_ro() as conn:
            row = conn.execute(_WINDOW_TOTALS_QUERY, (start_iso, end_iso)).fetchone()
        mi = row["mi"] or 0
        mo = row["mo"] or 0
        rt_sum = row["rt_sum"] or 0
        rt_n = row["rt_n"] or 0
        errors = max(0, mi - mo)
        # 0, not upstream's 100.0 fallback: an empty window has nothing to
        # call a success, and reporting 100% success with zero traffic would
        # mislead an operator scanning for a problem window.
        success_rate = round(mo / mi * 100, 1) if mi > 0 else 0
        avg_rt = round(rt_sum / rt_n / 1000, 3) if rt_n else 0
        return {
            "mi": mi,
            "mo": mo,
            "avg_response_time": avg_rt,
            "errors": errors,
            "success_rate": success_rate,
        }

    # ── public API (mirrors upstream's admin_api.py response shapes) ──

    def get_analytics(self, days: int) -> dict[str, Any]:
        end_d = datetime.now(UTC).date()
        start_d = end_d - timedelta(days=days - 1)
        return {
            "daily": self._daily_rows(start_d, end_d),
            "response_times": self._response_time_buckets(start_d, end_d),
        }

    def get_analytics_realtime(self) -> dict[str, Any]:
        today = datetime.now(UTC).date()
        day = self._daily_rows(today, today)[0]
        today_data = {
            "date": day["date"],
            "messages_in": day["messages_in"],
            "messages_out": day["messages_out"],
            "unique_users": day["unique_users"],
            "avg_response_time": day["avg_response_time"],
            "hourly": day["hourly"],
        }
        with self._db.locked_ro() as conn:
            total_users = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            role_rows = conn.execute(
                "SELECT role, COUNT(*) AS n FROM messages GROUP BY role"
            ).fetchall()
        by_role = {row["role"]: row["n"] for row in role_rows}
        all_time = {
            # Lifetime and independent of message_log_retention_days, unlike
            # total_in/out below which only see messages still in the log.
            "total_users": total_users,
            "total_in": by_role.get("user", 0),
            "total_out": by_role.get("bot", 0),
        }
        return {"today": today_data, "all_time": all_time}

    def get_performance(self, days: int) -> dict[str, Any]:
        end_d = datetime.now(UTC).date()
        start_d = end_d - timedelta(days=days - 1)
        cur = self._window_totals(start_d, end_d)

        prev_end_d = start_d - timedelta(days=1)
        prev_start_d = prev_end_d - timedelta(days=days - 1)
        prev = self._window_totals(prev_start_d, prev_end_d)

        return {
            "totals": {
                "queries": cur["mi"],
                "success_rate": cur["success_rate"],
                "avg_response_time": cur["avg_response_time"],
                "errors": cur["errors"],
            },
            "prev_totals": {
                "queries": prev["mi"],
                "success_rate": prev["success_rate"],
                "errors": prev["errors"],
            },
        }

    def get_storage_info(self) -> dict[str, Any]:
        with self._db.locked_ro() as conn:
            media_row = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes), 0) AS bytes FROM media"
            ).fetchone()
            chat_count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
        size_bytes = media_row["bytes"]
        return {
            "media_count": media_row["n"],
            "media_size_bytes": size_bytes,
            "media_size_mb": round(size_bytes / (1024 * 1024), 2),
            "chat_count": chat_count,
        }

    def export_analytics(self, days: int) -> list[list[Any]]:
        """CSV rows (header + data), built from the same daily aggregate the
        charts render — so the export can never show different numbers than
        the dashboard the operator is looking at.
        """
        end_d = datetime.now(UTC).date()
        start_d = end_d - timedelta(days=days - 1)
        daily = self._daily_rows(start_d, end_d)
        rows: list[list[Any]] = [["date", "messages", "user_messages", "bot_messages", "images"]]
        for day in daily:
            rows.append(
                [
                    day["date"],
                    day["messages_in"] + day["messages_out"],
                    day["messages_in"],
                    day["messages_out"],
                    day["images"],
                ]
            )
        return rows
