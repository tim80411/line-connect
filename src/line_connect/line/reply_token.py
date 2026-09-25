"""The reply token, modelled on LINE's rules for it.

A reply costs nothing against the monthly message quota; a push does. So the
question "may this token still be used?" decides what each answer costs, and
LINE's answer depends on *when the delivery carrying the token reached us* —
not on when the user sent the message:

- a token is usable for about one minute after receiving the webhook;
- a redelivered webhook carries the same token and restarts that minute;
- it is never usable once spent, nor 20 minutes after the event itself.

Measuring age from event.timestamp alone (as this code used to) is right for
a first delivery and wrong for every redelivery: an event LINE had to retry
arrives already a minute or more old, and went out as a billed push while its
token was still good.
"""

from dataclasses import dataclass

#: LINE refuses a reply token this long after the event, redelivered or not.
LINE_REPLY_EVENT_MAX_AGE_MS = 20 * 60 * 1000


@dataclass(frozen=True)
class ReplyToken:
    value: str | None
    #: When the delivery holding this token reached us — LINE's one-minute
    #: clock. None only for rows written before it was recorded.
    received_ms: int | None
    #: When the user acted (LINE event.timestamp) — the 20-minute hard cap.
    event_ts_ms: int | None

    def age_ms(self, now_ms: int) -> int | None:
        """Age on the clock the TTL is measured against."""
        clock = self.received_ms if self.received_ms is not None else self.event_ts_ms
        return None if clock is None else now_ms - clock

    def skip_reason(self, now_ms: int, ttl_ms: int) -> str | None:
        """None when a reply is worth attempting, else why not.

        Whether the token was already spent is not knowable from the token
        itself; the Replier tracks that.
        """
        if not self.value:
            return "no_token"
        if (
            self.event_ts_ms is not None
            and now_ms - self.event_ts_ms >= LINE_REPLY_EVENT_MAX_AGE_MS
        ):
            return "event_too_old"
        age = self.age_ms(now_ms)
        if age is not None and age >= ttl_ms:
            return "token_expired"
        return None


NO_REPLY_TOKEN = ReplyToken(value=None, received_ms=None, event_ts_ms=None)
