"""k8s probes.

/healthz (liveness): process alive, event loop responsive. Touches nothing
external — a Dify or DB outage must not make k8s restart the pod.

/readyz (readiness): DB writable and not draining. Also no Dify check: with a
single replica, dropping the pod from Endpoints on upstream failure turns
"slow" into "502".
"""

from typing import Any

from fastapi import APIRouter, Request, Response

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request, response: Response) -> dict[str, Any]:
    app = request.app
    if not getattr(app.state, "ready", False):
        response.status_code = 503
        return {"status": "draining"}

    db = getattr(app.state, "db", None)
    if db is not None:
        try:
            await db.ping()
        except Exception:
            response.status_code = 503
            return {"status": "db_unavailable"}

    return {"status": "ok"}
