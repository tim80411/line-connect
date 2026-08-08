"""LINE webhook signature verification.

Operates on the raw request bytes. Decoding to str and re-encoding (as
upstream did) can silently diverge from what LINE actually signed.
"""

import base64
import hashlib
import hmac


def compute_signature(channel_secret: str, body: bytes) -> str:
    digest = hmac.new(channel_secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


def verify_signature(channel_secret: str, body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    return hmac.compare_digest(signature, compute_signature(channel_secret, body))
