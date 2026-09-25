"""SendResult: telling a spent monthly quota apart from a transient 429."""

import pytest

from line_connect.line.client import SendResult


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (429, '{"message":"You have reached your monthly limit."}', True),
        (429, '{"message":"Too many requests"}', False),
        (400, '{"message":"You have reached your monthly limit."}', False),
        (None, "", False),
    ],
)
def test_quota_exhausted(status: int | None, body: str, expected: bool) -> None:
    assert SendResult(ok=False, status=status, body=body).quota_exhausted is expected
