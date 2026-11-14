import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


Status = Literal["Open", "In Progress", "Resolved", "Closed"]
Role = Literal["admin", "agent", "customer"]


def _clean(value: str) -> str:
    """Trim whitespace and reject control characters (null bytes, etc.)."""
    value = value.strip()
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", value):
        raise ValueError("Invalid characters")
    return value


# ---------- Users ----------
class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, v):
        return _clean(v)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v):
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("Password must contain letters and digits")
        return v


class UserLogin(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    full_name: str
    email: str
    role: Role
    is_active: bool


class RoleUpdate(BaseModel):
    role: Role


class ActiveUpdate(BaseModel):
    is_active: bool


# ---------- Tickets ----------
class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=5, max_length=2000)

    @field_validator("subject", "description")
    @classmethod
    def clean_text(cls, v):
        return _clean(v)


class TicketUpdate(BaseModel):
    status: Status
    notes: Optional[str] = Field(default="", max_length=2000)

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, v):
        return _clean(v or "")


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ticket_id: str
    customer_name: str
    customer_email: str
    subject: str
    description: str
    status: str
    notes: Optional[str] = ""
    created_at: datetime
    updated_at: datetime


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    timestamp: datetime
    username: Optional[str]
    action: str
    target: Optional[str]
    detail: Optional[str]
    ip_address: Optional[str]
