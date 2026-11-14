"""Create demo users (one per role).

Usage:   python seed.py
Optional: SEED_PASSWORD=YourStrongPass123 python seed.py   (otherwise random passwords are printed once)
Passwords are never stored in the repository.
"""
import os
import secrets

import models
from auth import hash_password
from database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)

DEMO = [
    ("admin1", "Alice Admin", "admin@example.com", "admin"),
    ("agent1", "Aaron Agent", "agent@example.com", "agent"),
    ("customer1", "Chloe Customer", "customer@example.com", "customer"),
]

db = SessionLocal()
shared = os.getenv("SEED_PASSWORD")
for username, full_name, email, role in DEMO:
    if db.query(models.User).filter(models.User.username == username).first():
        print(f"{username}: already exists, skipped")
        continue
    password = shared or (secrets.token_urlsafe(12) + "a1")
    db.add(models.User(username=username, full_name=full_name, email=email,
                       password_hash=hash_password(password), role=role))
    db.commit()
    print(f"created {role:9s} username={username}  password={password}")
db.close()
