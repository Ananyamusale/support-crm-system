"""Central configuration. All settings come from environment variables (.env),
so no secret or deployment detail is hard-coded in the source code."""
import os
import secrets

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tickets.db")

# JWT signing key. If none is configured a random one is generated at start-up
# (sessions then end on restart) - never a hard-coded default.
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_urlsafe(64)
JWT_ALGORITHM = "HS256"
TOKEN_MINUTES = int(os.getenv("TOKEN_MINUTES", "30"))

# Set COOKIE_SECURE=true when the site is served over HTTPS (production).
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

# Brute-force protection
MAX_FAILED_LOGINS = int(os.getenv("MAX_FAILED_LOGINS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "15"))

# Comma separated list. Empty = no cross-origin access (same-origin only).
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

ROLES = ("admin", "agent", "customer")
STATUSES = ("Open", "In Progress", "Resolved", "Closed")

# Interactive API docs (/docs) are useful in development but expose the API
# surface, so they are OFF unless explicitly enabled.
ENABLE_DOCS = os.getenv("ENABLE_DOCS", "false").lower() == "true"
