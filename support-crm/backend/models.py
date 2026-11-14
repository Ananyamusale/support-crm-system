from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from database import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(254), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)  # Argon2id hash, never plain text
    role = Column(String(20), nullable=False, default="customer")
    is_active = Column(Boolean, default=True, nullable=False)

    # brute-force protection
    failed_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=now_utc)

    tickets = relationship("Ticket", back_populates="owner")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(20), unique=True, index=True, nullable=False)

    # Ticket belongs to a user: this is what enables object-level authorization
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="tickets")

    customer_name = Column(String(100), nullable=False)
    customer_email = Column(String(254), nullable=False)
    subject = Column(String(150), nullable=False)
    description = Column(String(2000), nullable=False)

    status = Column(String(20), default="Open", nullable=False)
    notes = Column(String(2000), default="")

    created_at = Column(DateTime, default=now_utc)
    updated_at = Column(DateTime, default=now_utc)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=now_utc, index=True)
    username = Column(String(50), index=True)
    action = Column(String(50), index=True)   # e.g. LOGIN_OK, LOGIN_FAIL, TICKET_DELETE
    target = Column(String(100))
    detail = Column(String(300))
    ip_address = Column(String(64))
