import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings

ADMIN_COOKIE = "bgm_admin_session"
CUSTOMER_COOKIE = "bgm_customer_session"
CSRF_COOKIE = "bgm_csrf"
SESSION_MAX_AGE = 60 * 60 * 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _serializer(salt: str = "bgm-admin-session") -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt=salt)


def create_admin_session_token(admin_id: UUID) -> str:
    return _serializer().dumps({"admin_id": str(admin_id)})


def read_admin_session_token(token: str) -> UUID:
    try:
        data = _serializer().loads(token, max_age=SESSION_MAX_AGE)
        return UUID(data["admin_id"])
    except (BadSignature, SignatureExpired, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_admin_cookies(response: Response, admin_id: UUID, csrf_token: str) -> None:
    settings = get_settings()
    secure = settings.is_production
    response.set_cookie(
        ADMIN_COOKIE,
        create_admin_session_token(admin_id),
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )


def clear_admin_cookies(response: Response) -> None:
    response.delete_cookie(ADMIN_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def create_customer_session_token(customer_id: UUID) -> str:
    return _serializer("bgm-customer-session").dumps({"customer_id": str(customer_id)})


def read_customer_session_token(token: str) -> UUID:
    try:
        data = _serializer("bgm-customer-session").loads(token, max_age=SESSION_MAX_AGE)
        return UUID(data["customer_id"])
    except (BadSignature, SignatureExpired, KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc


def set_customer_cookies(response: Response, customer_id: UUID, csrf_token: str) -> None:
    settings = get_settings()
    secure = settings.is_production
    response.set_cookie(
        CUSTOMER_COOKIE,
        create_customer_session_token(customer_id),
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        path="/",
    )


def clear_customer_cookies(response: Response) -> None:
    response.delete_cookie(CUSTOMER_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")


def require_csrf(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    cookie = request.cookies.get(CSRF_COOKIE)
    header = request.headers.get("X-CSRF-Token")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def hmac_sign(value: str) -> str:
    return hmac.new(get_settings().secret_key.encode(), value.encode(), "sha256").hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC)


def hold_expiry() -> datetime:
    return utcnow() + timedelta(minutes=get_settings().hold_ttl_minutes)
