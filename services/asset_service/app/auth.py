import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from psycopg.rows import dict_row

from .database import get_connection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-dev-key")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "60"))


def _b64decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)
    return base64.b64decode(data + padding)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        algorithm, iterations, salt, digest = hashed_password.split("$")
    except ValueError as exc:
        raise ValueError("Unexpected password hash format") from exc

    if algorithm != "pbkdf2_sha256":
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    salt_bytes = _b64decode(salt)
    digest_bytes = _b64decode(digest)
    calc_digest = hashlib.pbkdf2_hmac(
        "sha256", plain_password.encode("utf-8"), salt_bytes, int(iterations)
    )
    return hmac.compare_digest(calc_digest, digest_bytes)


def create_access_token(*, user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRATION_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, username, role FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return row


def authenticate_user(username: str, password: str) -> Optional[dict]:
    with get_connection() as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, username, role, password_hash FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            if not row:
                return None
            if not verify_password(password, row["password_hash"]):
                return None
            return {"id": row["id"], "username": row["username"], "role": row["role"]}


def set_rls_user(conn, user_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT set_app_user(%s)", (user_id,))


def clear_rls_user(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.current_user_id', '', true)")
