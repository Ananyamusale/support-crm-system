import logging
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import config
import models
from auth import (COOKIE_NAME, audit, create_token, decode_token, fake_verify, get_current_user,
                  get_db, hash_password, require_roles, verify_password)
from database import engine
from models import AuditLog, Ticket, User, now_utc
from schemas import (ActiveUpdate, AuditOut, RoleUpdate, TicketCreate, TicketOut, TicketUpdate,
                     UserLogin, UserOut, UserRegister)
from security import SecurityHeadersMiddleware, login_limiter, register_limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("support-crm")

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Support CRM (Secure)",
    docs_url="/docs" if config.ENABLE_DOCS else None,
    redoc_url=None,
    openapi_url="/openapi.json" if config.ENABLE_DOCS else None,
)

app.add_middleware(SecurityHeadersMiddleware)

# CORS is closed by default (same-origin app). Only origins listed in .env are allowed.
if config.ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    """Never leak stack traces or internals to the client."""
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# =====================================================================
# AUTHENTICATION
# =====================================================================
@app.post("/api/auth/register", response_model=UserOut, status_code=201)
def register(data: UserRegister, request: Request, db: Session = Depends(get_db)):
    register_limiter.check(request.client.host if request.client else "unknown")
    # Public registration ALWAYS creates a customer. Roles can only be raised by an admin.
    user = User(
        username=data.username,
        full_name=data.full_name,
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        role="customer",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Generic message: do not reveal which field already exists
        raise HTTPException(status_code=409, detail="Username or email is already registered")
    db.refresh(user)
    audit(db, request, "REGISTER", user.username)
    return user


@app.post("/api/auth/login")
def login(data: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    login_limiter.check(request.client.host if request.client else "unknown")
    user = db.query(User).filter(User.username == data.username).first()

    if not user:
        fake_verify()  # keep timing similar so usernames cannot be enumerated
        audit(db, request, "LOGIN_FAIL", data.username[:50], detail="unknown user")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    now = now_utc()
    if user.locked_until and user.locked_until > now:
        audit(db, request, "LOGIN_BLOCKED", user.username, detail="account locked")
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again later.")

    if not user.is_active or not verify_password(data.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= config.MAX_FAILED_LOGINS:
            user.locked_until = now + timedelta(minutes=config.LOCKOUT_MINUTES)
            user.failed_attempts = 0
            audit(db, request, "ACCOUNT_LOCKED", user.username)
        db.commit()
        audit(db, request, "LOGIN_FAIL", user.username, detail="bad password")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user.failed_attempts = 0
    user.locked_until = None
    db.commit()

    token, csrf = create_token(user)
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True,                      # JavaScript cannot read the session cookie (XSS)
        secure=config.COOKIE_SECURE,        # HTTPS only in production
        samesite="strict",                  # not sent on cross-site requests (CSRF)
        max_age=config.TOKEN_MINUTES * 60,
        path="/",
    )
    audit(db, request, "LOGIN_OK", user.username)
    return {"user": UserOut.model_validate(user), "csrf_token": csrf}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    response.delete_cookie(COOKIE_NAME, path="/")
    audit(db, request, "LOGOUT", user.username)
    return {"success": True}


@app.get("/api/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@app.get("/api/auth/csrf")
def csrf_token(request: Request, user: User = Depends(get_current_user)):
    """Gives the page its CSRF token (e.g. after opening a new tab).
    Same-origin policy stops other sites from reading this response."""
    return {"csrf_token": decode_token(request.cookies[COOKIE_NAME])["csrf"]}


# =====================================================================
# TICKETS (CRUD) - with role and object-level authorization
# =====================================================================
def _new_ticket_id(db: Session) -> str:
    # Cryptographically random, not guessable (replaces random.randint)
    for _ in range(5):
        tid = f"TKT-{secrets.token_hex(4).upper()}"
        if not db.query(Ticket).filter(Ticket.ticket_id == tid).first():
            return tid
    raise HTTPException(status_code=500, detail="Could not allocate ticket id")


def _load_ticket(db: Session, ticket_id: str, user: User) -> Ticket:
    """Fetch a ticket and enforce object-level access (prevents IDOR).
    Customers only ever see their own tickets; a foreign ticket looks like 'not found'."""
    ticket = db.query(Ticket).filter(Ticket.ticket_id == ticket_id).first()
    if not ticket or (user.role == "customer" and ticket.owner_id != user.id):
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


# CREATE - any logged-in user
@app.post("/api/tickets", status_code=201)
def create_ticket(data: TicketCreate, request: Request, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    ticket = Ticket(
        ticket_id=_new_ticket_id(db),
        owner_id=user.id,
        customer_name=user.full_name,      # taken from the account, cannot be spoofed
        customer_email=user.email,
        subject=data.subject,
        description=data.description,
        status="Open",
        notes="",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    audit(db, request, "TICKET_CREATE", user.username, ticket.ticket_id)
    return {"ticket_id": ticket.ticket_id, "created_at": ticket.created_at}


# READ (list) - customers: own tickets; agents/admins: all
@app.get("/api/tickets", response_model=list[TicketOut])
def list_tickets(status: str | None = None, search: str | None = None,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Ticket)
    if user.role == "customer":
        query = query.filter(Ticket.owner_id == user.id)

    if status:
        if status not in config.STATUSES:
            raise HTTPException(status_code=422, detail="Invalid status filter")
        query = query.filter(Ticket.status == status)

    if search:
        search = search.strip()[:100]
        # autoescape=True treats % and _ literally; the value is always a bound parameter
        query = query.filter(
            Ticket.subject.contains(search, autoescape=True)
            | Ticket.description.contains(search, autoescape=True)
            | Ticket.ticket_id.contains(search, autoescape=True)
            | Ticket.customer_name.contains(search, autoescape=True)
        )
    return query.order_by(Ticket.created_at.desc()).limit(500).all()


# READ (single)
@app.get("/api/tickets/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _load_ticket(db, ticket_id, user)


# UPDATE - agents and admins only
@app.put("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: str, data: TicketUpdate, request: Request,
                  user: User = Depends(require_roles("agent", "admin")),
                  db: Session = Depends(get_db)):
    ticket = _load_ticket(db, ticket_id, user)
    ticket.status = data.status
    ticket.notes = data.notes
    ticket.updated_at = now_utc()
    db.commit()
    audit(db, request, "TICKET_UPDATE", user.username, ticket.ticket_id, f"status={data.status}")
    return {"success": True, "updated_at": ticket.updated_at}


# DELETE - admins only
@app.delete("/api/tickets/{ticket_id}")
def delete_ticket(ticket_id: str, request: Request, user: User = Depends(require_roles("admin")),
                  db: Session = Depends(get_db)):
    ticket = _load_ticket(db, ticket_id, user)
    db.delete(ticket)
    db.commit()
    audit(db, request, "TICKET_DELETE", user.username, ticket_id)
    return {"success": True, "message": "Ticket deleted"}


# =====================================================================
# ADMIN
# =====================================================================
@app.get("/api/admin/users", response_model=list[UserOut])
def list_users(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id).all()


@app.put("/api/admin/users/{user_id}/role", response_model=UserOut)
def set_role(user_id: int, data: RoleUpdate, request: Request,
             admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    target.role = data.role
    db.commit()
    audit(db, request, "ROLE_CHANGE", admin.username, target.username, f"new role={data.role}")
    return target


@app.put("/api/admin/users/{user_id}/active", response_model=UserOut)
def set_active(user_id: int, data: ActiveUpdate, request: Request,
               admin: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate yourself")
    target.is_active = data.is_active
    db.commit()
    audit(db, request, "USER_ACTIVE_CHANGE", admin.username, target.username, f"active={data.is_active}")
    return target


@app.get("/api/admin/audit", response_model=list[AuditOut])
def audit_log(user: User = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(200).all()


# =====================================================================
# FRONT END (served from the same origin, so no CORS is needed)
# =====================================================================
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND.exists():
    app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
