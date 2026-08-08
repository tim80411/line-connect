"""App factory and lifespan.

Run with factory mode so importing this module never instantiates Settings:
    uvicorn line_connect.main:create_app --factory
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import structlog
from fastapi import FastAPI

from line_connect import __version__
from line_connect.admin.media_store import MediaStore
from line_connect.api import health
from line_connect.api.webhook import line_webhook
from line_connect.config import Settings
from line_connect.dify.client import DifyClient
from line_connect.line.client import LineClient
from line_connect.logging_setup import setup_logging
from line_connect.pipeline.handlers import Bridge
from line_connect.pipeline.notify import Notifier
from line_connect.pipeline.queue import FailureHook, Handler, Pipeline
from line_connect.pipeline.replier import Replier
from line_connect.storage.db import Database
from line_connect.storage.repository import Repository

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    db = Database(settings.database_path)
    db.connect()
    db.connect_read()
    app.state.db = db
    repo = Repository(db)
    app.state.repo = repo

    http_client = httpx.AsyncClient()
    line = LineClient(settings, http_client)
    dify = DifyClient(settings, http_client)
    replier = Replier(settings, line, repo)
    notifier = Notifier(settings, replier)

    media: MediaStore | None = None
    if settings.media_store_enabled:
        media = MediaStore(settings, db)
        media.ensure_root()
    app.state.media = media

    bridge = Bridge(settings, repo, line, dify, replier, notifier, media)
    app.state.bridge = bridge
    app.state.line = line

    if settings.admin_enabled:
        from line_connect.admin.auth import AuthService
        from line_connect.admin.repository import AdminRepository

        admin_repo = AdminRepository(db)
        app.state.admin_repo = admin_repo
        app.state.admin_auth = AuthService(settings, admin_repo)

    pipeline = Pipeline(
        settings,
        repo,
        handler=app.state.handler_override or bridge.handle_event,
        on_failure=app.state.failure_hook_override or bridge.on_job_failure,
        flush_handler=bridge.flush_media,
    )
    bridge.attach_pipeline(pipeline)
    await pipeline.start()
    app.state.pipeline = pipeline

    app.state.ready = True
    log.info(
        "startup_complete",
        version=__version__,
        workers=settings.worker_count,
        journal_mode=db.journal_mode(),
    )
    yield
    # Shutdown order (plan §5.6): readyz red → let kube-proxy converge →
    # drain workers → leave the rest in the DB for next-boot recovery.
    app.state.ready = False
    await asyncio.sleep(settings.drain_delay_seconds)
    bridge.cancel_debounce()
    await pipeline.stop()
    await http_client.aclose()
    db.close()
    log.info("shutdown_complete")


def create_app(
    settings: Settings | None = None,
    handler: Handler | None = None,
    on_failure: FailureHook | None = None,
) -> FastAPI:
    settings = settings or Settings()  # type: ignore[call-arg]  # env-populated
    setup_logging(settings.log_level, settings.log_format)

    app = FastAPI(
        title="line-connect",
        version=__version__,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings
    app.state.ready = False
    app.state.handler_override = handler
    app.state.failure_hook_override = on_failure
    app.include_router(health.router)
    app.add_api_route(settings.webhook_path, line_webhook, methods=["POST"])
    if settings.admin_enabled:
        # Imported only when enabled: with no ADMIN_PASSWORD the admin package
        # is never loaded and the routes simply do not exist (fail-closed).
        from line_connect.api.admin import build_router

        app.include_router(build_router(settings))
    return app
