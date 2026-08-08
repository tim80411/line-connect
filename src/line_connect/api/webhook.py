"""POST /line/webhook — the only externally reachable business endpoint.

Contract: verify → dedup → persist → 200, nothing else. All real work happens
in the worker pipeline; LINE gets its response in milliseconds regardless of
how slow Dify is (upstream defect #1: the handler awaited Dify inline and blew
LINE's timeout, triggering redeliveries).
"""

import json

from fastapi import Request
from fastapi.responses import PlainTextResponse

from line_connect.config import Settings
from line_connect.line.signature import verify_signature


async def line_webhook(request: Request) -> PlainTextResponse:
    settings: Settings = request.app.state.settings
    body = await request.body()
    if not body:
        return PlainTextResponse("ok")
    signature = request.headers.get("X-Line-Signature")
    if not verify_signature(settings.line_channel_secret, body, signature):
        return PlainTextResponse("invalid signature", status_code=400)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return PlainTextResponse("invalid json", status_code=400)

    events = payload.get("events", []) if isinstance(payload, dict) else []
    pipeline = request.app.state.pipeline
    for raw_event in events:
        if isinstance(raw_event, dict):
            await pipeline.submit_raw(raw_event)

    return PlainTextResponse("ok")
