"""Configurazione dell'applicazione FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from debrief.database import get_connection, create_tables
from debrief.api import routes_auth, routes_incidents, routes_chat, routes_metrics


CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inizializza lo schema SQLite all'avvio."""
    conn = get_connection()
    create_tables(conn)
    conn.close()
    yield


app = FastAPI(
    title="Debrief API",
    description="Incident Response Multi-Agent Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(routes_auth.router)
app.include_router(routes_incidents.router)
app.include_router(routes_chat.router)
app.include_router(routes_metrics.router)


@app.get("/health", tags=["health"])
def health():
    """Verifica che il server risponda."""
    return {"status": "ok"}


def main():
    """Avvia il server di sviluppo."""
    import uvicorn

    uvicorn.run(
        "debrief.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
