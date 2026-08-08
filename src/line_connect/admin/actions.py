"""Action registry and dispatch.

Shape inherited from upstream: one POST endpoint, an `action` field in the JSON
body, one handler per action. It is not REST, and that is deliberate — the
ported SPA derives its API URL from its own page URL (app.js:105) and funnels
every call through one wrapper, so keeping the envelope identical means the
~40 call sites in app.js needed no changes at all.

Handlers register themselves with @action. Feature modules (analytics, media)
import this module and add their own, so no single file owns every action.
"""

import asyncio
import csv
import io
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog
from fastapi import Response
from fastapi.responses import JSONResponse

from line_connect.admin.auth import AuthService
from line_connect.admin.repository import TYPING_MAX_AGE_SECONDS, AdminRepository
from line_connect.config import Settings
from line_connect.line.client import LineClient
from line_connect.line.messages import text_msg
from line_connect.storage.db import utc_cutoff_iso

if TYPE_CHECKING:
    from line_connect.admin.media_store import MediaStore

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class AdminContext:
    settings: Settings
    repo: AdminRepository
    auth: AuthService
    line: LineClient
    media: "MediaStore | None"
    client_ip: str


#: dict body (200), (dict, status), or a ready-made Response for binary/CSV.
ActionResult = dict[str, Any] | tuple[dict[str, Any], int] | Response
Handler = Callable[[AdminContext, dict[str, Any]], Awaitable[ActionResult]]


@dataclass(frozen=True)
class Action:
    handler: Handler
    requires_auth: bool


REGISTRY: dict[str, Action] = {}


def action(name: str, *, auth: bool = True) -> Callable[[Handler], Handler]:
    def register(handler: Handler) -> Handler:
        if name in REGISTRY:
            raise RuntimeError(f"duplicate admin action: {name}")
        REGISTRY[name] = Action(handler=handler, requires_auth=auth)
        return handler

    return register


