from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func, or_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import datetime

# Initialize FastAPI app
app = FastAPI(title="Bitespeed Identity Reconciliation API")

# SQLite Database setup
DATABASE_URL = "sqlite:///./contacts.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Contact Model
class Contact(Base):
    __tablename__ = "contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    phoneNumber = Column(String, nullable=True, index=True)
    email = Column(String, nullable=True, index=True)
    linkedId = Column(Integer, nullable=True, index=True)
    linkPrecedence = Column(String, nullable=False, default="primary")
    createdAt = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    updatedAt = Column(DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    deletedAt = Column(DateTime, nullable=True)

# Create tables
Base.metadata.create_all(bind=engine)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Request Model
class IdentifyRequest(BaseModel):
    email: Optional[str] = None
    phoneNumber: Optional[str] = None

# Response Model
class ContactResponse(BaseModel):
    primaryContactId: int
    emails: List[str]
    phoneNumbers: List[str]
    secondaryContactIds: List[int]

class IdentifyResponse(BaseModel):
    contact: ContactResponse

# Helper functions
def find_primary_contact(db: Session, contact_id: int):
    contact = db.query(Contact).filter(Contact.id == contact_id).first()
    if not contact:
        return None
    
    if contact.linkPrecedence == "primary":
        return contact
    
    return find_primary_contact(db, contact.linkedId)

def get_all_linked_contacts(db: Session, primary_id: int):
    primary_contact = db.query(Contact).filter(Contact.id == primary_id).first()
    if not primary_contact or primary_contact.linkPrecedence != "primary":
        return []
    
    secondary_contacts = db.query(Contact).filter(
        Contact.linkedId == primary_id,
        Contact.linkPrecedence == "secondary"
    ).all()
    
    return [primary_contact] + secondary_contacts

@app.post("/identify", response_model=IdentifyResponse)
def identify(request: IdentifyRequest, db: Session = Depends(get_db)):
    # Validate request
    if not request.email and not request.phoneNumber:
        raise HTTPException(status_code=400, detail="Either email or phoneNumber must be provided")
    
    # Find contacts with matching email or phone number
    query = db.query(Contact)
    conditions = []
    
    if request.email:
        conditions.append(Contact.email == request.email)
    
    if request.phoneNumber:
        conditions.append(Contact.phoneNumber == request.phoneNumber)
    
    matching_contacts = query.filter(or_(*conditions)).all()
    
    # Case 1: No matching contacts found, create a new primary contact
    if not matching_contacts:
        new_contact = Contact(
            phoneNumber=request.phoneNumber,
            email=request.email,
            linkPrecedence="primary"
        )
        db.add(new_contact)
        db.commit()
        db.refresh(new_contact)
        
        return IdentifyResponse(
            contact=ContactResponse(
                primaryContactId=new_contact.id,
                emails=[new_contact.email] if new_contact.email else [],
                phoneNumbers=[new_contact.phoneNumber] if new_contact.phoneNumber else [],
                secondaryContactIds=[]
            )
        )
    
    # Find all primary contacts among matches
    primary_contacts = [c for c in matching_contacts if c.linkPrecedence == "primary"]
    
    # Case 2: Multiple primary contacts found, need to consolidate
    if len(primary_contacts) > 1:
        # Sort by creation date to find the oldest primary contact
        primary_contacts.sort(key=lambda x: x.createdAt)
        oldest_primary = primary_contacts[0]
        other_primaries = primary_contacts[1:]
        
        # Convert other primaries to secondary linked to the oldest
        for contact in other_primaries:
            contact.linkPrecedence = "secondary"
            contact.linkedId = oldest_primary.id
            contact.updatedAt = datetime.datetime.utcnow()
        
        db.commit()
    
    # Get the primary contact
    primary_contact = None
    if primary_contacts:
        primary_contact = primary_contacts[0]
    else:
        # All contacts are secondary, find their primary
        primary_contact = find_primary_contact(db, matching_contacts[0].linkedId)
    
    # Get all contacts linked to this primary
    all_linked_contacts = get_all_linked_contacts(db, primary_contact.id)
    
    # Check if we need to create a new secondary contact
    existing_emails = {c.email for c in all_linked_contacts if c.email}
    existing_phones = {c.phoneNumber for c in all_linked_contacts if c.phoneNumber}
    
    if ((request.email and request.email not in existing_emails) or 
        (request.phoneNumber and request.phoneNumber not in existing_phones)):
        # Create a new secondary contact
        new_secondary = Contact(
            phoneNumber=request.phoneNumber,
            email=request.email,
            linkedId=primary_contact.id,
            linkPrecedence="secondary"
        )
        db.add(new_secondary)
        db.commit()
        db.refresh(new_secondary)
        all_linked_contacts.append(new_secondary)
    
    # Prepare response
    emails = list({c.email for c in all_linked_contacts if c.email})
    phone_numbers = list({c.phoneNumber for c in all_linked_contacts if c.phoneNumber})
    secondary_ids = [c.id for c in all_linked_contacts if c.linkPrecedence == "secondary"]
    
    return IdentifyResponse(
        contact=ContactResponse(
            primaryContactId=primary_contact.id,
            emails=emails,
            phoneNumbers=phone_numbers,
            secondaryContactIds=secondary_ids
        )
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)