"""Autenticazione bcrypt con sessioni a token opaco revocabile."""

import uuid
import secrets

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from debrief import database as db


# Password

def hash_password(password: str) -> str:
    """Restituisce l'hash bcrypt della password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica una password contro il suo hash bcrypt."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Un hash corrotto equivale a credenziali non valide.
        return False


def _sanitize(user: dict) -> dict:
    """Rimuove i campi sensibili prima di inviare l'utente al frontend."""
    user.pop("password_hash", None)
    return user


# Sessioni

def register_user(username: str, password: str, team_id: str) -> dict:
    """Crea un nuovo utente. Solleva ValueError se lo username è già preso."""
    user = db.create_user(uuid.uuid4().hex, username, hash_password(password), team_id)
    return _sanitize(user)


def login(username: str, password: str) -> str:
    """Verifica le credenziali e crea una sessione."""
    user = db.get_user_by_username(username)
    # Non rivelare quale credenziale è errata.
    if user is None or not verify_password(password, user["password_hash"]):
        raise ValueError("Invalid username or password")
    token = secrets.token_urlsafe(32)
    db.create_session(token, user["id"])
    return token


def logout(token: str):
    """Invalida il token di sessione corrente."""
    db.delete_session(token)


# Dipendenza per le route protette

_bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """Restituisce l'utente del token bearer oppure solleva HTTP 401."""
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    user_id = db.get_user_id_by_token(creds.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return _sanitize(user)
