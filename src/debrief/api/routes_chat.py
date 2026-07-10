"""
routes_chat.py - Chat con streaming SSE.

Inoltra il generatore sincrono service.stream_chat() come Server-Sent Events.
FastAPI esegue il generatore sincrono in un threadpool, quindi le chiamate
bloccanti interne (sqlite, embedding, LanceDB, LLM) non bloccano l'event loop.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from debrief import auth
from debrief.api import service

router = APIRouter(prefix="/incidents", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


@router.post("/{incident_id}/chat")
def chat(incident_id: str, body: ChatRequest, user: dict = Depends(auth.current_user)):
    """Invia un messaggio all'incidente e riceve in streaming la risposta
    dell'agente. Eventi SSE: routing | tool | token | triage | done | error."""
    # 404 pulito PRIMA di iniziare lo streaming: una volta partita la risposta in
    # streaming, lo status code HTTP è già stato inviato e non si può più cambiare.
    if not service.can_access_incident(incident_id, user["id"]):
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    service.join_incident(incident_id, user["id"])

    # Generator expression: avvolge ogni evento prodotto da stream_chat in un frame
    # SSE. È "pigra" (lazy): i frame vengono prodotti uno a uno man mano che servono,
    # non tutti subito. Niente parentesi quadre = generatore, non lista.
    stream = (
        service.sse_frame(event)
        for event in service.stream_chat(incident_id, body.message, user["id"])
    )
    # StreamingResponse invia il generatore al client a pezzi. FastAPI esegue il
    # generatore sincrono in un threadpool, quindi le chiamate bloccanti interne
    # (sqlite, embedding, LLM) non bloccano l'event loop del server.
    return StreamingResponse(
        stream,
        media_type="text/event-stream",   # tipo MIME richiesto da SSE
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disabilita il buffering di eventuali proxy (es. nginx)
        },
    )
