"""Classification table (§7.2): status/exception → retry policy class."""

import httpx
import pytest

from line_connect.dify.errors import (
    DifyConversationInvalid,
    DifyError,
    DifyFatal,
    DifyTransient,
    classify_http_status,
    classify_transport_error,
)

MARKERS = ("conversation not exists", "conversation not found")


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (404, '{"code": "not_found"}', DifyConversationInvalid),
        (400, '{"message": "Conversation Not Exists."}', DifyConversationInvalid),
        (400, '{"message": "conversation not found"}', DifyConversationInvalid),
        (400, '{"message": "invalid query"}', DifyFatal),
        (401, '{"code": "unauthorized"}', DifyFatal),
        (403, '{"code": "forbidden"}', DifyFatal),
        (422, '{"message": "bad inputs"}', DifyFatal),
        (429, '{"message": "rate limited"}', DifyTransient),
        (500, "internal error", DifyTransient),
        (502, "bad gateway", DifyTransient),
        (503, "unavailable", DifyTransient),
    ],
)
def test_http_status_classification(status: int, body: str, expected: type[DifyError]) -> None:
    assert isinstance(classify_http_status(status, body, MARKERS), expected)


def test_marker_matching_is_case_insensitive() -> None:
    err = classify_http_status(400, "CONVERSATION NOT EXISTS", MARKERS)
    assert isinstance(err, DifyConversationInvalid)


def test_body_snippet_truncated() -> None:
    err = classify_http_status(500, "x" * 5000, MARKERS)
    assert len(str(err)) < 600


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ConnectError("refused"),
        httpx.ReadTimeout("slow"),
        httpx.ReadError("reset"),
        httpx.RemoteProtocolError("peer closed"),
        httpx.WriteError("broken pipe"),
    ],
)
def test_transport_errors_are_transient(exc: httpx.TransportError) -> None:
    assert isinstance(classify_transport_error(exc), DifyTransient)
