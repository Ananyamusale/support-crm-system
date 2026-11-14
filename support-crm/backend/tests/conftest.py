import os
import sys
import tempfile
from pathlib import Path

# Use a throw-away database and a fixed test key BEFORE the app is imported
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-test-secret-key"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

import models
from auth import hash_password
from database import SessionLocal, engine
from main import app
from security import login_limiter, register_limiter

PASSWORD = "Str0ngPassw0rd!"


@pytest.fixture(autouse=True)
def clean_db():
    models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
    login_limiter.reset()
    register_limiter.reset()
    yield


def make_user(username, role="customer"):
    db = SessionLocal()
    db.add(models.User(username=username, full_name=username.title(), email=f"{username}@example.com",
                       password_hash=hash_password(PASSWORD), role=role))
    db.commit()
    db.close()


def login_client(username, role="customer"):
    """Create a user (if needed) and return a logged-in client plus its CSRF header."""
    db = SessionLocal()
    exists = db.query(models.User).filter(models.User.username == username).first()
    db.close()
    if not exists:
        make_user(username, role)
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    c.csrf = {"X-CSRF-Token": r.json()["csrf_token"]}
    return c


@pytest.fixture
def anon():
    return TestClient(app)


@pytest.fixture
def customer():
    return login_client("alice")


@pytest.fixture
def customer2():
    return login_client("bob")


@pytest.fixture
def agent():
    return login_client("agent1", "agent")


@pytest.fixture
def admin():
    return login_client("admin1", "admin")


def new_ticket(client, subject="Printer broken", description="It does not print anything"):
    r = client.post("/api/tickets", json={"subject": subject, "description": description}, headers=client.csrf)
    assert r.status_code == 201, r.text
    return r.json()["ticket_id"]
