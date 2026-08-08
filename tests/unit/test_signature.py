from line_connect.line.signature import compute_signature, verify_signature

SECRET = "test-secret"


def test_valid_signature_passes() -> None:
    body = b'{"events": []}'
    sig = compute_signature(SECRET, body)
    assert verify_signature(SECRET, body, sig)


def test_tampered_body_fails() -> None:
    sig = compute_signature(SECRET, b'{"events": []}')
    assert not verify_signature(SECRET, b'{"events": [1]}', sig)


def test_wrong_secret_fails() -> None:
    body = b'{"events": []}'
    sig = compute_signature("other-secret", body)
    assert not verify_signature(SECRET, body, sig)


def test_missing_signature_fails() -> None:
    assert not verify_signature(SECRET, b"{}", None)
    assert not verify_signature(SECRET, b"{}", "")


def test_garbage_signature_does_not_crash() -> None:
    assert not verify_signature(SECRET, b"{}", "not base64 at all !!!")


def test_non_ascii_body() -> None:
    body = '{"text": "你好 🎌"}'.encode()
    sig = compute_signature(SECRET, body)
    assert verify_signature(SECRET, body, sig)
