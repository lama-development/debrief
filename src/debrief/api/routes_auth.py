"""
routes_auth.py - Endpoint di autenticazione: register, login, logout, me.

Le route sono sottili: validano l'input e delegano a auth.py. register e login
sono aperte; logout e me richiedono un bearer token valido.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from debrief import auth
from debrief import database as db

# APIRouter raggruppa endpoint correlati. prefix="/auth" → tutte le route qui
# iniziano con /auth (es. /auth/login). tags=[...] le raggruppa nella doc /docs.
router = APIRouter(prefix="/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False)


# Questi modelli Pydantic definiscono la FORMA del corpo (body) JSON in arrivo.
# FastAPI li usa per validare la richiesta automaticamente: se mancano campi o i
# tipi sono sbagliati, risponde 422 da solo, prima ancora di entrare nella funzione.
class RegisterRequest(BaseModel):
    username: str = Field(min_length=1)   # min_length=1 → non può essere vuoto
    password: str = Field(min_length=1)
    team_id: str = Field(min_length=1)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: RegisterRequest):
    """Crea un utente e lo autentica subito (auto-login)."""
    # `body: RegisterRequest` → FastAPI legge il JSON, lo valida e ce lo passa già
    # come oggetto tipizzato. Accediamo ai campi con body.username, body.password.
    try:
        user = auth.register_user(body.username, body.password, body.team_id)
    except ValueError as e:
        # auth solleva ValueError se lo username è già preso → lo traduciamo in
        # un errore HTTP 409 Conflict. str(e) è il messaggio dell'eccezione.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    token = auth.login(body.username, body.password)
    return {"user": user, "token": token}


@router.post("/login")
def do_login(body: LoginRequest):
    """Verifica le credenziali e restituisce un token di sessione."""
    try:
        token = auth.login(body.username, body.password)
    except ValueError as e:
        # Credenziali errate → 401 Unauthorized.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return {"token": token}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def do_logout(
    # Due dependency: una per leggere il token grezzo (per invalidarlo), una per
    # garantire che l'utente sia autenticato (altrimenti current_user solleva 401).
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    user: dict = Depends(auth.current_user),
):
    """Invalida il token corrente (richiede autenticazione)."""
    # 204 No Content → successo senza corpo di risposta.
    auth.logout(creds.credentials)


@router.get("/me")
def me(user: dict = Depends(auth.current_user)):
    """Restituisce l'utente autenticato."""
    # Depends(current_user) fa tutto il lavoro: se il token è valido, `user`
    # contiene già l'utente; altrimenti la richiesta è stata respinta con 401.
    return user


@router.get("/teams")
def teams():
    """Catalogo pubblico necessario per scegliere il team in registrazione."""
    catalog, _ = db.get_teams()
    return catalog
