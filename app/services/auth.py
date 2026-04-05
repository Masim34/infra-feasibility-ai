"""
app/services/auth.py
Production-grade authentication service with bcrypt password hashing,
JWT tokens, API key generation, and user management.
"""
import os
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional

import jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session

from app.db.models import User, get_db

# ─── Config ────────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production-use-256bit-random-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", 1440))  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
http_bearer = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ─── Password utilities ────────────────────────────────────────────────────────

def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_api_key() -> str:
    """Generate a cryptographically secure API key (64 hex chars = 256 bits)."""
    return secrets.token_hex(32)


# ─── JWT token utilities ──────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a long-lived refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── User management ──────────────────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter(User.username == username.lower()).first()


def get_user_by_api_key(db: Session, api_key: str) -> Optional[User]:
    return db.query(User).filter(User.api_key == api_key).first()


def create_user(
    db: Session,
    email: str,
    username: str,
    password: str,
    full_name: Optional[str] = None,
    company: Optional[str] = None,
    plan: str = "free",
) -> User:
    """Register a new user with hashed password and API key."""
    # Check for duplicates
    if get_user_by_email(db, email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Email '{email}' is already registered",
        )
    if get_user_by_username(db, username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{username}' is already taken",
        )

    user = User(
        email=email.lower(),
        username=username.lower(),
        hashed_password=hash_password(password),
        full_name=full_name,
        company=company,
        plan=plan,
        api_key=generate_api_key(),
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username_or_email: str, password: str) -> User:
    """Authenticate a user by username or email + password."""
    # Try email first, then username
    user = get_user_by_email(db, username_or_email)
    if not user:
        user = get_user_by_username(db, username_or_email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    return user


def rotate_api_key(db: Session, user: User) -> str:
    """Rotate the user's API key. Returns the new key."""
    new_key = generate_api_key()
    user.api_key = new_key
    db.commit()
    return new_key


# ─── FastAPI dependencies ──────────────────────────────────────────────────────

def get_current_user_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency: validate JWT Bearer token, return User."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - provide Bearer token or X-API-Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def get_current_user_api_key(
    api_key: Optional[str] = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """FastAPI dependency: validate X-API-Key header, return User."""
    if not api_key:
        return None
    user = get_user_by_api_key(db, api_key)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    return user


def get_current_user(
    jwt_user: Optional[User] = Depends(get_current_user_jwt),
    api_key_user: Optional[User] = Depends(get_current_user_api_key),
) -> User:
    """
    Unified auth dependency: accepts JWT Bearer token OR X-API-Key header.
    JWT takes precedence if both are provided.
    """
    user = jwt_user or api_key_user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required: provide Bearer token or X-API-Key",
        )
    return user


# ─── Plan-based rate limiting helpers ─────────────────────────────────────────

PLAN_LIMITS = {
    "free":       {"analyses_per_day": 5,   "max_projects": 3,   "monte_carlo": False},
    "pro":        {"analyses_per_day": 50,  "max_projects": 25,  "monte_carlo": True},
    "enterprise": {"analyses_per_day": 999, "max_projects": 999, "monte_carlo": True},
}


def check_plan_feature(user: User, feature: str) -> bool:
    """Check if user's plan includes a given feature."""
    limits = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])
    return bool(limits.get(feature, False))


def require_plan_feature(feature: str):
    """FastAPI dependency factory: raise 403 if user's plan lacks the feature."""
    def _check(user: User = Depends(get_current_user)):
        if not check_plan_feature(user, feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature}' requires a higher plan. Upgrade at /billing.",
            )
        return user
    return _check
