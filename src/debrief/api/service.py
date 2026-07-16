"""Orchestrazione di chat, ciclo di vita e persistenza degli incidenti."""

import json
import logging
import re
from datetime import datetime, timezone

from agno.run.agent import RunContentEvent, RunCompletedEvent, ToolCallCompletedEvent, ToolCallStartedEvent

from debrief import database as db
from debrief.agents.orchestrator import create_router_agent, route_message
from debrief.agents.triage import create_triage_agent, run_triage, validate_teams
from debrief.agents.investigator import create_investigator_agent, build_investigation_prompt
from debrief.agents.resolver import create_resolver_agent, build_resolution_prompt
from debrief.api.lifecycle import advance_status
from debrief.rag.indexer import get_db, upsert_past_incident, _build_incident_text
from debrief.schemas import AgentRole, ClassificationOverrideRequest, DebriefReport, RoutingDecision, Severity, TimelineEvent
from debrief.tools.embedding import embed_text


logger = logging.getLogger(__name__)

DEBRIEF_MENTION_RE = re.compile(r"(?<![\w@])@debrief\b", re.IGNORECASE)
DEBRIEF_HELP_TEXT = (
    "Mi spiace, non posso aiutarti con questa richiesta. Però sono qui per darti "
    "una mano con l'incidente: posso cercare casi simili, analizzare le possibili "
    "cause o suggerirti come intervenire."
)


# Supporto SSE

def sse_frame(event: dict) -> str:
    """Serializza un evento SSE e lo termina con una riga vuota."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# Chat con risposta progressiva

def stream_chat(incident_id: str, message: str, user_id: str):
    """Orchestra un turno e produce eventi compatibili con SSE."""
    try:
        incident = db.get_incident(incident_id)
        if incident is None:
            yield {"type": "error", "message": f"Incident {incident_id} not found"}
            return

        db.add_incident_participant(incident_id, user_id)

        status = incident["status"]
        description = incident["description"]
        conversation_context = _conversation_context(incident_id)

        db.add_timeline_event(incident_id, "message", user_id, message)

        # Dopo il triage Debrief risponde solo se menzionato.
        bot_requested = status == "open" or DEBRIEF_MENTION_RE.search(message) is not None
        if not bot_requested:
            yield {"type": "done", "status": status, "incident_id": incident_id}
            return

        # La decisione viene inviata subito, così la UI mostra l'agente attivo.
        router = create_router_agent()
        decision = route_message(router, message, status, description)
        yield {"type": "routing", "agent": decision.agent.value, "reason": decision.reason}

        # Tutti gli agenti vengono adattati allo stesso protocollo di eventi.
        if decision.agent == AgentRole.TRIAGE:
            event_name, _ = yield from _stream_triage(
                incident_id, message, description, conversation_context
            )

        elif decision.agent == AgentRole.INVESTIGATOR:
            yield from _stream_investigator(
                incident_id, message, description,
                conversation_context=conversation_context,
            )
            event_name = None
        elif decision.agent == AgentRole.RESOLVER:
            event_name = yield from _stream_resolver(
                incident_id, message, description,
                conversation_context=conversation_context,
            )
        elif decision.agent == AgentRole.OVERRIDE:
            yield from _stream_override(decision)
            event_name = None
        else:
            yield {"type": "token", "content": DEBRIEF_HELP_TEXT}
            db.add_timeline_event(incident_id, "message", "debrief", DEBRIEF_HELP_TEXT)
            event_name = None

        # Solo un evento semantico valido può avanzare la macchina a stati.
        new_status = status
        if event_name:
            new_status = advance_status(status, event_name)
            if new_status != status:
                db.set_incident_status(incident_id, new_status)

        yield {"type": "done", "status": new_status, "incident_id": incident_id}

    except Exception as e:
        # Gli errori restano nel protocollo del flusso.
        yield {"type": "error", "message": str(e)}


def _stream_triage(incident_id: str, message: str, description: str = "",
                   conversation_context: str = ""):
    """Esegue il triage e restituisce evento e risultato strutturato."""
    teams, valid_ids = db.get_teams()
    agent = create_triage_agent(teams)
    triage_input = message
    if conversation_context:
        triage_input = (
            f"Descrizione originale: {description}\n\n"
            f"Cronologia precedente:\n{conversation_context}\n\n"
            f"Nuovo messaggio: {message}"
        )
    triage = run_triage(agent, triage_input)

    if triage is None:
        text = "Impossibile classificare l'incidente. Riprova con una descrizione più dettagliata."
        yield {"type": "token", "content": text}
        db.add_timeline_event(incident_id, "triage", "triage", text)
        return None, None

    triage = validate_teams(triage, valid_ids)
    yield {"type": "triage", "data": triage.model_dump(mode="json")}

    if triage.needs_clarification:
        questions = "\n".join(
            f"{i + 1}. {q}" for i, q in enumerate(triage.clarifying_questions)
        )
        text = f"{triage.summary}\n\nHo bisogno di alcune informazioni aggiuntive:\n{questions}"
    else:
        text = triage.summary
    yield {"type": "token", "content": text}

    db.update_incident_classification(incident_id, triage.title, triage.severity.value)
    for team_id in triage.suggested_teams:
        db.add_timeline_event(incident_id, "involvement", "triage", team_id)
    db.add_timeline_event(incident_id, "triage", "triage", text)

    if triage.needs_clarification:
        return "TRIAGE_NEEDS_CLARIFICATION", triage
    return "TRIAGE_CLASSIFIED", triage


def _stream_investigator(incident_id: str, message: str, description: str,
                         triage_context: str = "", conversation_context: str = ""):
    """Trasmette l'indagine progressivamente e ne restituisce il testo completo."""
    agent = create_investigator_agent()
    incident_context = description
    if conversation_context:
        incident_context += f"\n\n<conversation_history>\n{conversation_context}\n</conversation_history>"
    prompt = build_investigation_prompt(message, incident_context, triage_context=triage_context)
    full, _ = yield from _stream_agent_prose(agent, prompt)
    db.add_timeline_event(incident_id, "message", "investigator", full)
    return full


