"""Analytics actions: thin async wrappers around AnalyticsRepository's SQL
aggregations. Registered by import (see api/admin.py), same pattern as
actions_media.py.
"""

import asyncio
from typing import Any

from line_connect.admin.actions import ActionResult, AdminContext, action, csv_response
from line_connect.admin.analytics import AnalyticsRepository

_DEFAULT_DAYS = 7
_MIN_DAYS = 1
_MAX_DAYS = 365


def _days(body: dict[str, Any]) -> int:
    """The "days" key upstream's _resolve_date_range read. Its {start, end}
    alternative was not ported: every call site in app.js only ever sends
    `days` (7 / 30 / 90 from the date-range tabs)."""
    raw = body.get("days")
    try:
        n = int(raw) if raw is not None else _DEFAULT_DAYS
    except (TypeError, ValueError):
        n = _DEFAULT_DAYS
    return max(_MIN_DAYS, min(_MAX_DAYS, n))


def _analytics(ctx: AdminContext) -> AnalyticsRepository:
    # Built fresh per call instead of living on AdminContext: it is a
    # stateless wrapper over the shared Database, cheap to construct, and
    # this keeps AdminContext's shape from needing to change for it.
    return AnalyticsRepository(ctx.repo.db)


@action("get_analytics")
async def get_analytics(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    days = _days(body)
    return await asyncio.to_thread(_analytics(ctx).get_analytics, days)


@action("get_analytics_realtime")
async def get_analytics_realtime(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    return await asyncio.to_thread(_analytics(ctx).get_analytics_realtime)


@action("get_performance")
async def get_performance(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    days = _days(body)
    return await asyncio.to_thread(_analytics(ctx).get_performance, days)


@action("get_storage_info")
async def get_storage_info(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    data = await asyncio.to_thread(_analytics(ctx).get_storage_info)
    # media_max_mb lives on Settings, not the DB, so it is stitched in here
    # rather than in AnalyticsRepository — lets the UI's storage bar size
    # itself instead of the hardcoded /100 it used before.
    data["media_max_mb"] = ctx.settings.media_store_max_mb
    return data


@action("export_analytics")
async def export_analytics(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    days = _days(body)
    rows = await asyncio.to_thread(_analytics(ctx).export_analytics, days)
    return csv_response(rows, f"analytics-{days}d.csv")
