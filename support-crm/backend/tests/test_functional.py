"""Functional tests: the application does what it should (CRUD, roles, UI flow)."""
from conftest import PASSWORD, new_ticket


def test_register_and_login(anon):
    r = anon.post("/api/auth/register", json={"username": "newuser", "full_name": "New User",
                                              "email": "new@example.com", "password": PASSWORD})
    assert r.status_code == 201 and r.json()["role"] == "customer"
    assert "password" not in r.text and "hash" not in r.text
    r = anon.post("/api/auth/login", json={"username": "newuser", "password": PASSWORD})
    assert r.status_code == 200
    assert anon.get("/api/auth/me").json()["username"] == "newuser"


def test_logout_ends_session(customer):
    assert customer.post("/api/auth/logout", headers=customer.csrf).status_code == 200
    customer.cookies.clear()
    assert customer.get("/api/tickets").status_code == 401


def test_create_read_ticket(customer):
    tid = new_ticket(customer)
    r = customer.get(f"/api/tickets/{tid}")
    assert r.status_code == 200
    body = r.json()
    assert body["subject"] == "Printer broken" and body["status"] == "Open"
    assert body["customer_name"] == "Alice"          # taken from the account
    assert len(customer.get("/api/tickets").json()) == 1


def test_agent_sees_all_and_updates(customer, agent):
    tid = new_ticket(customer)
    assert len(agent.get("/api/tickets").json()) == 1
    r = agent.put(f"/api/tickets/{tid}", json={"status": "In Progress", "notes": "Looking into it"}, headers=agent.csrf)
    assert r.status_code == 200
    t = customer.get(f"/api/tickets/{tid}").json()
    assert t["status"] == "In Progress" and t["notes"] == "Looking into it"


def test_admin_deletes(customer, admin):
    tid = new_ticket(customer)
    assert admin.delete(f"/api/tickets/{tid}", headers=admin.csrf).status_code == 200
    assert admin.get(f"/api/tickets/{tid}").status_code == 404


def test_search_and_filter(customer, agent):
    new_ticket(customer, "Login problem", "Cannot sign in to portal")
    new_ticket(customer, "Billing question", "Invoice is wrong")
    assert len(agent.get("/api/tickets", params={"search": "billing"}).json()) == 1
    assert len(agent.get("/api/tickets", params={"status": "Open"}).json()) == 2
    assert len(agent.get("/api/tickets", params={"status": "Closed"}).json()) == 0


def test_admin_manages_users(admin):
    from conftest import make_user
    make_user("carol")
    users = admin.get("/api/admin/users").json()
    carol = next(u for u in users if u["username"] == "carol")
    r = admin.put(f"/api/admin/users/{carol['id']}/role", json={"role": "agent"}, headers=admin.csrf)
    assert r.status_code == 200 and r.json()["role"] == "agent"


def test_missing_ticket_returns_404(agent):
    assert agent.get("/api/tickets/TKT-DOESNOTEXIST").status_code == 404


def test_frontend_is_served(anon):
    r = anon.get("/login.html")
    assert r.status_code == 200 and "Support CRM" in r.text
