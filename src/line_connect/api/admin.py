"""Admin routes: GET serves the dashboard, POST runs one action.

Both live at the same path on purpose. The ported SPA computes its API base
from `location.href` (app.js:105), so serving the page at /admin means it posts
to /admin — the UI's transport layer needed no porting at all.
"""

from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse

from line_connect.admin import actions as core_actions
from line_connect.admin import actions_analytics, actions_media  # noqa: F401 - registers actions
from line_connect.admin.actions import AdminContext, dispatch
from line_connect.config import Settings

log = structlog.get_logger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "admin" / "static"


def render_dashboard() -> str:
    """Inline CSS and JS into one document, as upstream's endpoints/admin.py did.

    One request, no static mount, no cache-busting to think about — the whole
    dashboard is ~200KB of text.
    """
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    return html.replace("/* __CSS__ */", css).replace("/* __JS__ */", js)


def client_ip_of(request: Request, trust_proxy: bool) -> str:
    """Identity for login throttling.

    Behind the cluster ingress every request arrives from the same pod IP, so
    without X-Forwarded-For one attacker's lockout would lock out everyone.
    The header is only trusted when ADMIN_TRUST_PROXY_HEADERS says a proxy is
    actually in front — trusting it on a directly-exposed service would let a
    client mint a fresh identity per attempt.
    """
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def build_router(settings: Settings) -> APIRouter:
    """Routes are registered at app-construction time; the services they need
    are looked up from app.state per request, because those only exist once
    lifespan has opened the database."""
    router = APIRouter()
    page = render_dashboard()

    @router.get(settings.admin_path, response_class=HTMLResponse)
    async def dashboard() -> HTMLResponse:
        return HTMLResponse(
            page,
            headers={
                # The login wall lives inside the page; keep it out of caches.
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "same-origin",
            },
        )

    @router.post(settings.admin_path)
    async def admin_api(request: Request) -> Response:
        try:
            body: Any = await request.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            return Response(
                content='{"error":"invalid body"}',
                status_code=400,
                media_type="application/json",
            )
        state = request.app.state
        ctx = AdminContext(
            settings=settings,
            repo=state.admin_repo,
            auth=state.admin_auth,
            line=state.line,
            media=state.media,
            client_ip=client_ip_of(request, settings.admin_trust_proxy_headers),
        )
        return await dispatch(ctx, body)

    log.info(
        "admin_mounted", path=settings.admin_path, actions=len(core_actions.REGISTRY)
    )
    return router