def _stream_resolver(incident_id: str, message: str, description: str,
                     triage_context: str = "", investigation_summary: str = "",
                     conversation_context: str = ""):
    """Trasmette progressivamente i passi di risoluzione."""
    agent = create_resolver_agent()
    additional_parts = []
    if triage_context:
        additional_parts.append(f"Classification context:\n{triage_context}")
    if message:
        additional_parts.append(f"User request: {message}")
    if conversation_context:
        additional_parts.append(f"Conversation history:\n{conversation_context}")
    additional = "\n\n".join(additional_parts)
    prompt = build_resolution_prompt(description, additional_context=additional,
                                     investigation_summary=investigation_summary)
    full, has_evidence = yield from _stream_agent_prose(agent, prompt)
    db.add_timeline_event(incident_id, "resolution", "resolver", full)
    if not has_evidence:
        # Senza fonti RAG utili la proposta richiede una verifica umana.
        reason = "Nessuna fonte applicabile trovata: è richiesto il contributo di una persona esperta."
        db.add_timeline_event(incident_id, "escalation", "resolver", reason)
        yield {
            "type": "human_help_required",
            "data": {"problem_context": description, "reason": reason},
        }
    return "RESOLUTION_STARTED"


def _stream_override(decision: RoutingDecision):
    """Valida e propone una modifica manuale senza applicarla."""
    params = decision.override_params
    if params is None:
        yield {"type": "token", "content": "Non riesco a capire cosa vuoi modificare. Specifica severità (es. 'alza a SEV1') o team (es. 'coinvolgi PRODUCTION')."}
        return

    _, valid_ids = db.get_teams()
    add_teams = [t for t in params.add_teams if t in valid_ids]
    remove_teams = [t for t in params.remove_teams if t in valid_ids]
    severity_val = params.severity.value if params.severity else None

    if severity_val is None and not add_teams and not remove_teams:
        yield {
            "type": "token",
            "content": f"Nessuna modifica valida riconosciuta. Team disponibili: {', '.join(sorted(valid_ids))}",
        }
        return

    yield {
        "type": "override_proposed",
        "data": {
            "severity": severity_val,
            "add_teams": add_teams,
            "remove_teams": remove_teams,
            "description": params.description or decision.reason,
        },
    }


