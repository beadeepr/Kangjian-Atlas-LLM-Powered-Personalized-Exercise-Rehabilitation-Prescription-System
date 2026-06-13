import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from typing import Any
from binascii import Error as BinasciiError

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "backend" / ".env")

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_EXPIRE_SECONDS = int(os.getenv("JWT_EXPIRE_SECONDS", str(60 * 60 * 24 * 7)))


class AuthError(Exception):
    pass


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def create_access_token(user_id: int, account: str) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "account": account,
        "iat": now,
        "exp": now + JWT_EXPIRE_SECONDS,
    }
    header_part = _base64url_encode(_json_bytes(header))
    payload_part = _base64url_encode(_json_bytes(payload))
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_part}.{payload_part}.{_base64url_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header_part, payload_part, signature_part = token.split(".", 2)
    except ValueError as exc:
        raise AuthError("invalid token") from exc

    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    expected_signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    try:
        actual_signature = _base64url_decode(signature_part)
    except (ValueError, BinasciiError) as exc:
        raise AuthError("invalid token signature") from exc
    if not hmac.compare_digest(actual_signature, expected_signature):
        raise AuthError("invalid token signature")

    try:
        payload = json.loads(_base64url_decode(payload_part).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, BinasciiError) as exc:
        raise AuthError("invalid token payload") from exc

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        raise AuthError("token expired")
    return payload
