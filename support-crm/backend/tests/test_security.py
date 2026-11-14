"""Security tests. Each test maps to a security requirement (see README, section 'Requirements')."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt

import config
from conftest import PASSWORD, login_client, make_user, new_ticket
from database import SessionLocal
from models import AuditLog, User


# ---------- SR1 Authentication ----------
def test_passwords_are_hashed_with_argon2(customer):
    db = SessionLocal()
    u = db.query(User).filter(User.username == "alice").first()
    db.close()
    assert u.password_hash.startswith("$argon2id$") and PASSWORD not in u.password_hash


def test_unauthenticated_requests_are_rejected(anon):
    for method, url in [("get", "/api/tickets"), ("post", "/api/tickets"), ("get", "/api/tickets/TKT-1"),
                        ("put", "/api/tickets/TKT-1"), ("delete", "/api/tickets/TKT-1"),
                        ("get", "/api/admin/users"), ("get", "/api/admin/audit")]:
        assert getattr(anon, method)(url).status_code == 401, url


def test_brute_force_lockout(anon):
    make_user("victim")
    for _ in range(config.MAX_FAILED_LOGINS):
        assert anon.post("/api/auth/login", json={"username": "victim", "password": "wrong-pass-1"}).status_code == 401
    # even the CORRECT password is refused while locked
    r = anon.post("/api/auth/login", json={"username": "victim", "password": PASSWORD})
    assert r.status_code == 429


def test_login_error_does_not_reveal_whether_user_exists(anon):
    make_user("realuser")
    a = anon.post("/api/auth/login", json={"username": "realuser", "password": "bad-password-1"})
    b = anon.post("/api/auth/login", json={"username": "nosuchuser", "password": "bad-password-1"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_weak_password_rejected(anon):
    for pw in ["short1", "onlyletterslong", "1234567890123"]:
        r = anon.post("/api/auth/register", json={"username": "weak", "full_name": "W", "email": "w@example.com", "password": pw})
        assert r.status_code == 422, pw


# ---------- SR2 Session management ----------
def test_session_cookie_flags(anon):
    make_user("cookieuser")
    r = anon.post("/api/auth/login", json={"username": "cookieuser", "password": PASSWORD})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie


def test_forged_and_expired_tokens_rejected(anon):
    make_user("tok")
    forged = jwt.encode({"sub": "1", "role": "admin", "csrf": "x", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "wrong-key", algorithm="HS256")
    anon.cookies.set("access_token", forged)
    assert anon.get("/api/admin/users").status_code == 401
    expired = jwt.encode({"sub": "1", "role": "admin", "csrf": "x", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)}, config.SECRET_KEY, algorithm="HS256")
    anon.cookies.set("access_token", expired)
    assert anon.get("/api/tickets").status_code == 401
    none_alg = jwt.encode({"sub": "1"}, None, algorithm="none")
    anon.cookies.set("access_token", none_alg)
    assert anon.get("/api/tickets").status_code == 401


def test_csrf_token_required_for_state_changes(customer):
    tid = new_ticket(customer)
    r = customer.post("/api/tickets", json={"subject": "abc", "description": "defgh"})            # no header
    assert r.status_code == 403
    r = customer.post("/api/tickets", json={"subject": "abc", "description": "defgh"}, headers={"X-CSRF-Token": "wrong"})
    assert r.status_code == 403
    assert customer.get(f"/api/tickets/{tid}").status_code == 200                                # GET is fine


# ---------- SR3 Authorization ----------
def test_customer_cannot_update_or_delete(customer):
    tid = new_ticket(customer)
    assert customer.put(f"/api/tickets/{tid}", json={"status": "Closed", "notes": ""}, headers=customer.csrf).status_code == 403
    assert customer.delete(f"/api/tickets/{tid}", headers=customer.csrf).status_code == 403


def test_agent_cannot_delete_or_use_admin_area(customer, agent):
    tid = new_ticket(customer)
    assert agent.delete(f"/api/tickets/{tid}", headers=agent.csrf).status_code == 403
    assert agent.get("/api/admin/users").status_code == 403
    assert agent.get("/api/admin/audit").status_code == 403


def test_idor_customer_cannot_access_other_customers_ticket(customer, customer2):
    tid = new_ticket(customer)                                       # Alice's ticket
    assert customer2.get(f"/api/tickets/{tid}").status_code == 404   # Bob guesses the id
    assert customer2.get("/api/tickets").json() == []                # not in his list either
    assert customer2.get("/api/tickets", params={"search": "Printer"}).json() == []


def test_mass_assignment_cannot_self_promote(anon):
    r = anon.post("/api/auth/register", json={"username": "sneaky", "full_name": "S", "email": "s@example.com",
                                              "password": PASSWORD, "role": "admin", "is_active": True})
    assert r.status_code == 201 and r.json()["role"] == "customer"


def test_admin_cannot_change_own_role(admin):
    me = admin.get("/api/auth/me").json()
    assert admin.put(f"/api/admin/users/{me['id']}/role", json={"role": "customer"}, headers=admin.csrf).status_code == 400


def test_deactivated_user_loses_access(admin, customer):
    uid = customer.get("/api/auth/me").json()["id"]
    admin.put(f"/api/admin/users/{uid}/active", json={"is_active": False}, headers=admin.csrf)
    assert customer.get("/api/tickets").status_code == 401


# ---------- SR4 Input validation / injection ----------
SQLI = ["' OR '1'='1", "'; DROP TABLE tickets;--", "\" OR 1=1 --", "' UNION SELECT password_hash FROM users--"]


def test_sql_injection_in_search_and_filters(customer, agent):
    new_ticket(customer)
    for payload in SQLI:
        r = agent.get("/api/tickets", params={"search": payload})
        assert r.status_code == 200 and r.json() == [], payload      # treated as plain text, matches nothing
        assert agent.get("/api/tickets", params={"status": payload}).status_code == 422
    assert len(agent.get("/api/tickets").json()) == 1                # table still intact


def test_sql_injection_in_login(anon):
    make_user("sqluser")
    for payload in SQLI:
        r = anon.post("/api/auth/login", json={"username": payload, "password": payload})
        assert r.status_code in (401, 429)
        assert "access_token" not in r.headers.get("set-cookie", "")


def test_sql_injection_in_ticket_id_path(agent):
    for payload in SQLI:
        assert agent.get(f"/api/tickets/{payload}").status_code in (404, 422)


def test_input_validation_rejects_bad_data(customer, agent):
    tid = new_ticket(customer)
    h = customer.csrf
    assert customer.post("/api/tickets", json={"subject": "x" * 151, "description": "valid text"}, headers=h).status_code == 422
    assert customer.post("/api/tickets", json={"subject": "ok subject", "description": "d" * 2001}, headers=h).status_code == 422
    assert customer.post("/api/tickets", json={"subject": "ok subject", "description": "bad\x00char"}, headers=h).status_code == 422
    assert agent.put(f"/api/tickets/{tid}", json={"status": "Hacked", "notes": ""}, headers=agent.csrf).status_code == 422


def test_bad_email_and_username_rejected(anon):
    base = {"full_name": "N", "password": PASSWORD}
    assert anon.post("/api/auth/register", json={**base, "username": "okname", "email": "not-an-email"}).status_code == 422
    assert anon.post("/api/auth/register", json={**base, "username": "bad name<script>", "email": "a@example.com"}).status_code == 422


def test_xss_payload_is_stored_as_text_and_frontend_never_uses_innerhtml(customer):
    payload = "<script>alert(1)</script>"
    tid = new_ticket(customer, "XSS test subject", payload)
    r = customer.get(f"/api/tickets/{tid}")
    assert r.headers["content-type"].startswith("application/json")   # never rendered as HTML by the server
    assert r.json()["description"] == payload
    # static check on the UI code: user data only goes in via textContent
    frontend = Path(__file__).resolve().parent.parent.parent / "frontend"
    for f in frontend.glob("*.js"):
        text = f.read_text()
        code = "\n".join(l for l in text.splitlines() if not l.strip().startswith("//"))
        assert "innerHTML" not in code and "document.write" not in code and "eval(" not in code, f.name


# ---------- SR5 Secure configuration / error handling ----------
def test_security_headers_present(anon):
    r = anon.get("/login.html")
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_api_responses_not_cached(customer):
    assert customer.get("/api/tickets").headers["cache-control"] == "no-store"


def test_api_docs_disabled_by_default(anon):
    assert anon.get("/docs").status_code in (404, 405)
    assert anon.get("/openapi.json").status_code in (404, 405)


def test_cors_closed_by_default(anon):
    r = anon.get("/api/tickets", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_ticket_ids_are_unpredictable_and_unique(customer):
    ids = {new_ticket(customer, f"Subject {i}", "some description") for i in range(30)}
    assert len(ids) == 30
    assert all(re.fullmatch(r"TKT-[0-9A-F]{8}", i) for i in ids)


def test_no_stack_trace_or_internal_details_leak(agent):
    r = agent.get("/api/tickets/TKT-NOPE")
    assert r.status_code == 404 and "Traceback" not in r.text and "sqlalchemy" not in r.text.lower()


# ---------- SR6 Audit logging ----------
def test_security_events_are_logged(anon, admin):
    make_user("loguser")
    anon.post("/api/auth/login", json={"username": "loguser", "password": "wrong-password-1"})
    anon.post("/api/auth/login", json={"username": "loguser", "password": PASSWORD})
    db = SessionLocal()
    actions = {a.action for a in db.query(AuditLog).all()}
    db.close()
    assert {"LOGIN_FAIL", "LOGIN_OK"} <= actions
    rows = admin.get("/api/admin/audit").json()
    assert any(r["action"] == "LOGIN_OK" for r in rows)


def test_deletions_and_role_changes_are_logged(customer, admin):
    tid = new_ticket(customer)
    admin.delete(f"/api/tickets/{tid}", headers=admin.csrf)
    uid = customer.get("/api/auth/me").json()["id"]
    admin.put(f"/api/admin/users/{uid}/role", json={"role": "agent"}, headers=admin.csrf)
    actions = [r["action"] for r in admin.get("/api/admin/audit").json()]
    assert "TICKET_DELETE" in actions and "ROLE_CHANGE" in actions