def _conversation_context(incident_id: str, limit: int = 12) -> str:
    """Formatta gli ultimi eventi conversazionali per riprendere una sessione."""
    relevant_types = {"message", "triage", "resolution", "override"}
    events = [
        event for event in db.get_timeline(incident_id)
        if event["event_type"] in relevant_types and event.get("content")
    ][-limit:]
    return "\n".join(
        f"{event.get('actor') or 'system'}: {event['content']}"
        for event in events
    )


def _stream_agent_prose(agent, prompt: str):
    """Inoltra token e chiamate agli strumenti, restituendo testo ed evidenza RAG."""
    full = ""
    tool_calls = 0
    useful_tool_results = 0
    try:
        for ev in agent.run(prompt, stream=True, stream_events=True):
            if isinstance(ev, ToolCallStartedEvent):
                tool_calls += 1
                name = getattr(ev.tool, "tool_name", None) if ev.tool else None
                if name:
                    yield {"type": "tool", "name": name}
            elif isinstance(ev, ToolCallCompletedEvent):
                tool_result = ev.tool.result if ev.tool else None
                content = str(ev.content or tool_result or "").lower()
                # Una chiamata vuota non è considerata evidenza per la risoluzione.
                no_result_markers = (
                    "no similar past incidents found",
                    "no relevant knowledge base articles found",
                )
                if content and not any(marker in content for marker in no_result_markers):
                    useful_tool_results += 1
            elif isinstance(ev, RunContentEvent):
                if ev.content:
                    full += ev.content
                    yield {"type": "token", "content": ev.content}
            elif isinstance(ev, RunCompletedEvent):
                # Il contenuto finale è la versione autorevole.
                if ev.content:
                    full = ev.content
    except Exception as e:
        # Conserva anche il testo prodotto prima dell'errore.
        err = f"\n\n[errore durante la generazione: {e}]"
        full += err
        yield {"type": "token", "content": err}
    return full, tool_calls > 0 and useful_tool_results > 0


# Ciclo di vita

def create_incident(description: str, created_by: str) -> dict:
    """Crea un incidente `open`; il triage avviene in chat."""
    return db.create_incident(description, created_by)


def list_incidents(user_id: str, status: str | None = None, limit: int = 100) -> list[dict]:
    """Elenca le conversazioni dell'utente e gli incidenti dimostrativi accessibili."""
    return db.list_user_incidents(user_id, status=status, limit=limit)


def can_access_incident(incident_id: str, user_id: str) -> bool:
    return db.user_can_access_incident(user_id, incident_id)


def join_incident(incident_id: str, user_id: str) -> None:
    """Associa un utente autenticato a una conversazione esistente."""
    if db.get_incident(incident_id) is None:
        raise ValueError(f"Incident {incident_id} not found")
    db.add_incident_participant(incident_id, user_id)


def get_incident_detail(incident_id: str) -> dict | None:
    """Restituisce campi, timeline, debriefing, partecipanti e team correnti."""
    incident = db.get_incident(incident_id)
    if incident is None:
        return None
    return {
        **incident,
        "involved_teams": db.get_incident_teams(incident_id),
        "timeline": db.get_timeline(incident_id),
        "debrief_report": db.get_debrief_report(incident_id),
        "participants": db.get_incident_participants(incident_id),
    }


