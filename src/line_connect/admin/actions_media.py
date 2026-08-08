"""Media actions. Registered by import (see api/admin.py)."""

from typing import Any

from fastapi.responses import FileResponse

from line_connect.admin.actions import ActionResult, AdminContext, action


@action("get_image")
async def get_image(ctx: AdminContext, body: dict[str, Any]) -> ActionResult:
    """Serve a stored media file.

    Answers a POST with binary, which app.js's api() wrapper already special
    cases (app.js:368) by reading the response as a blob.
    """
    message_id = str(body.get("message_id") or "")
    if not message_id:
        return {"error": "missing message_id"}, 400
    if ctx.media is None:
        return {"error": "media store disabled"}, 404
    found = ctx.media.resolve(message_id)
    if found is None:
        return {"error": "image not found"}, 404
    path, content_type = found
    return FileResponse(path, media_type=content_type)
