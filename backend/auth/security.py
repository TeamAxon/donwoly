import os
import uuid
import base64
import hashlib
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from jwt import InvalidTokenError


JWT_ALGORITHM = "HS256"


def _bcrypt_input(password: str) -> bytes:
    # bcrypt accepts at most 72 bytes. SHA-256 preserves support for longer valid passwords.
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_input(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(_bcrypt_input(password), password_hash.encode("utf-8"))


def _jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET environment variable is required")
    return secret


def _create_token(user_id: uuid.UUID, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    return _create_token(user_id, "access", timedelta(minutes=minutes))


def create_refresh_token(user_id: uuid.UUID) -> str:
    days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))
    return _create_token(user_id, "refresh", timedelta(days=days))


def decode_access_token(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise InvalidTokenError("token is not an access token")
        return uuid.UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid access token") from exc
