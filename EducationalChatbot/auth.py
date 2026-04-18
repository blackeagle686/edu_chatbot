"""
auth.py — Wasla lightweight in-memory authentication.
Stores hashed passwords using Python's built-in hashlib so there
are no additional dependencies required.
"""
import hashlib
import os
import hmac

# In-memory user store: { username: {"password_hash": str, "role": str} }
_users: dict = {}

# Secret for signing session tokens (loaded from env or a random key)
_SECRET = os.getenv("SESSION_SECRET", os.urandom(32).hex())


def _hash(password: str) -> str:
    """SHA-256 + HMAC password hashing."""
    return hmac.new(_SECRET.encode(), password.encode(), hashlib.sha256).hexdigest()


def register(username: str, password: str, role: str = "user") -> dict:
    """Register a new user. Returns {"ok": True} or {"error": "..."}."""
    if not username or not password:
        return {"error": "Username and password are required."}
    if len(username) < 3:
        return {"error": "Username must be at least 3 characters."}
    if len(password) < 6:
        return {"error": "Password must be at least 6 characters."}
    if username in _users:
        return {"error": "Username already taken."}
    _users[username] = {"password_hash": _hash(password), "role": role}
    return {"ok": True, "username": username, "role": role}


def login(username: str, password: str) -> dict:
    """Verify credentials. Returns {"ok": True, "role": ...} or {"error": "..."}."""
    user = _users.get(username)
    if not user:
        return {"error": "Invalid username or password."}
    if not hmac.compare_digest(user["password_hash"], _hash(password)):
        return {"error": "Invalid username or password."}
    return {"ok": True, "username": username, "role": user["role"]}


def make_session_token(username: str) -> str:
    """Produce a simple signed token: username|signature."""
    sig = hmac.new(_SECRET.encode(), username.encode(), hashlib.sha256).hexdigest()
    return f"{username}|{sig}"


def verify_session_token(token: str) -> dict | None:
    """Verify and decode a session token. Returns user dict or None."""
    if not token or "|" not in token:
        return None
    username, sig = token.rsplit("|", 1)
    expected = hmac.new(_SECRET.encode(), username.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    user = _users.get(username)
    return {"username": username, "role": user["role"]} if user else None
