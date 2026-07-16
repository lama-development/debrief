"""Endpoint di autenticazione e catalogo team."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from debrief import auth
from debrief import database as db

router = APIRouter(prefix="/auth", tags=["auth"])

_bearer = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)
    team_id: str = Field(min_length=1)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
def register(body: RegisterRequest):
    """Crea un utente ed esegue subito l'accesso."""
    try:
        user = auth.register_user(body.username, body.password, body.team_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    token = auth.login(body.username, body.password)
    return {"user": user, "token": token}


@router.post("/login")
def do_login(body: LoginRequest):
    """Verifica le credenziali e restituisce un token di sessione."""
    try:
        token = auth.login(body.username, body.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    return {"token": token}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def do_logout(
    creds: HTTPAuthorizationCredentials = Depends(_bearer),
    user: dict = Depends(auth.current_user),
):
    """Invalida il token corrente (richiede autenticazione)."""
    auth.logout(creds.credentials)


@router.get("/me")
def me(user: dict = Depends(auth.current_user)):
    """Restituisce l'utente autenticato."""
    return user


@router.get("/teams")
def teams():
    """Catalogo pubblico necessario per scegliere il team in registrazione."""
    catalog, _ = db.get_teams()
    return catalog
