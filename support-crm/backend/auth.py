"""Authentication, session handling, CSRF protection and role-based access control."""
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

import config
from database import SessionLocal
from models import AuditLog, User

ph = PasswordHasher()  # Argon2id with safe defaults

# Used to keep response time similar when the username does not exist
_DUMMY_HASH = ph.hash("dummy-password-for-timing")

COOKIE_NAME = "access_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- passwords ----------
def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def fake_verify() -> None:
    verify_password("wrong", _DUMMY_HASH)


# ---------- tokens ----------
def create_token(user: User) -> tuple[str, str]:
    """Returns (jwt, csrf_token). The CSRF token is bound inside the JWT."""
    csrf = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=config.TOKEN_MINUTES)
    payload = {"sub": str(user.id), "role": user.role, "csrf": csrf, "exp": expires}
    return jwt.encode(payload, config.SECRET_KEY, algorithm=config.JWT_ALGORITHM), csrf


def decode_token(token: str) -> dict:
    return jwt.decode(token, config.SECRET_KEY, algorithms=[config.JWT_ALGORITHM])


# ---------- audit log ----------
def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def audit(db: Session, request: Request, action: str, username: str | None = None,
          target: str | None = None, detail: str | None = None) -> None:
    db.add(AuditLog(username=username, action=action, target=target,
                    detail=(detail or "")[:300], ip_address=client_ip(request)))
    db.commit()


# ---------- dependencies ----------
def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # CSRF: state-changing requests must echo the token bound to this session
    if request.method not in SAFE_METHODS:
        header = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(header, str(payload.get("csrf", ""))):
            raise HTTPException(status_code=403, detail="CSRF token missing or invalid")

    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account unavailable")
    return user


def require_roles(*roles: str):
    """Server-side role check. The role is read from the database, not from the token."""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission")
        return user
    return checker
