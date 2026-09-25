"""LINE's reply-token rules: one minute from receipt, 20 minutes from the event."""

import pytest

from line_connect.line.reply_token import NO_REPLY_TOKEN, ReplyToken

NOW = 1_800_000_000_000
TTL = 50_000


def token(received_ago: int | None, event_ago: int | None) -> ReplyToken:
    return ReplyToken(
        value="rt-1",
        received_ms=None if received_ago is None else NOW - received_ago,
        event_ts_ms=None if event_ago is None else NOW - event_ago,
    )


@pytest.mark.parametrize(
    ("received_ago", "event_ago", "expected"),
    [
        # First delivery, answered promptly.
        (5_000, 5_500, None),
        # Redelivery: the event is 90s old but LINE restarted the minute on
        # receipt. This is the case that used to go out as a billed push.
        (5_000, 90_000, None),
        # Waited in our own queue past the TTL since it reached us.
        (51_000, 51_500, "token_expired"),
        # LINE's hard cap applies however recently the redelivery arrived.
        (1_000, 20 * 60_000, "event_too_old"),
        # Rows written before receipt time was recorded: event clock fallback.
        (None, 51_000, "token_expired"),
        (None, 5_000, None),
        # Nothing to judge by: let LINE decide.
        (None, None, None),
    ],
)
def test_skip_reason(
    received_ago: int | None, event_ago: int | None, expected: str | None
) -> None:
    assert token(received_ago, event_ago).skip_reason(NOW, TTL) == expected


def test_missing_token_is_never_usable() -> None:
    assert NO_REPLY_TOKEN.skip_reason(NOW, TTL) == "no_token"
    assert ReplyToken("", NOW, NOW).skip_reason(NOW, TTL) == "no_token"


def test_age_runs_on_the_receipt_clock() -> None:
    assert token(received_ago=3_000, event_ago=90_000).age_ms(NOW) == 3_000
    assert token(received_ago=None, event_ago=90_000).age_ms(NOW) == 90_000
    assert token(received_ago=None, event_ago=None).age_ms(NOW) is None
