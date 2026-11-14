# How to turn this project into marks (report + video)

## Order of work
1. Put the files in your GitHub repo and **commit in small steps** (see commit list below).
2. Run the app, run the tests, take your OWN screenshots (examples are in `docs/screenshots/`).
3. Write the report from the evidence. 4. Record the video last.

## Suggested commits (regular history = marks)
1. `Add users table, Argon2 hashing and login` 2. `Add JWT cookie session and CSRF token`
3. `Add RBAC and object-level ticket checks` 4. `Add Pydantic validation and secure ticket IDs`
5. `Add audit log and admin endpoints` 6. `Add security headers, CORS lock-down, config via .env`
7. `Rebuild front end without innerHTML` 8. `Add pytest functional and security tests`
9. `Add Bandit and pip-audit reports` 10. `Update README and docs`

## Report (5 pages, NCI template, Times New Roman 11, headings 12) – what to write where
| Section | Put this | Rubric |
|---|---|---|
| Executive summary | Purpose of app, 3-4 key fixes, test results (37 tests, Bandit 0 issues) | 5% |
| 1 Introduction | Support CRM background; aim = secure it | |
| 2 Methodology | e.g. Agile/iterative with security in every sprint (secure SDLC); say why | |
| 3 Requirements | Use-case diagram (3 roles), functional + non-functional, SR1–SR10 | 10% |
| 4 Design | DFD with trust boundaries (README section 8), abuse/misuse cases, STRIDE table | 15% |
| 5 Implementation | Why FastAPI/SQLAlchemy/Argon2/JWT cookie; 2–3 code snippets (`require_roles`, `_load_ticket`, login lockout) | 25% |
| 6 Testing | Pytest + Bandit + pip-audit; the 3 deep tests table; findings (2 Bandit lows fixed) | 10% |
| 7 Conclusion | What was achieved + limitations (README section 9) | |
| References | IEEE style, numbered [1], [2] … | 5% |
| Appendices | Requirements table with % , screenshots, test output | |

Front page: name, student ID, project title, GitHub link, **YouTube unlisted link**. Add the AI declaration (cover sheet).

## Video script (target 6 minutes, face visible THE WHOLE time)
1. 0:00 Introduce yourself, show GitHub repo + README (30 s)
2. Start app: `uvicorn main:app`, open login page (30 s)
3. Customer: register, login, create ticket, see only own tickets (60 s)
4. Show XSS payload `<script>alert(1)</script>` appears as text (30 s)
5. Agent: update status. Admin: delete, change role, audit log (60 s)
6. Attacks: wrong password ×5 → lockout; customer opens another user's ticket URL → "not found"; `' OR '1'='1` in search → nothing (90 s)
7. Code walkthrough: `auth.py`, `main.py` (`_load_ticket`), `schemas.py`, database tables in a DB viewer (60 s)
8. Run `pytest` and `bandit`, show results (30 s)
