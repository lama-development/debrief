"""
app.py - Applicazione FastAPI di Debrief.

Assembla i router (auth, incidenti, chat, metriche) sopra il service layer.
Allo startup garantisce che la cartella data/ e le tabelle SQLite esistano,
così un clone pulito parte senza passaggi manuali.

Avvio:
    uv run dev
    # oppure
    uv run uvicorn src.debrief.api.app:app --reload
"""

# asynccontextmanager: serve a creare la funzione `lifespan` (vedi sotto), che
# definisce cosa fare all'avvio e allo spegnimento dell'app.
from contextlib import asynccontextmanager

from fastapi import FastAPI
# CORS = Cross-Origin Resource Sharing: regola quali siti (origini) possono
# chiamare la nostra API dal browser. Serve perché il frontend gira su una porta
# diversa (es. 5173) rispetto all'API (8000).
from fastapi.middleware.cors import CORSMiddleware

from debrief.database import get_connection, create_tables
from debrief.api import routes_auth, routes_incidents, routes_chat, routes_metrics


# Origini consentite per il CORS: gli URL del frontend in sviluppo (Vite usa 5173).
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]


# @asynccontextmanager + funzione con `yield` = "lifespan" di FastAPI. Tutto ciò
# che sta PRIMA dello yield viene eseguito all'AVVIO; ciò che sta dopo allo
# SPEGNIMENTO. Qui all'avvio garantiamo che DB e tabelle esistano (idempotente),
# così un clone pulito del progetto parte senza setup manuale.
@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_connection()
    create_tables(conn)
    conn.close()
    yield   # da qui in poi l'app è "in esecuzione"; dopo lo yield = shutdown


# Creiamo l'applicazione FastAPI. title/description/version popolano la documentazione
# automatica (Swagger UI su /docs). lifespan collega la funzione di avvio sopra.
app = FastAPI(
    title="Debrief API",
    description="Incident Response Multi-Agent Platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Registriamo il middleware CORS. "*" = consenti tutti i metodi/header; le origini
# invece sono ristrette a quelle del frontend. Un middleware "avvolge" ogni richiesta.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# Colleghiamo i quattro gruppi di route (router) all'app. Ogni router è definito
# nel suo file e raccoglie endpoint correlati (auth, incidenti, chat, metriche).
app.include_router(routes_auth.router)
app.include_router(routes_incidents.router)
app.include_router(routes_chat.router)
app.include_router(routes_metrics.router)


# @app.get("/health") è un DECORATORE: registra la funzione sottostante come
# gestore della richiesta GET su /health. È il pattern base di FastAPI.
@app.get("/health", tags=["health"])
def health():
    """Liveness check (serve a verificare che il server sia vivo)."""
    return {"status": "ok"}   # FastAPI converte automaticamente il dict in JSON


def main():
    """Entry point per `uv run dev` (vedi [project.scripts] in pyproject.toml)."""
    import uvicorn   # uvicorn è il server che esegue l'app FastAPI

    uvicorn.run(
        "debrief.api.app:app",   # "modulo:oggetto" dell'app
        host="127.0.0.1",        # per cambiare host/porta modifica qui
        port=8000,
        reload=True,             # riavvio automatico al salvataggio (dev)
    )
