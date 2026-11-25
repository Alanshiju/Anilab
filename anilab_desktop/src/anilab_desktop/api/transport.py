"""HTTP transport implementing defpackage/ig.java + defpackage/r21.java."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import os

import httpx

from .crypto import WireCrypto, canonical_request, is_valid_nonce

BASE_URL = os.environ.get("ANILAB_API_BASE_URL", "")
APP_VERSION_CODE = os.environ.get("ANILAB_APP_VERSION_CODE", "4")
APP_ID = os.environ.get("ANILAB_APP_ID", "com.example.mediacatalog")


def _device_timezone() -> str | None:
    """Return an ASCII 33..126 timezone identifier if available."""
    try:
        tz = datetime.now().astimezone().tzinfo
        tz_name = getattr(tz, "key", None) or str(tz)
    except Exception:
        return None
    if not tz_name or not tz_name.strip():
        return None
    if all(33 <= ord(ch) <= 126 for ch in tz_name):
        return tz_name
    return None


def _extract_bearer_token(auth_header: str | None) -> str:
    if not auth_header:
        return ""
    if auth_header.startswith("Bearer "):
        return auth_header[len("Bearer ") :].strip()
    return auth_header.strip()


class AniMeloTransport(httpx.BaseTransport):
    """httpx transport mirroring ig (headers) + r21 (EncryptedBody)."""

    def __init__(
        self,
        inner: httpx.BaseTransport | None = None,
        *,
        crypto: WireCrypto | None = None,
        token_provider: Callable[[], str | None] | None = None,
        timezone_provider: Callable[[], str | None] | None = None,
    ) -> None:
        self._inner = inner or httpx.HTTPTransport()
        if crypto is not None:
            self._crypto: WireCrypto | None = crypto
        elif os.environ.get("ANILAB_WIRE_SECRET"):
            self._crypto = WireCrypto()
        else:
            self._crypto = None
        self._token_provider = token_provider
        self._timezone_provider = timezone_provider or _device_timezone

    def _prepare_request(self, request: httpx.Request) -> tuple[httpx.Request, str]:
        headers = httpx.Headers(request.headers)
        headers["Accept"] = "application/json"
        headers["X-App-Version-Code"] = APP_VERSION_CODE
        headers["X-App-Id"] = APP_ID

        tz = self._timezone_provider()
        if tz:
            headers["X-Time-Zone"] = tz

        if "Authorization" not in headers and self._token_provider is not None:
            token = self._token_provider()
            if token:
                headers["Authorization"] = f"Bearer {token}"

        raw_token = _extract_bearer_token(headers.get("Authorization"))
        if self._crypto is None:
            if body:
                return (
                    httpx.Request(
                        method=request.method,
                        url=request.url,
                        headers=headers,
                        content=body,
                    ),
                    "",
                )
            return (
                httpx.Request(
                    method=request.method,
                    url=request.url,
                    headers=headers,
                ),
                "",
            )

        headers.pop("Authorization", None)

        nonce = self._crypto.generate_nonce()
        query_str = request.url.query.decode("ascii") if request.url.query else ""
        canonical = canonical_request(request.method, request.url.path, query_str)

        headers["X-Nonce"] = nonce
        headers["X-Seal"] = self._crypto.encrypt_seal(raw_token, nonce, canonical)

        body = request.content
        if body:
            orig_ct = headers.get("Content-Type")
            encrypted_body = self._crypto.encrypt_request_body(
                body, orig_ct, nonce, canonical
            )
            headers["Content-Type"] = "application/octet-stream"
            headers["Content-Length"] = str(len(encrypted_body))
            new_req = httpx.Request(
                method=request.method,
                url=request.url,
                headers=headers,
                content=encrypted_body,
            )
        else:
            new_req = httpx.Request(
                method=request.method,
                url=request.url,
                headers=headers,
            )
        return new_req, nonce

    def _decode_response(
        self, response: httpx.Response, request_nonce: str
    ) -> httpx.Response:
        raw_body = response.read()
        if self._crypto is None:
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=raw_body,
            )
        resp_nonce = response.headers.get("X-Nonce")

        if resp_nonce is None:
            if not raw_body:
                return httpx.Response(
                    status_code=response.status_code,
                    headers=response.headers,
                    content=raw_body,
                )
            if 200 <= response.status_code < 300:
                headers = httpx.Headers(response.headers)
                headers.pop("X-Nonce", None)
                headers.pop("Content-Length", None)
                headers["Content-Type"] = "text/plain"
                return httpx.Response(
                    status_code=502,
                    headers=headers,
                    content=b"unreadable answer",
                )
            headers = httpx.Headers(response.headers)
            headers.pop("Content-Length", None)
            return httpx.Response(
                status_code=response.status_code,
                headers=headers,
                content=b"",
            )

        if not is_valid_nonce(resp_nonce):
            return self._unreadable_answer(response)

        try:
            decoded = self._crypto.decrypt_response_body(
                raw_body, resp_nonce, request_nonce
            )
        except Exception:
            return self._unreadable_answer(response)

        headers = httpx.Headers(response.headers)
        headers.pop("X-Nonce", None)
        headers.pop("Content-Length", None)
        headers["Content-Type"] = decoded.content_type
        return httpx.Response(
            status_code=response.status_code,
            headers=headers,
            content=decoded.body,
        )

    @staticmethod
    def _unreadable_answer(response: httpx.Response) -> httpx.Response:
        headers = httpx.Headers(response.headers)
        headers.pop("X-Nonce", None)
        headers.pop("Content-Length", None)
        headers["Content-Type"] = "text/plain"
        status = 502 if 200 <= response.status_code < 300 else response.status_code
        return httpx.Response(
            status_code=status,
            headers=headers,
            content=b"unreadable answer",
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        prepared, req_nonce = self._prepare_request(request)
        response = self._inner.handle_request(prepared)
        return self._decode_response(response, req_nonce)

    def close(self) -> None:
        self._inner.close()
