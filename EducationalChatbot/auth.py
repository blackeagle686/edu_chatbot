"""
auth.py — Wasla Persistent SQLite Authentication.
Stores users in a local database file to ensure data persists across restarts.
"""
import hashlib
import os
import hmac
import sqlite3
import re
from contextlib import contextmanager

# Database configuration
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.db")
_SECRET = os.getenv("SESSION_SECRET", "wasla-default-super-secret-key-2026")

def init_db():
    """Initializes the SQLite database and creates the users table if it doesn't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                full_name TEXT DEFAULT '',
                bio TEXT DEFAULT '',
                cv_filename TEXT
            )
        """)
        conn.commit()

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Enable name-based access to columns
    try:
        yield conn
    finally:
        conn.close()

def _hash(password: str) -> str:
    """SHA-256 + HMAC password hashing."""
    return hmac.new(_SECRET.encode(), password.encode(), hashlib.sha256).hexdigest()

def register(username: str, password: str, role: str = "user") -> dict:
    """Register a new user in the database."""
    if not re.match(r'^[a-zA-Z0-9_\-.]+$', username):
        return {"error": "Username can only contain letters, numbers, and . - _"}

    if not username or not password:
        return {"error": "Username and password are required."}
    if len(username) < 3:
        return {"error": "Username must be at least 3 characters."}
    if len(password) < 6:
        return {"error": "Password must be at least 6 characters."}

    try:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, _hash(password), role)
            )
            conn.commit()
        return {"ok": True, "username": username, "role": role}
    except sqlite3.IntegrityError:
        return {"error": "Username already taken."}
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}

def login(username: str, password: str) -> dict:
    """Verify credentials against the database."""
    if not re.match(r'^[a-zA-Z0-9_\-.]+$', username):
        return {"error": "Invalid username format."}
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        
    if not user:
        return {"error": "Invalid username or password."}
    
    if not hmac.compare_digest(user["password_hash"], _hash(password)):
        return {"error": "Invalid username or password."}
    
    return {"ok": True, "username": username, "role": user["role"]}

def make_session_token(username: str) -> str:
    """Produce a signed session token."""
    sig = hmac.new(_SECRET.encode(), username.encode(), hashlib.sha256).hexdigest()
    return f"{username}|{sig}"

def verify_session_token(token: str) -> dict | None:
    """Verify session token and retrieve user data from the database."""
    if not token or "|" not in token:
        return None
    
    username, sig = token.rsplit("|", 1)
    expected = hmac.new(_SECRET.encode(), username.encode(), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(expected, sig):
        return None
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    
    if not user:
        return None
    
    # Convert Row object to dict and remove password hash
    user_data = dict(user)
    user_data.pop("password_hash", None)
    return user_data

def update_user_profile(username: str, full_name: str, bio: str, cv_filename: str = None) -> bool:
    """Update user profile data in the database."""
    try:
        with get_db() as conn:
            if cv_filename:
                conn.execute(
                    "UPDATE users SET full_name = ?, bio = ?, cv_filename = ? WHERE username = ?",
                    (full_name, bio, cv_filename, username)
                )
            else:
                conn.execute(
                    "UPDATE users SET full_name = ?, bio = ? WHERE username = ?",
                    (full_name, bio, username)
                )
            conn.commit()
            return conn.total_changes > 0
    except Exception:
        return False

# Initialize the database on module load
init_db()
