"""LINE Connect — reply formatting (FlexMessage + plain text).

Public entry point ported from upstream `_build_reply`: try FlexMessage when
enabled, falling back to plain text on any conversion failure or when the
FlexMessage conversion declines to produce a result (e.g. bubble too large).
"""

import logging
from typing import Any

from .flex import format_flex_reply
from .plain import format_plain_reply

logger = logging.getLogger(__name__)

__all__ = ["build_reply"]


def build_reply(answer: str, *, flex_enabled: bool, strip_md: bool) -> list[dict[str, Any]]:
    """Build LINE reply messages. Uses FlexMessage if enabled, otherwise plain text."""
    if flex_enabled:
        try:
            msgs = format_flex_reply(answer)
            if msgs:
                return msgs
        except Exception:
            logger.warning("[LC] FlexMessage conversion failed, falling back to text")
    return format_plain_reply(answer, strip_md)
