# Bitespeed Identity Reconciliation API

This is a FastAPI application that implements the Bitespeed Identity Reconciliation task. The API provides an endpoint to identify and consolidate customer contacts based on matching email addresses and phone numbers.

## Features

- `/identify` endpoint that accepts email and phoneNumber parameters
- Contact reconciliation logic that links related contacts
- SQLite database for storing contact information
- Automatic creation of primary and secondary contacts based on business rules

## Requirements

- Python 3.7+
- FastAPI
- SQLAlchemy
- Uvicorn
- SQLite

## Installation

1. Clone this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Application

### Local Development

```bash
uvicorn main:app --reload
```

## API Documentation

After starting the application, you can access the auto-generated API documentation at:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API Endpoints

### POST `/identify`

Identifies and consolidates contact information.

**Request Body:**

```json
{
  "email": "string", // optional
  "phoneNumber": "string" // optional
}
```

At least one of `email` or `phoneNumber` must be provided.

**Response:**

```json
{
  "contact": {
    "primaryContactId": 0,
    "emails": ["string"],
    "phoneNumbers": ["string"],
    "secondaryContactIds": [0]
  }
}
```

## Database Schema

The application uses a SQLite database with a single `contacts` table:

```
Contact {
  id Int
  phoneNumber String?
  email String?
  linkedId Int?
  linkPrecedence "secondary"|"primary"
  createdAt DateTime
  updatedAt DateTime
  deletedAt DateTime?
}
```

## Business Rules

1. If an incoming request has no matching contacts, a new primary contact is created.
2. If an incoming request matches existing contact(s) but contains new information, a secondary contact is created.
3. If multiple primary contacts are found to be related, they are consolidated with the oldest one remaining as primary.
4. All contacts linked to a primary contact are returned in the response.
