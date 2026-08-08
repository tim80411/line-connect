"""Dify error taxonomy. The classification *is* the retry policy (plan §5.3):

- DifyTransient           → retry on the blocking transport, keep the cid
- DifyConversationInvalid → the only class allowed to drop a conversation_id
- DifyFatal               → give up, keep the cid

Upstream dropped the cid after any two failures, so a network blip became a
permanently reset conversation (issue #1 root cause #3).
"""

from collections.abc import Sequence

import httpx

MAX_BODY_SNIPPET = 500


class DifyError(Exception):
    pass


class DifyTransient(DifyError):
    """Network/timeout/5xx/429 — the conversation itself is fine."""


class DifyConversationInvalid(DifyError):
    """Dify explicitly reports the conversation does not exist."""


class DifyFatal(DifyError):
    """Configuration or app errors (401/403, other 4xx, SSE error events)."""


def classify_http_status(
    status: int, body: str, conversation_markers: Sequence[str]
) -> DifyError:
    snippet = body[:MAX_BODY_SNIPPET]
    if status == 404:
        return DifyConversationInvalid(f"HTTP 404: {snippet}")
    if 400 <= status < 500:
        lowered = body.lower()
        if any(marker in lowered for marker in conversation_markers):
            return DifyConversationInvalid(f"HTTP {status}: {snippet}")
    if status == 429 or status >= 500:
        return DifyTransient(f"HTTP {status}: {snippet}")
    return DifyFatal(f"HTTP {status}: {snippet}")


def classify_transport_error(exc: httpx.TransportError) -> DifyTransient:
    """Connect failures, read timeouts, protocol breaks, mid-stream cuts."""
    return DifyTransient(f"{type(exc).__name__}: {exc}")
