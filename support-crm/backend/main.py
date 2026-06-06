from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from datetime import datetime
import random

from database import SessionLocal, engine
from models import Ticket
from schemas import TicketCreate, TicketUpdate

import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/")
def home():
    return {"message": "Support CRM API Running"}


# CREATE TICKET
@app.post("/api/tickets")
def create_ticket(ticket: TicketCreate, db: Session = Depends(get_db)):

    random_id = f"TKT-{random.randint(1000,9999)}"

    new_ticket = Ticket(
        ticket_id=random_id,
        customer_name=ticket.customer_name,
        customer_email=ticket.customer_email,
        subject=ticket.subject,
        description=ticket.description,
        status="Open",
        notes=""
    )

    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)

    return {
        "ticket_id": new_ticket.ticket_id,
        "created_at": new_ticket.created_at
    }


# GET ALL TICKETS
@app.get("/api/tickets")
def get_tickets(
    status: str = None,
    search: str = None,
    db: Session = Depends(get_db)
):

    tickets = db.query(Ticket)

    if status:
        tickets = tickets.filter(Ticket.status == status)

    if search:
        tickets = tickets.filter(
            (Ticket.customer_name.contains(search)) |
            (Ticket.customer_email.contains(search)) |
            (Ticket.subject.contains(search)) |
            (Ticket.description.contains(search)) |
            (Ticket.ticket_id.contains(search))
        )

    return tickets.all()


# GET SINGLE TICKET
@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):

    return db.query(Ticket).filter(
        Ticket.ticket_id == ticket_id
    ).first()


# UPDATE TICKET
@app.put("/api/tickets/{ticket_id}")
def update_ticket(
    ticket_id: str,
    updated_ticket: TicketUpdate,
    db: Session = Depends(get_db)
):

    ticket = db.query(Ticket).filter(
        Ticket.ticket_id == ticket_id
    ).first()

    if not ticket:
        return {"success": False, "message": "Ticket not found"}

    ticket.status = updated_ticket.status
    ticket.notes = updated_ticket.notes
    ticket.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(ticket)

    return {
        "success": True,
        "updated_at": ticket.updated_at
    }


# DELETE TICKET
@app.delete("/api/tickets/{ticket_id}")
def delete_ticket(ticket_id: str, db: Session = Depends(get_db)):

    ticket = db.query(Ticket).filter(
        Ticket.ticket_id == ticket_id
    ).first()

    if not ticket:
        return {"success": False, "message": "Ticket not found"}

    db.delete(ticket)
    db.commit()

    return {"success": True, "message": "Ticket deleted"}