"""Password → token exchange, token validation, and per-IP login throttling.

Two upstream defects are fixed here:

1. Upstream compared the password with `!=` (endpoints/line.py:117), which
   leaks length and prefix through timing. We use hmac.compare_digest.
2. Upstream fell back to accepting the raw password on *every* action when the
   token check failed (endpoints/line.py:127-130), so a leaked password stayed
   usable forever and tokens bought nothing. There is no fallback here: only
   `login` ever looks at the password.
"""

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass, field

import structlog

from line_connect.admin.repository import AdminRepository
from line_connect.config import Settings
from line_connect.storage.db import utc_now_iso

log = structlog.get_logger(__name__)

TOKEN_BYTES = 32
#: Drop rate-limit entries older than this so the dict cannot grow unbounded.
RATE_LIMIT_ENTRY_TTL_SECONDS = 3600.0


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def expires_at(ttl_hours: int) -> str:
    """ISO timestamp `ttl_hours` from now, in utc_now_iso()'s sortable format."""
    from datetime import UTC, datetime, timedelta

    moment = datetime.now(UTC) + timedelta(hours=ttl_hours)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


@dataclass
class _Attempts:
    count: int = 0
    locked_until: float = 0.0  # time.monotonic() deadline
    touched: float = 0.0


@dataclass
class LoginRateLimiter:
    """Per-IP failure counter, in memory.

    In memory is sufficient and honest: the SQLite design already pins this
    service to a single process, so there is no second replica to share state
    with. A restart clears the counters — an attacker would have to be able to
    restart the pod to exploit that.
    """

    max_attempts: int
    lockout_seconds: float
    _entries: dict[str, _Attempts] = field(default_factory=dict)

    def allowed(self, ip: str) -> bool:
        entry = self._entries.get(ip)
        if entry is None:
            return True
        return entry.locked_until <= time.monotonic()

    def record(self, ip: str, *, success: bool) -> None:
        now = time.monotonic()
        self._evict_stale(now)
        if success:
            self._entries.pop(ip, None)
            return
        entry = self._entries.setdefault(ip, _Attempts())
        if entry.locked_until and entry.locked_until <= now:
            entry.count = 0
            entry.locked_until = 0.0
        entry.count += 1
        entry.touched = now
        if entry.count >= self.max_attempts:
            entry.locked_until = now + self.lockout_seconds
            log.warning("admin_login_locked", ip=ip, attempts=entry.count)

    def _evict_stale(self, now: float) -> None:
        cutoff = now - RATE_LIMIT_ENTRY_TTL_SECONDS
        stale = [
            ip
            for ip, e in self._entries.items()
            if e.touched < cutoff and e.locked_until <= now
        ]
        for ip in stale:
            del self._entries[ip]


class AuthService:
    def __init__(self, settings: Settings, repo: AdminRepository) -> None:
        self._settings = settings
        self._repo = repo
        self.limiter = LoginRateLimiter(
            max_attempts=settings.admin_login_max_attempts,
            lockout_seconds=settings.admin_login_lockout_seconds,
        )

    def login(self, password: str, ip: str) -> tuple[dict[str, object], int]:
        """(body, status). Never raises — the caller just serializes the result."""
        if not self.limiter.allowed(ip):
            return (
                {
                    "error": "too_many_attempts",
                    "retry_after": self._settings.admin_login_lockout_seconds,
                },
                429,
            )
        configured = self._settings.admin_password
        if not configured or not hmac.compare_digest(password, configured):
            self.limiter.record(ip, success=False)
            return {"error": "unauthorized"}, 401

        self.limiter.record(ip, success=True)
        token = secrets.token_urlsafe(TOKEN_BYTES)
        expires = expires_at(self._settings.admin_token_ttl_hours)
        self._repo.create_token(
            token_hash(token), expires, utc_now_iso(), self._settings.admin_max_tokens
        )
        log.info("admin_login_ok", ip=ip)
        return {"token": token, "expires": expires}, 200

    def validate(self, token: str | None) -> bool:
        if not token:
            return False
        return self._repo.token_is_valid(token_hash(token), utc_now_iso())
