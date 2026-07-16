"""Endpoint della chat con trasmissione progressiva SSE."""

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
    """Invia un messaggio e restituisce gli eventi SSE dell'agente."""
    # Il codice di stato HTTP non può cambiare dopo l'avvio del flusso.
    if not service.can_access_incident(incident_id, user["id"]):
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    service.join_incident(incident_id, user["id"])

    stream = (
        service.sse_frame(event)
        for event in service.stream_chat(incident_id, body.message, user["id"])
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Evita l'accumulo nei proxy.
        },
    )
