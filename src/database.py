# sqlite3 lets us use a simple file database
import sqlite3
# os lets us read settings from environment
import os
# load_dotenv loads settings from the .env file
from dotenv import load_dotenv

# Load .env file first so getenv below can find values
load_dotenv()

# Path to database file. Uses / so it works on all systems.
DATABASE_URL = os.getenv("DATABASE_URL", "data/support_ticket_decision_assisstant.db")


def get_connection():
    conn = sqlite3.connect(DATABASE_URL)

    # By default, SQLite returns rows as tuples (0, "alice@mail.com", ...)
    # Setting row_factory = sqlite3.Row lets us access data by column name: row["email"]
    conn.row_factory = sqlite3.Row  # lets you access columns by name
    return conn
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        email           TEXT    UNIQUE NOT NULL,
        password_hash   TEXT    NOT NULL,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS tickets (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL,
        message     TEXT    NOT NULL,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS decisions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id   INTEGER NOT NULL,
        action      TEXT    NOT NULL,
        reason      TEXT    NOT NULL,
        confidence  REAL    NOT NULL,
        sources     TEXT    NOT NULL,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ticket_id) REFERENCES tickets(id)
        );
        CREATE TABLE IF NOT EXISTS kb_chunks (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        source      TEXT    NOT NULL,
        text        TEXT    NOT NULL,
        embedding   TEXT    NOT NULL,
        model       TEXT    NOT NULL,
        dim         INTEGER NOT NULL
        );
        """)
    conn.commit()  # Save all changes permanently to the database file
    conn.close()   # Close the connection — always close when done to free resources

# Only run this when we run this file directly
if __name__ == "__main__":
    # Create tables if they do not exist
    init_db()
    # Show simple message when done
    print("Database initialized.")