def override_classification(
    incident_id: str,
    override: ClassificationOverrideRequest,
    actor: str,
) -> dict:
    """Applica e registra una modifica manuale validata."""
    incident = db.get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")

    _, valid_ids = db.get_teams()

    before_sev = incident.get("severity")
    before_teams = db.get_incident_teams(incident_id)

    severity_changed = (
        override.severity is not None and override.severity.value != before_sev
    )
    if severity_changed:
        db.update_incident_severity(incident_id, override.severity.value)

    # Ignora duplicati e operazioni senza effetto, rendendo sicuri i nuovi tentativi.
    current_teams = set(before_teams)
    add_teams = list(dict.fromkeys(
        t for t in override.add_teams if t in valid_ids and t not in current_teams
    ))
    remove_teams = list(dict.fromkeys(
        t for t in override.remove_teams if t in valid_ids and t in current_teams
    ))

    if not severity_changed and not add_teams and not remove_teams:
        return incident

    for team_id in add_teams:
        db.add_timeline_event(incident_id, "involvement", actor, team_id)
    for team_id in remove_teams:
        db.add_timeline_event(incident_id, "disinvolvement", actor, team_id)

    log = json.dumps({
        "before": {"severity": before_sev, "teams": before_teams},
        "after": {
            "severity": override.severity.value if severity_changed else before_sev,
            "add_teams": add_teams,
            "remove_teams": remove_teams,
        },
        "reason": override.reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False)
    db.add_timeline_event(incident_id, "override", actor, log)

    updated = db.get_incident(incident_id)
    assert updated is not None
    return updated


def resolve_incident(incident_id: str, resolution_summary: str, provided_by: str) -> dict:
    """Chiude l'incidente, salva il debriefing e aggiorna il RAG."""
    incident = db.get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")

    new_status = advance_status(incident["status"], "RESOLVED")
    if new_status == incident["status"]:
        raise ValueError(f"Cannot resolve incident in status '{incident['status']}'")

    resolved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db.set_incident_status(incident_id, new_status, resolved_at=resolved_at)
    db.add_timeline_event(incident_id, "resolution", provided_by, resolution_summary)

    debrief_report = _build_debrief_report(incident, resolution_summary)
    db.save_debrief_report(incident_id, json.dumps(debrief_report, ensure_ascii=False))

    # Un errore nell'indice vettoriale non annulla la chiusura salvata in SQLite.
    try:
        _index_resolved_incident(incident, resolution_summary)
    except Exception:
        logger.exception("Failed to index resolved incident %s", incident_id)
    updated = db.get_incident(incident_id)
    assert updated is not None
    return updated


def reopen_incident(incident_id: str, reopened_by: str) -> dict:
    """Riapre un incidente risolto con guardia di transizione."""
    incident = db.get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")
    new_status = advance_status(incident["status"], "REOPENED")
    if new_status == incident["status"]:
        raise ValueError(f"Cannot apply REOPENED from status '{incident['status']}'")
    db.set_incident_status(incident_id, new_status)
    db.add_timeline_event(incident_id, "reopen", reopened_by, "Incidente riaperto")
    updated = db.get_incident(incident_id)
    assert updated is not None
    return updated


# Debriefing e indicizzazione

def _build_debrief_report(incident: dict, resolution_summary: str) -> dict:
    """Assembla il report minimale da incidente e timeline."""
    # Usa SEV3 se la severità storica è assente o non valida.
    try:
        severity = Severity(incident.get("severity"))
    except (ValueError, TypeError):
        severity = Severity.SEV3

    timeline = []
    for row in db.get_timeline(incident["id"]):
        try:
            event = TimelineEvent(
                timestamp=row["timestamp"],
                event_type=row["event_type"],
                actor=row["actor"] or "",
                content=row["content"] or "",
            )
            timeline.append(event)
        except Exception:
            # Un evento storico malformato non blocca l'intero report.
            continue

    report = DebriefReport(
        incident_id=incident["id"],
        title=incident["title"],
        severity=severity,
        timeline=timeline,
        resolution=resolution_summary,
    )
    return report.model_dump(mode="json")


def _index_resolved_incident(incident: dict, resolution_summary: str) -> None:
    """Aggiorna l'incidente nell'indice `past_incidents`."""
    inc_for_index = {
        "id": incident["id"],
        "title": incident["title"],
        "severity": incident.get("severity") or "",
        "description": incident["description"],
        "resolution": resolution_summary,
    }
    vector = embed_text(_build_incident_text(inc_for_index))
    upsert_past_incident(get_db(), inc_for_index, vector)


def capture_human_solution(incident_id: str, solution_text: str,
                           provided_by: str) -> dict:
    """Salva una soluzione umana e prova a renderla subito recuperabile dal RAG."""
    incident = db.get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")
    event_id = db.add_timeline_event(
        incident_id,
        "human_solution",
        provided_by,
        f"Soluzione umana acquisita: {solution_text}",
    )
    try:
        _index_resolved_incident(incident, solution_text)
    except Exception:
        logger.exception("Failed to index human solution for incident %s", incident_id)
    return {
        "id": event_id,
        "incident_id": incident_id,
        "solution": solution_text,
        "provided_by": provided_by,
    }
