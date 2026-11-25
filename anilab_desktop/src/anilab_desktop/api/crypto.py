"""Wire-encryption primitives matching defpackage/iw3.java and defpackage/r21.java."""

from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import io
import os
import re
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DEFAULT_WIRE_SECRET: bytes = os.environ.get("ANILAB_WIRE_SECRET", "").encode("utf-8")
MAX_DECOMPRESSED_BYTES: int = 33_554_432  # 32 MiB cap
_NONCE_RE = re.compile(r"^[0-9a-f]{32}$")


def is_valid_nonce(nonce: str | None) -> bool:
    """Return True if nonce is a 32-char lowercase hex string."""
    return bool(nonce and _NONCE_RE.fullmatch(nonce))


def canonical_request(method: str, path: str, query: str = "") -> str:
    """Build the canonical request string used as AAD in r21.java.

    Format: ``<UPPERCASE_METHOD>\\n/<path_without_leading_slash>\\n<raw_query>``
    """
    norm_path = path if path.startswith("/") else f"/{path}"
    return f"{method.upper()}\n{norm_path}\n{query}"


def _gunzip_capped(data: bytes, max_bytes: int = MAX_DECOMPRESSED_BYTES) -> bytes:
    """Decompress gzipped payload while enforcing the 32 MiB output cap."""
    out = bytearray()
    with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as gz:
        while True:
            chunk = gz.read(16_384)
            if not chunk:
                break
            if len(out) + len(chunk) > max_bytes:
                raise ValueError(
                    f"Decompressed payload exceeds {max_bytes} byte limit"
                )
            out.extend(chunk)
    return bytes(out)


@dataclass(frozen=True)
class DecryptedResponse:
    """Decoded response payload and restored Content-Type."""

    content_type: str
    body: bytes


class WireCrypto:
    """Implements iw3 HMAC-SHA256 key/IV derivation and AES-256-GCM framing."""

    def __init__(self, secret: bytes | None = None) -> None:
        resolved = secret if secret is not None else os.environ.get("ANILAB_WIRE_SECRET", "").encode("utf-8")
        if not resolved:
            raise ValueError(
                "Wire secret is not set. Provide secret=... or set ANILAB_WIRE_SECRET."
            )
        self._secret = resolved

    @staticmethod
    def generate_nonce() -> str:
        """Generate a 16-byte random hex nonce (32 lowercase hex chars)."""
        return os.urandom(16).hex()

    def _hmac(self, label: str) -> bytes:
        return hmac.new(
            self._secret, label.encode("utf-8"), hashlib.sha256
        ).digest()

    def derive_key_iv(self, nonce: str, prefix: str = "") -> tuple[bytes, bytes]:
        """Derive a 32-byte AES key and 12-byte GCM IV from nonce and prefix."""
        key = self._hmac(f"{prefix}key{nonce}")
        iv = self._hmac(f"{prefix}iv{nonce}")[:12]
        return key, iv

    def encrypt_seal(self, token: str, nonce: str, canonical: str) -> str:
        """Encrypt the bearer token into the Base64 X-Seal header value."""
        key, iv = self.derive_key_iv(nonce, prefix="h")
        aad = f"h\n{canonical}".encode("utf-8")
        ct = AESGCM(key).encrypt(iv, token.encode("utf-8"), aad)
        return base64.b64encode(ct).decode("ascii")

    def decrypt_seal(self, seal_b64: str, nonce: str, canonical: str) -> str:
        """Decrypt an X-Seal header value (primarily for testing)."""
        key, iv = self.derive_key_iv(nonce, prefix="h")
        aad = f"h\n{canonical}".encode("utf-8")
        ct = base64.b64decode(seal_b64)
        return AESGCM(key).decrypt(iv, ct, aad).decode("utf-8")

    def encrypt_request_body(
        self,
        body: bytes,
        content_type: str | None,
        nonce: str,
        canonical: str,
    ) -> bytes:
        """Frame and encrypt a non-empty request body with [0x00][ctLen][ct][body]."""
        ct_str = content_type or "application/octet-stream"
        ct_bytes = ct_str.encode("utf-8")
        if len(ct_bytes) > 255:
            raise ValueError("The content type is too long (> 255 bytes)")

        frame = bytes((0, len(ct_bytes))) + ct_bytes + body
        key, iv = self.derive_key_iv(nonce, prefix="")
        aad = f"q\n{canonical}".encode("utf-8")
        return AESGCM(key).encrypt(iv, frame, aad)

    def decrypt_request_body(
        self,
        encrypted: bytes,
        nonce: str,
        canonical: str,
    ) -> tuple[str, bytes]:
        """Decrypt a framed request body (primarily for testing)."""
        key, iv = self.derive_key_iv(nonce, prefix="")
        aad = f"q\n{canonical}".encode("utf-8")
        frame = AESGCM(key).decrypt(iv, encrypted, aad)
        if len(frame) < 2:
            raise ValueError("Request frame too short")
        ct_len = frame[1]
        if len(frame) < 2 + ct_len:
            raise ValueError("Truncated content-type in request frame")
        ct_str = frame[2 : 2 + ct_len].decode("utf-8")
        return ct_str, frame[2 + ct_len :]

    def encrypt_response_body(
        self,
        body: bytes,
        content_type: str,
        response_nonce: str,
        request_nonce: str,
        *,
        gzip_compress: bool = False,
    ) -> bytes:
        """Frame and encrypt a response body (primarily for testing)."""
        ct_bytes = content_type.encode("utf-8")
        if len(ct_bytes) > 255:
            raise ValueError("The content type is too long (> 255 bytes)")
        flags = 1 if gzip_compress else 0
        payload = gzip.compress(body) if gzip_compress else body
        frame = bytes((flags, len(ct_bytes))) + ct_bytes + payload
        key, iv = self.derive_key_iv(response_nonce, prefix="")
        aad = f"s\n{request_nonce}".encode("utf-8")
        return AESGCM(key).encrypt(iv, frame, aad)

    def decrypt_response_body(
        self,
        encrypted: bytes,
        response_nonce: str,
        request_nonce: str,
    ) -> DecryptedResponse:
        """Decrypt a response body, gunzipping if (flags & 1) != 0."""
        if not is_valid_nonce(response_nonce) or len(encrypted) < 18:
            raise ValueError("Invalid response nonce or ciphertext too short")
        key, iv = self.derive_key_iv(response_nonce, prefix="")
        aad = f"s\n{request_nonce}".encode("utf-8")
        frame = AESGCM(key).decrypt(iv, encrypted, aad)
        if len(frame) < 2:
            raise ValueError("Decrypted response frame too short")
        flags = frame[0]
        ct_len = frame[1]
        header_end = 2 + ct_len
        if len(frame) < header_end:
            raise ValueError("Truncated content-type in response frame")
        content_type = frame[2:header_end].decode("utf-8")
        payload = frame[header_end:]
        if (flags & 1) != 0:
            payload = _gunzip_capped(payload, MAX_DECOMPRESSED_BYTES)
        return DecryptedResponse(content_type=content_type, body=payload)
