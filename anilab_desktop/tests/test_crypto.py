"""Unit tests for iw3/r21 wire encryption and AniMeloTransport."""

from __future__ import annotations

import httpx
import pytest

from anilab_desktop.api.crypto import (
    MAX_DECOMPRESSED_BYTES,
    WireCrypto,
    canonical_request,
    is_valid_nonce,
)
from anilab_desktop.api.transport import AniMeloTransport


_TEST_SECRET = b"unit-test-wire-secret-32-bytes!!"


def test_nonce_validation() -> None:
    nonce = WireCrypto.generate_nonce()
    assert len(nonce) == 32
    assert is_valid_nonce(nonce)
    assert not is_valid_nonce("not-hex")
    assert not is_valid_nonce(nonce.upper())


def test_x_seal_round_trip() -> None:
    crypto = WireCrypto(_TEST_SECRET)
    nonce = WireCrypto.generate_nonce()
    canonical = canonical_request("GET", "/api/me", "before=10")

    seal = crypto.encrypt_seal("secret-jwt-token", nonce, canonical)
    assert crypto.decrypt_seal(seal, nonce, canonical) == "secret-jwt-token"

    with pytest.raises(Exception):
        crypto.decrypt_seal(seal, nonce, canonical_request("POST", "/api/me", "before=10"))


def test_request_body_round_trip() -> None:
    crypto = WireCrypto(_TEST_SECRET)
    nonce = WireCrypto.generate_nonce()
    canonical = canonical_request("POST", "/api/continue-watching", "")
    payload = b'{"ids":[1,2,3]}'

    encrypted = crypto.encrypt_request_body(payload, "application/json", nonce, canonical)
    ct, decrypted = crypto.decrypt_request_body(encrypted, nonce, canonical)
    assert ct == "application/json"
    assert decrypted == payload


@pytest.mark.parametrize("gzip_compress", [False, True])
def test_response_body_round_trip(gzip_compress: bool) -> None:
    crypto = WireCrypto(_TEST_SECRET)
    req_nonce = WireCrypto.generate_nonce()
    resp_nonce = WireCrypto.generate_nonce()
    payload = b'{"ok":true,"items":[1,2,3,4,5]}' * 10

    encrypted = crypto.encrypt_response_body(
        payload,
        "application/json; charset=utf-8",
        resp_nonce,
        req_nonce,
        gzip_compress=gzip_compress,
    )
    decoded = crypto.decrypt_response_body(encrypted, resp_nonce, req_nonce)
    assert decoded.content_type == "application/json; charset=utf-8"
    assert decoded.body == payload


def test_transport_end_to_end_mock() -> None:
    crypto = WireCrypto(_TEST_SECRET)
    captured_headers: dict[str, str] = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_headers
        captured_headers = dict(request.headers)
        assert "authorization" not in {k.lower() for k in request.headers}
        req_nonce = request.headers["X-Nonce"]
        canonical = canonical_request(
            request.method,
            request.url.path,
            request.url.query.decode("ascii") if request.url.query else "",
        )
        assert crypto.decrypt_seal(request.headers["X-Seal"], req_nonce, canonical) == "my-token"

        ct, body = crypto.decrypt_request_body(request.content, req_nonce, canonical)
        assert ct == "application/json"
        assert body == b'{"hello":"world"}'

        resp_nonce = WireCrypto.generate_nonce()
        enc_resp = crypto.encrypt_response_body(
            b'{"status":"ok"}',
            "application/json",
            resp_nonce,
            req_nonce,
            gzip_compress=True,
        )
        return httpx.Response(200, headers={"X-Nonce": resp_nonce}, content=enc_resp)

    transport = AniMeloTransport(
        inner=httpx.MockTransport(mock_handler),
        crypto=crypto,
        token_provider=lambda: "my-token",
        timezone_provider=lambda: "Asia/Kolkata",
    )
    with httpx.Client(transport=transport, base_url="https://example.test/api/") as client:
        resp = client.post("test?foo=bar", content=b'{"hello":"world"}', headers={"Content-Type": "application/json"})

    assert resp.status_code == 200
    assert resp.headers["Content-Type"] == "application/json"
    assert resp.json() == {"status": "ok"}
    assert captured_headers["x-app-version-code"] == "4"
    assert captured_headers["x-time-zone"] == "Asia/Kolkata"
