"""
auth.py - Autenticazione: hashing password (bcrypt) e sessioni a token opaco.

Flusso: register -> crea utente con password hashata. login -> verifica le
credenziali e rilascia un token casuale salvato in tabella `sessions`. Le route
protette dipendono da `current_user`, che risolve il bearer token nell'utente.

Token opaco (non JWT): nessuna dipendenza extra, revocabile (logout = delete).

Concetto chiave: NON salviamo mai la password in chiaro. Salviamo il suo "hash"
bcrypt, una funzione a senso unico: dalla password ottieni l'hash, ma dall'hash
NON puoi risalire alla password. Al login ri-calcoliamo l'hash e confrontiamo.
"""

import uuid       # genera identificatori univoci casuali (per l'id utente)
import secrets    # genera token crittograficamente sicuri (per le sessioni)

import bcrypt     # libreria standard de-facto per l'hashing delle password
# Pezzi di FastAPI per gestire l'autenticazione nelle route:
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Importiamo il modulo database con un alias breve `db` per scrivere db.funzione().
from debrief import database as db


# --- Password ---

def hash_password(password: str) -> str:
    """Hash bcrypt della password. Restituisce una stringa salvabile in DB."""
    # bcrypt lavora con `bytes`, non con `str`: .encode() converte testo→byte.
    # gensalt() genera un "sale" casuale (incluso nell'hash) così due password
    # uguali producono hash diversi. .decode() riconverte i byte in stringa per
    # salvarli comodamente nel DB.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica una password contro il suo hash bcrypt."""
    try:
        # checkpw ri-calcola l'hash della password fornita (usando il sale dentro
        # password_hash) e confronta. Restituisce True/False.
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Se l'hash salvato è malformato (es. dato sporco), non esplodiamo:
        # consideriamo semplicemente la verifica fallita.
        return False


def _sanitize(user: dict) -> dict:
    """Rimuove campi sensibili prima di restituire un utente al client."""
    # .pop(chiave, default): toglie la chiave dal dict se c'è; il secondo argomento
    # None evita errore se la chiave non esiste. Così l'hash della password non
    # esce MAI verso il frontend.
    user.pop("password_hash", None)
    return user


# --- Registrazione / login / logout ---

def register_user(username: str, password: str) -> dict:
    """Crea un nuovo utente. Solleva ValueError se lo username è già preso."""
    # uuid.uuid4().hex = id casuale univoco come stringa esadecimale.
    # Salviamo l'hash, mai la password in chiaro.
    user = db.create_user(uuid.uuid4().hex, username, hash_password(password))
    return _sanitize(user)


def login(username: str, password: str) -> str:
    """Verifica le credenziali e rilascia un token di sessione.
    Solleva ValueError se username o password non sono validi."""
    user = db.get_user_by_username(username)
    # `not verify_password(...)` → True se la password NON combacia. Per sicurezza
    # diamo lo stesso errore sia per username inesistente sia per password errata
    # (non riveliamo quale dei due è sbagliato).
    if user is None or not verify_password(password, user["password_hash"]):
        raise ValueError("Invalid username or password")
    # token_urlsafe(32) = stringa casuale di 32 byte, sicura da mettere in un URL/header.
    token = secrets.token_urlsafe(32)
    db.create_session(token, user["id"])
    return token


def logout(token: str):
    """Invalida il token di sessione corrente."""
    db.delete_session(token)


# --- Dependency FastAPI per le route protette ---

# HTTPBearer legge l'header "Authorization: Bearer <token>". auto_error=False →
# non lancia errore automatico se manca: lo gestiamo noi sotto con un messaggio chiaro.
_bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """Risolve il bearer token nell'utente autenticato (sanitizzato).
    Solleva 401 se il token manca o non è valido."""
    # Questa è una "dependency" di FastAPI: le route che scrivono
    # `user = Depends(current_user)` la eseguono PRIMA del proprio corpo. Se qui
    # solleviamo un'eccezione, la route non viene nemmeno eseguita.
    # `Depends(_bearer)` dice a FastAPI di estrarre lui le credenziali dall'header
    # e passarle come argomento `creds`.
    if creds is None:
        # HTTPException → FastAPI la trasforma in una risposta HTTP con quel codice.
        raise HTTPException(status_code=401, detail="Missing bearer token")
    user_id = db.get_user_id_by_token(creds.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return _sanitize(user)
