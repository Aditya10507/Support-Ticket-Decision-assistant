import json
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
from src.database import get_connection, init_db
from src.auth import (
    make_password_hash,
    check_password_match,
    create_login_token,
    get_user_id_from_token
)

# Create the app. It receives all requests.
app = FastAPI(title="Support Ticket Decision Assistant")

# Run this only when the app starts, not on import.
# This keeps tests from touching the real DB.
@app.on_event("startup")
def start_db():
    # Make tables if they do not exist
    init_db()

# ── Request Body Models ────────────────────────────────────────────────────────
# These define what data must come in the request body
# FastAPI automatically validates them — missing fields return a 422 error

class RegisterRequest(BaseModel):
    # Data needed to create a new account
    email: str
    password: str

class LoginRequest(BaseModel):
    # Data needed to log in
    email: str
    password: str

class TicketRequest(BaseModel):
    # Data needed to submit a support ticket
    # 4000 char cap stops quota-burn via huge tickets (422 if over).
    message: str = Field(min_length=1, max_length=4000)

# ── Helper: Get Current User From Token ───────────────────────────────────────
def get_current_user_id(authorization: str) -> int:
    # Checks Authorization header format: "Bearer <token>"
    # Returns user ID if valid, raises HTTP 401 if not
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    # Split "Bearer <token>" and take the token part
    token = authorization.split(" ")[1]

    # Decode the JWT and extract user ID
    user_id = get_user_id_from_token(token)

    # If token is expired or tampered, return 401
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_id

# ── Endpoint 1: POST /register ────────────────────────────────────────────────
@app.post("/register", status_code=201)
def register(request: RegisterRequest):
    # Make a new user. Password is hashed, never saved as plain text.
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Check if email already exists
        existing = cursor.execute(
            "SELECT id FROM users WHERE email = ?", (request.email,)
        ).fetchone()

        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Hash password before saving
        hashed = make_password_hash(request.password)

        # Save new user
        cursor.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (request.email, hashed)
        )
        conn.commit()
    finally:
        # Always close, even if there was an error
        conn.close()

    return {"message": "User registered successfully"}

# ── Endpoint 2: POST /login ───────────────────────────────────────────────────
@app.post("/login")
def login(request: LoginRequest):
    # Check login and return a token if correct
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Find user by email
        user = cursor.execute(
            "SELECT id, password_hash FROM users WHERE email = ?", (request.email,)
        ).fetchone()
    finally:
        # Always close, even if there was an error
        conn.close()

    # Return same error whether email is wrong or password is wrong (security)
    if not user or not check_password_match(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create and return a JWT with this user's ID inside
    token = create_login_token(user["id"])

    return {"access_token": token, "token_type": "bearer"}

# ── Endpoint 3: GET /me ───────────────────────────────────────────────────────
@app.get("/me")
def get_me(authorization: str = Header(default=None)):
    # Returns the logged-in user's account details
    # Requires a valid JWT in the Authorization header
    user_id = get_current_user_id(authorization)

    # Open DB and always close it after
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Get this user's data
        user = cursor.execute(
            "SELECT id, email, created_at FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    finally:
        conn.close()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id": user["id"],
        "email": user["email"],
        "created_at": user["created_at"]
    }

# ── Endpoint 4: POST /tickets ─────────────────────────────────────────────────
@app.post("/tickets", status_code=201)
def submit_ticket(request: TicketRequest, authorization: str = Header(default=None)):
    # Submits a support ticket, runs AI decision, saves and returns the result
    # Only authenticated users can submit tickets
    user_id = get_current_user_id(authorization)

    # Open DB and always close it after
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Save the ticket first
        cursor.execute(
            "INSERT INTO tickets (user_id, message) VALUES (?, ?)",
            (user_id, request.message)
        )
        # Get new ticket id
        ticket_id = cursor.lastrowid

        # Load AI helpers only when needed
        from src.retrieval import retrieve_relevant_chunks
        from src.decision import generate_decision

        # Step 1: Find matching policy text
        relevant_chunks = retrieve_relevant_chunks(request.message)

        # Step 2: Ask Gemini for a decision
        decision = generate_decision(request.message, relevant_chunks)

        # Save the AI answer
        cursor.execute(
            """INSERT INTO decisions (ticket_id, action, reason, confidence, sources)
               VALUES (?, ?, ?, ?, ?)""",
            (
                ticket_id,
                decision["action"],
                decision["reason"],
                decision["confidence"],
                json.dumps(decision["sources"])  # List -> text for DB
            )
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "ticket_id": ticket_id,
        "message": request.message,
        "decision": decision
    }

# ── Endpoint 5: GET /tickets ──────────────────────────────────────────────────
@app.get("/tickets")
def get_my_tickets(authorization: str = Header(default=None)):
    # Returns all tickets submitted by the currently logged-in user
    # Users can ONLY see their own tickets — not anyone else's
    user_id = get_current_user_id(authorization)

    # Open DB and always close it after
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Get only this user's tickets
        tickets = cursor.execute(
            """SELECT t.id, t.message, t.created_at,
                      d.action, d.confidence
               FROM tickets t
               LEFT JOIN decisions d ON d.ticket_id = t.id
               WHERE t.user_id = ?
               ORDER BY t.created_at DESC""",
            (user_id,)
        ).fetchall()
    finally:
        conn.close()

    # Convert each SQLite row into a plain dictionary for JSON response
    return [
        {
            "id": row["id"],
            "message": row["message"],
            "created_at": row["created_at"],
            "action": row["action"],
            "confidence": row["confidence"]
        }
        for row in tickets
    ]

# ── Endpoint 6: GET /tickets/{ticket_id} ──────────────────────────────────────
@app.get("/tickets/{ticket_id}")
def get_ticket_by_id(ticket_id: int, authorization: str = Header(default=None)):
    # Returns one specific ticket with its full AI decision
    # Critical security check: users can ONLY access their own tickets
    user_id = get_current_user_id(authorization)

    # Open DB and always close it after
    conn = get_connection()
    try:
        cursor = conn.cursor()
        # Get one ticket with its decision
        row = cursor.execute(
            """SELECT t.id, t.message, t.created_at, t.user_id,
                      d.action, d.reason, d.confidence, d.sources, d.created_at as decision_at
               FROM tickets t
               LEFT JOIN decisions d ON d.ticket_id = t.id
               WHERE t.id = ?""",
            (ticket_id,)
        ).fetchone()
    finally:
        conn.close()

    # Return 404 if ticket does not exist
    if not row:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # AUTHORIZATION: Does this ticket belong to the person asking?
    # This stops Alice from reading Bob's tickets — returns 403 Forbidden
    if row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "id": row["id"],
        "message": row["message"],
        "created_at": row["created_at"],
        "decision": {
            "action": row["action"],
            "reason": row["reason"],
            "confidence": row["confidence"],
            "sources": json.loads(row["sources"]) if row["sources"] else [],
            "created_at": row["decision_at"]
        }
    }