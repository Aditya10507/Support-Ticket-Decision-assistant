# Test that users cannot read each other's tickets
import os
import tempfile
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from src.api import app, get_current_user_id
import src.database as db
from src.auth import create_login_token

# No token should give 401 error
def test_no_token_blocked():
    # Empty header must raise 401
    with pytest.raises(HTTPException) as e:
        get_current_user_id(None)
    assert e.value.status_code == 401

# Bad token should give 401 error
def test_bad_token_blocked():
    # Wrong token must raise 401
    with pytest.raises(HTTPException) as e:
        get_current_user_id("Bearer fake123")
    assert e.value.status_code == 401

# Alice cannot read Bob's ticket
def test_alice_cannot_read_bob_ticket():
    # Make temp DB so real data is safe
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    old_url = db.DATABASE_URL
    db.DATABASE_URL = tmp.name
    try:
        # Make tables in temp DB
        db.init_db()
        conn = db.get_connection()
        cur = conn.cursor()
        # Make two users: Alice and Bob
        cur.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", ("alice@test.com", "x"))
        alice_id = cur.lastrowid
        cur.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", ("bob@test.com", "x"))
        bob_id = cur.lastrowid
        # Make one ticket owned by Bob
        cur.execute("INSERT INTO tickets (user_id, message) VALUES (?, ?)", (bob_id, "Bob issue"))
        tid = cur.lastrowid
        conn.commit()
        conn.close()
        # Make tokens for both
        alice_token = create_login_token(alice_id)
        bob_token = create_login_token(bob_id)
        # Call API without startup event
        with TestClient(app, raise_server_exceptions=False) as client:
            # Alice tries to read Bob ticket -> 403
            r1 = client.get(f"/tickets/{tid}", headers={"Authorization": f"Bearer {alice_token}"})
            assert r1.status_code == 403
            # Bob reads own ticket -> 200
            r2 = client.get(f"/tickets/{tid}", headers={"Authorization": f"Bearer {bob_token}"})
            assert r2.status_code == 200
    finally:
        # Restore real DB path and delete temp file
        db.DATABASE_URL = old_url
        os.unlink(tmp.name)