def _error(message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


async def dispatch(ctx: AdminContext, body: dict[str, Any]) -> Response:
    name = str(body.get("action") or "")
    entry = REGISTRY.get(name)
    if entry is None:
        return _error(f"unknown action: {name}", 400)
    try:
        if entry.requires_auth:
            token = body.get("token")
            # No password fallback here — see admin/auth.py.
            if not isinstance(token, str) or not ctx.auth.validate(token):
                return _error("unauthorized", 401)
        result = await entry.handler(ctx, body)
    except Exception:
        log.exception("admin_action_failed", action=name)
        return _error("internal error", 500)
    if isinstance(result, Response):
        return result
    if isinstance(result, tuple):
        payload, status = result
        return JSONResponse(payload, status_code=status)
    return JSONResponse(result)


def _chat_id(body: dict[str, Any]) -> str:
    return str(body.get("chat_id") or "")


# ── auth / unauthenticated ─────────────────────────────────────────


@action("login", auth=False)
async def login(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    payload, status = ctx.auth.login(str(body.get("password") or ""), ctx.client_ip)
    return payload, status


@action("get_bot_info", auth=False)
async def get_bot_info(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    """Unauthenticated so the login screen can show the OA's name and icon.

    Same trade-off upstream made: it reveals which official account this
    deployment serves, which is public information on LINE anyway.
    """
    info = await ctx.line.get_bot_info()
    return info or {"error": "Could not fetch bot info"}


@action("health", auth=False)
async def health(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    from line_connect import __version__

    return {"status": "ok", "version": __version__}


# ── chats ──────────────────────────────────────────────────────────


@action("list_chats")
async def list_chats(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    chats = await asyncio.to_thread(ctx.repo.list_chats)
    return {"chats": chats}


@action("get_history")
async def get_history(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    chat_id = _chat_id(body)
    if not chat_id:
        return {"error": "missing chat_id"}, 400
    limit = ctx.settings.admin_history_limit
    history = await asyncio.to_thread(ctx.repo.get_history, chat_id, limit)
    cutoff = utc_cutoff_iso(TYPING_MAX_AGE_SECONDS)
    typing = await asyncio.to_thread(ctx.repo.is_typing, chat_id, cutoff)
    return {"history": history, "typing": typing}


@action("get_chat_meta")
async def get_chat_meta(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    chat_id = _chat_id(body)
    if not chat_id:
        return {"error": "missing chat_id"}, 400
    meta = await asyncio.to_thread(ctx.repo.get_chat_meta, chat_id)
    return {"meta": meta}


@action("update_chat_meta")
async def update_chat_meta(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    chat_id = _chat_id(body)
    if not chat_id:
        return {"error": "missing chat_id"}, 400
    fields: dict[str, Any] = {
        k: body[k] for k in ("custom_name", "notes", "starred", "tags") if k in body
    }
    meta = await asyncio.to_thread(ctx.repo.update_chat_meta, chat_id, fields)
    return {"ok": True, "meta": meta}


# ── outbound ───────────────────────────────────────────────────────


@action("send_message")
async def send_message(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    """Operator replies by hand. Costs a LINE push message from the account's
    monthly quota — this is not a reply-token reply."""
    chat_id = _chat_id(body)
    text = str(body.get("text") or "").strip()
    if not chat_id or not text:
        return {"error": "missing chat_id or text"}, 400

    row = await asyncio.to_thread(ctx.repo.get_conversation, chat_id)
    if row is None:
        return {"error": "chat not found"}, 404
    target = row["source_id"]
    if not target:
        return {"error": "chat has no push target"}, 404

    bot_info = await ctx.line.get_bot_info()
    text = text.replace(
        "{username}", row["custom_name"] or row["display_name"] or "User"
    ).replace("{account_name}", bot_info.get("displayName") or "LINE Official Account")

    if not await ctx.line.push(target, [text_msg(text)]):
        return {"error": "LINE push failed"}, 502
    await asyncio.to_thread(ctx.repo.log_admin_message, chat_id, text)
    return {"ok": True, "sent_to": target}


# ── destructive ────────────────────────────────────────────────────


@action("clear_history")
async def clear_history(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    """Wipes one chat's message log.

    Known consequence: analytics is computed from that same log, so clearing a
    chat retroactively changes the charts. Upstream kept separate counters and
    did not have this coupling. Accepted — a soft-delete flag would complicate
    every aggregate for a rarely-used action.
    """
    chat_id = _chat_id(body)
    if not chat_id:
        return {"error": "missing chat_id"}, 400
    paths = await asyncio.to_thread(ctx.repo.clear_history, chat_id)
    if ctx.media is not None and paths:
        await asyncio.to_thread(ctx.media.unlink_many, paths)
    return {"ok": True}


@action("clear_all_chats")
async def clear_all_chats(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    count, paths = await asyncio.to_thread(ctx.repo.clear_all_chats)
    if ctx.media is not None and paths:
        await asyncio.to_thread(ctx.media.unlink_many, paths)
    return {"ok": True, "cleared": count}


@action("export_chat")
async def export_chat(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    """Full history, not the ≤100 messages the browser happens to be holding
    (upstream's export was built client-side from the loaded page)."""
    chat_id = _chat_id(body)
    if not chat_id:
        return {"error": "missing chat_id"}, 400
    rows = await asyncio.to_thread(
        ctx.repo.export_history, chat_id, ctx.settings.admin_export_max_rows
    )
    safe_id = "".join(c if c.isalnum() else "_" for c in chat_id)
    if str(body.get("format") or "csv").lower() == "json":
        return json_export_response(rows, f"chat_{safe_id}.json")
    table: list[list[Any]] = [["timestamp", "role", "name", "type", "text"]]
    table.extend(
        [m["ts"], m["r"], m.get("n", ""), m.get("tp", "text"), m["t"]] for m in rows
    )
    return csv_response(table, f"chat_{safe_id}.csv")


# ── tags / templates ───────────────────────────────────────────────


@action("manage_tags")
async def manage_tags(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    op = str(body.get("op") or "list")
    tag = str(body.get("tag") or "").strip()
    if op == "add":
        if not tag:
            return {"error": "missing tag"}, 400
        await asyncio.to_thread(ctx.repo.add_tag, tag)
    elif op == "remove":
        if not tag:
            return {"error": "missing tag"}, 400
        await asyncio.to_thread(ctx.repo.remove_tag, tag)
    elif op == "rename":
        new = str(body.get("new_tag") or "").strip()
        if not tag or not new:
            return {"error": "missing tag or new_tag"}, 400
        await asyncio.to_thread(ctx.repo.rename_tag, tag, new)
    elif op != "list":
        return {"error": f"unknown op: {op}"}, 400
    return {"tags": await asyncio.to_thread(ctx.repo.list_tags)}


@action("manage_templates")
async def manage_templates(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    op = str(body.get("op") or "list")
    template_id = str(body.get("id") or "")
    title = str(body.get("title") or "").strip()
    text = str(body.get("body") or "").strip()
    if op == "add":
        if not title or not text:
            return {"error": "missing title or body"}, 400
        await asyncio.to_thread(ctx.repo.add_template, title, text)
    elif op == "delete":
        if not template_id:
            return {"error": "missing id"}, 400
        await asyncio.to_thread(ctx.repo.delete_template, template_id)
    elif op in ("edit", "update"):
        # Upstream shipped both names for the same operation; the UI uses
        # whichever the editor's save path was written against.
        if not template_id or not title or not text:
            return {"error": "missing id, title or body"}, 400
        await asyncio.to_thread(ctx.repo.update_template, template_id, title, text)
    elif op != "list":
        return {"error": f"unknown op: {op}"}, 400
    return {"templates": await asyncio.to_thread(ctx.repo.list_templates)}


# ── Phase B placeholders ───────────────────────────────────────────


@action("get_schedule")
async def get_schedule(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    """Business-hours scheduling is Phase B. The chat view still asks for it on
    open, so answer benignly rather than making the UI swallow a 400."""
    return {"schedule": {}, "is_outside": False}


# ── shared helpers for other action modules ────────────────────────


def csv_response(rows: list[list[Any]], filename: str) -> Response:
    """CSV built in memory: an export is capped at ADMIN_EXPORT_MAX_ROWS, which
    at the observed message sizes is single-digit MB — streaming would add
    complexity to save nothing."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    return Response(
        content=buf.getvalue().encode("utf-8-sig"),  # BOM: Excel reads UTF-8
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def json_export_response(payload: Any, filename: str) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
