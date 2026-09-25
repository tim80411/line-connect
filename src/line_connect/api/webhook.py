"""POST /line/webhook — the only externally reachable business endpoint.

Contract: verify → dedup → persist → 200, nothing else. All real work happens
in the worker pipeline; LINE gets its response in milliseconds regardless of
how slow Dify is (upstream defect #1: the handler awaited Dify inline and blew
LINE's timeout, triggering redeliveries).

uvicorn runs with --no-access-log, so the `webhook_handled` / `webhook_rejected`
lines below are the only record that a delivery reached the app at all. A
message claimed with redelivery=true means LINE's first attempt never got here.
"""

import json
import time

import structlog
from fastapi import Request
from fastapi.responses import PlainTextResponse

from line_connect.config import Settings
from line_connect.line.signature import verify_signature

log = structlog.get_logger(__name__)


async def line_webhook(request: Request) -> PlainTextResponse:
    t0 = time.monotonic()
    settings: Settings = request.app.state.settings
    body = await request.body()
    if not body:
        return PlainTextResponse("ok")
    signature = request.headers.get("X-Line-Signature")
    if not verify_signature(settings.line_channel_secret, body, signature):
        log.warning("webhook_rejected", reason="invalid_signature", bytes=len(body))
        return PlainTextResponse("invalid signature", status_code=400)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        log.warning("webhook_rejected", reason="invalid_json", bytes=len(body))
        return PlainTextResponse("invalid json", status_code=400)

    events = payload.get("events", []) if isinstance(payload, dict) else []
    pipeline = request.app.state.pipeline
    claimed = 0
    for raw_event in events:
        if isinstance(raw_event, dict) and await pipeline.submit_raw(raw_event) is not None:
            claimed += 1

    log.info(
        "webhook_handled",
        events=len(events),
        claimed=claimed,
        handler_ms=int((time.monotonic() - t0) * 1000),
    )
    return PlainTextResponse("ok")
