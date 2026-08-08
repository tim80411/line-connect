"""Auth internals: token lifetime, token cap, lockout expiry."""

from pathlib import Path
from typing import Any

from line_connect.admin.auth import AuthService, LoginRateLimiter, token_hash
from line_connect.admin.repository import AdminRepository
from line_connect.storage.db import Database, utc_now_iso


def make_auth(db: Database, tmp_path: Path, **overrides: Any) -> AuthService:
    from tests.integration.conftest import make_settings

    opts: dict[str, Any] = {"admin_password": "pw"}
    opts.update(overrides)
    return AuthService(make_settings(tmp_path, **opts), AdminRepository(db))


class TestLogin:
    def test_correct_password_issues_token(self, db: Database, tmp_path: Path) -> None:
        auth = make_auth(db, tmp_path)
        body, status = auth.login("pw", "1.2.3.4")
        assert status == 200
        assert auth.validate(str(body["token"])) is True

    def test_wrong_password_rejected(self, db: Database, tmp_path: Path) -> None:
        auth = make_auth(db, tmp_path)
        assert auth.login("nope", "1.2.3.4")[1] == 401

    def test_empty_configured_password_never_authenticates(
        self, db: Database, tmp_path: Path
    ) -> None:
        """Belt and braces: the routes are not mounted in this case anyway, but
        an empty password must not make an empty submission succeed."""
        auth = make_auth(db, tmp_path, admin_password="")
        assert auth.login("", "1.2.3.4")[1] == 401

    def test_only_the_stored_hash_hits_the_database(
        self, db: Database, tmp_path: Path
    ) -> None:
        auth = make_auth(db, tmp_path)
        token = str(auth.login("pw", "1.2.3.4")[0]["token"])
        with db.locked() as conn:
            stored = [r["token_hash"] for r in conn.execute("SELECT * FROM admin_tokens")]
        assert stored == [token_hash(token)]
        assert token not in stored


class TestTokenValidation:
    def test_blank_and_unknown_tokens(self, db: Database, tmp_path: Path) -> None:
        auth = make_auth(db, tmp_path)
        assert auth.validate(None) is False
        assert auth.validate("") is False
        assert auth.validate("made-up") is False

    def test_expired_token_rejected(self, db: Database, tmp_path: Path) -> None:
        auth = make_auth(db, tmp_path)
        token = str(auth.login("pw", "1.2.3.4")[0]["token"])
        with db.locked() as conn:
            conn.execute("UPDATE admin_tokens SET expires_at = '2000-01-01T00:00:00.000Z'")
        assert auth.validate(token) is False

    def test_token_count_is_capped(self, db: Database, tmp_path: Path) -> None:
        auth = make_auth(db, tmp_path, admin_max_tokens=3)
        tokens = [str(auth.login("pw", "1.2.3.4")[0]["token"]) for _ in range(5)]
        with db.locked() as conn:
            count = conn.execute("SELECT COUNT(*) FROM admin_tokens").fetchone()[0]
        assert count == 3
        assert auth.validate(tokens[-1]) is True
        assert auth.validate(tokens[0]) is False

    def test_expired_tokens_are_swept_on_login(
        self, db: Database, tmp_path: Path
    ) -> None:
        repo = AdminRepository(db)
        repo.create_token("stale", "2000-01-01T00:00:00.000Z", utc_now_iso(), 10)
        auth = make_auth(db, tmp_path)
        auth.login("pw", "1.2.3.4")
        with db.locked() as conn:
            hashes = {r["token_hash"] for r in conn.execute("SELECT * FROM admin_tokens")}
        assert "stale" not in hashes


class TestRateLimiter:
    def test_locks_after_max_attempts(self) -> None:
        limiter = LoginRateLimiter(max_attempts=3, lockout_seconds=300)
        for _ in range(2):
            limiter.record("ip", success=False)
            assert limiter.allowed("ip") is True
        limiter.record("ip", success=False)
        assert limiter.allowed("ip") is False

    def test_lockout_expires(self) -> None:
        limiter = LoginRateLimiter(max_attempts=1, lockout_seconds=0)
        limiter.record("ip", success=False)
        assert limiter.allowed("ip") is True  # zero-second lockout already elapsed

    def test_ips_are_independent(self) -> None:
        limiter = LoginRateLimiter(max_attempts=1, lockout_seconds=300)
        limiter.record("attacker", success=False)
        assert limiter.allowed("attacker") is False
        assert limiter.allowed("bystander") is True

    def test_success_clears_the_tally(self) -> None:
        limiter = LoginRateLimiter(max_attempts=2, lockout_seconds=300)
        limiter.record("ip", success=False)
        limiter.record("ip", success=True)
        limiter.record("ip", success=False)
        assert limiter.allowed("ip") is True
