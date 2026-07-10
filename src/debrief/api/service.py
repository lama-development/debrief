"""
service.py - Livello di servizio tra le route HTTP e il resto del sistema.

È l'UNICO posto che conosce:
- la macchina a stati dell'incidente (transizioni consentite);
- la sequenza di persistenza di ogni turno di chat;
- il loop di apprendimento (re-indicizzazione in LanceDB alla risoluzione).

Le route restano sottili: parse della richiesta -> chiamata al servizio -> risposta.
La chat è uno *streaming*: `stream_chat` è un generatore sincrono che produce eventi
(dict). FastAPI esegue i generatori sincroni in un threadpool, quindi le chiamate
bloccanti (sqlite, sentence-transformers, LanceDB) non bloccano l'event loop e non
serve un refactor async.
"""

import json
import logging
import re
from datetime import datetime, timezone

# Tipi di evento che Agno emette durante lo streaming di un agente: contenuto
# (token), completamento, inizio chiamata a un tool. Li riconosciamo con isinstance.
from agno.run.agent import RunContentEvent, RunCompletedEvent, ToolCallCompletedEvent, ToolCallStartedEvent

from debrief import database as db
from debrief.agents.orchestrator import create_router_agent, route_message
from debrief.agents.triage import create_triage_agent, run_triage, validate_teams
from debrief.agents.investigator import create_investigator_agent, build_investigation_prompt
from debrief.agents.resolver import create_resolver_agent, build_resolution_prompt
from debrief.api.lifecycle import advance_status
from debrief.rag.indexer import get_db, upsert_past_incident, _build_incident_text
from debrief.schemas import AgentRole, ClassificationOverrideRequest, OverrideParams, DebriefReport, RoutingDecision, Severity, TimelineEvent
from debrief.tools.embedding import embed_text


logger = logging.getLogger(__name__)

DEBRIEF_MENTION_RE = re.compile(r"(?<![\w@])@debrief\b", re.IGNORECASE)
DEBRIEF_HELP_TEXT = (
    "Mi spiace, non posso aiutarti con questa richiesta. Però sono qui per darti "
    "una mano con l'incidente: posso cercare casi simili, analizzare le possibili "
    "cause o suggerirti come intervenire."
)


# ---------------------------------------------------------------------------
# Macchina a stati
# ---------------------------------------------------------------------------
# Le transizioni sono keyed per *evento semantico* e guardate da una tabella:
# una transizione non prevista dallo stato corrente viene ignorata (lo stato
# resta invariato). Così, ad es., un messaggio al resolver su un incidente già
# 'resolved' non lo riapre.

# Struttura: dizionario di dizionari. Per ogni evento, una mappa
# {stato_di_partenza: stato_di_arrivo}. Se lo stato corrente non è tra le chiavi
# interne, la transizione semplicemente non avviene (vedi advance_status).
# evento -> {stato_di_partenza: stato_di_arrivo}
# Ciclo di vita a 3 stati: open -> active -> resolved (riapribile).
# ---------------------------------------------------------------------------
# Helper SSE
# ---------------------------------------------------------------------------

def sse_frame(event: dict) -> str:
    """Serializza un evento come frame SSE (`data: <json>\\n\\n`).
    La route fa semplicemente: `(sse_frame(e) for e in stream_chat(...))`."""
    # SSE (Server-Sent Events) è il protocollo con cui il server "spinge" eventi al
    # browser su una singola connessione HTTP. Il formato richiede: la riga
    # "data: <contenuto>" seguita da DUE a-capo (\n\n) che segnano la fine del frame.
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Chat in streaming (il cuore)
# ---------------------------------------------------------------------------

def stream_chat(incident_id: str, message: str, user_id: str):
    """Generatore sincrono che orchestra un turno di chat e produce eventi dict.

    NOTA SUI GENERATORI (concetto Python chiave qui):
    Una funzione che contiene `yield` non restituisce un valore unico: diventa un
    GENERATORE. Ogni `yield X` "consegna" X al chiamante e METTE IN PAUSA la
    funzione; alla richiesta successiva riparte da dove si era fermata. Così
    possiamo produrre eventi UNO ALLA VOLTA man mano che arrivano, invece di
    aspettare la fine. È ciò che permette alla chat di apparire "in tempo reale".

    Sequenza: carica incidente -> persiste messaggio utente -> routing (bloccante)
    -> agente (triage bloccante / investigator+resolver in streaming) -> persiste
    la risposta -> applica la transizione di stato -> 'done'.

    Schema eventi: routing | tool | token | triage | done | error.
    """
    try:
        incident = db.get_incident(incident_id)
        if incident is None:
            # yield "consegna" un evento di errore e poi `return` chiude il generatore.
            yield {"type": "error", "message": f"Incident {incident_id} not found"}
            return

        db.add_incident_participant(incident_id, user_id)

        status = incident["status"]
        description = incident["description"]
        conversation_context = _conversation_context(incident_id)

        # 1. Persisti il messaggio dell'utente in timeline.
        db.add_timeline_event(incident_id, "message", user_id, message)

        # I messaggi della chat appartengono prima di tutto al team. Dopo il triage
        # iniziale Debrief interviene solo quando viene menzionato esplicitamente.
        # Finché l'incidente è "open", invece, ogni risposta completa il normale
        # ciclo di chiarimenti del triage senza obbligare l'utente a ripetere la mention.
        bot_requested = status == "open" or DEBRIEF_MENTION_RE.search(message) is not None
        if not bot_requested:
            yield {"type": "done", "status": status, "incident_id": incident_id}
            return

        # 2. Routing (bloccante, veloce: piccola decisione JSON). Emettiamo subito
        #    un evento "routing" così la UI può mostrare "sto pensando con X".
        router = create_router_agent()
        decision = route_message(router, message, status, description)
        yield {"type": "routing", "agent": decision.agent.value, "reason": decision.reason}

        # 3-4. Esegui l'agente scelto.
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
        else:  # Mention valida, ma nessun agente specialistico necessario.
            yield {"type": "token", "content": DEBRIEF_HELP_TEXT}
            db.add_timeline_event(incident_id, "message", "debrief", DEBRIEF_HELP_TEXT)
            event_name = None

        # 5. Applica l'eventuale transizione di stato (solo eventi automatici dalla chat).
        new_status = status
        if event_name:
            new_status = advance_status(status, event_name)
            # Scriviamo nel DB solo se lo stato è davvero cambiato.
            if new_status != status:
                db.set_incident_status(incident_id, new_status)

        # 6. Evento finale: segnala alla UI che il turno è concluso e qual è il nuovo stato.
        yield {"type": "done", "status": new_status, "incident_id": incident_id}

    except Exception as e:
        # Qualsiasi errore diventa un evento "error" invece di rompere lo stream.
        yield {"type": "error", "message": str(e)}


def _stream_triage(incident_id: str, message: str, description: str = "",
                   conversation_context: str = ""):
    """Triage: output strutturato. Restituisce tupla (event_name, triage_result)."""
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
    """Investigator: token streaming. Restituisce il testo completo per il resolver."""
    agent = create_investigator_agent()
    incident_context = description
    if conversation_context:
        incident_context += f"\n\n<conversation_history>\n{conversation_context}\n</conversation_history>"
    prompt = build_investigation_prompt(message, incident_context, triage_context=triage_context)
    full, _ = yield from _stream_agent_prose(agent, prompt)
    db.add_timeline_event(incident_id, "message", "investigator", full)
    return full  # passato al resolver nella pipeline automatica


def _stream_resolver(incident_id: str, message: str, description: str,
                     triage_context: str = "", investigation_summary: str = "",
                     conversation_context: str = ""):
    """Resolver: token streaming. Garantisce lo stato 'active'."""
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
        reason = "Nessuna fonte applicabile trovata: è richiesto il contributo di una persona esperta."
        db.add_timeline_event(incident_id, "escalation", "resolver", reason)
        yield {
            "type": "human_help_required",
            "data": {"problem_context": description, "reason": reason},
        }
    return "RESOLUTION_STARTED"


def _stream_override(decision: RoutingDecision):
    """Propone un override strutturato senza applicarlo: aspetta conferma dal frontend.
    Valida team e severità rispetto al catalogo; emette override_proposed se valido."""
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
    """Itera `agent.run(stream=True)` inoltrando i delta come eventi 'token'
    (e i tool call come eventi 'tool', opzionali per la UX). Restituisce il testo
    completo accumulato, da persistere in timeline."""
    full = ""   # qui accumuliamo l'intera risposta pezzo per pezzo
    tool_calls = 0
    useful_tool_results = 0
    try:
        # Con stream=True, agent.run NON restituisce un valore unico ma è ITERABILE:
        # produce una sequenza di eventi via via che il modello genera. Il for li
        # consuma uno a uno.
        for ev in agent.run(prompt, stream=True, stream_events=True):
            if isinstance(ev, ToolCallStartedEvent):
                tool_calls += 1
                # L'agente sta chiamando un tool di ricerca. getattr(obj, "attr",
                # default) legge un attributo in modo sicuro (default se assente).
                name = getattr(ev.tool, "tool_name", None) if ev.tool else None
                if name:
                    yield {"type": "tool", "name": name}   # la UI può mostrare lo stato di ricerca
            elif isinstance(ev, ToolCallCompletedEvent):
                tool_result = ev.tool.result if ev.tool else None
                content = str(ev.content or tool_result or "").lower()
                no_result_markers = (
                    "no similar past incidents found",
                    "no relevant knowledge base articles found",
                )
                if content and not any(marker in content for marker in no_result_markers):
                    useful_tool_results += 1
            elif isinstance(ev, RunContentEvent):
                # Un "delta" di testo (qualche parola). Lo accumuliamo e lo inoltriamo.
                if ev.content:
                    full += ev.content
                    yield {"type": "token", "content": ev.content}
            elif isinstance(ev, RunCompletedEvent):
                # Evento finale: contiene il testo completo "autorevole". Lo usiamo
                # come versione definitiva (sovrascrive l'accumulo, per sicurezza).
                if ev.content:
                    full = ev.content
    except Exception as e:
        # Se la generazione si interrompe, segnaliamo l'errore in linea senza perdere
        # il testo già prodotto.
        err = f"\n\n[errore durante la generazione: {e}]"
        full += err
        yield {"type": "token", "content": err}
    # Il valore di `return` di un generatore viene raccolto da chi fa `yield from`.
    return full, tool_calls > 0 and useful_tool_results > 0


# ---------------------------------------------------------------------------
# Ciclo di vita dell'incidente (non-streaming)
# ---------------------------------------------------------------------------

def create_incident(description: str, created_by: str) -> dict:
    """Crea un incidente in stato 'open'. La classificazione (triage) NON avviene
    qui: il client apre la chat con la descrizione come primo messaggio, e il
    router (open -> triage) la classifica. Così tutto il lavoro degli agenti passa
    da un unico percorso (stream_chat)."""
    return db.create_incident(description, created_by)


def list_incidents(user_id: str, status: str | None = None, limit: int = 100) -> list[dict]:
    """Elenca le conversazioni dell'utente e gli incidenti seed pubblici."""
    return db.list_user_incidents(user_id, status=status, limit=limit)


def can_access_incident(incident_id: str, user_id: str) -> bool:
    return db.user_can_access_incident(user_id, incident_id)


def join_incident(incident_id: str, user_id: str) -> None:
    """Associa un utente autenticato a una conversazione esistente."""
    if db.get_incident(incident_id) is None:
        raise ValueError(f"Incident {incident_id} not found")
    db.add_incident_participant(incident_id, user_id)


def get_incident_detail(incident_id: str) -> dict | None:
    """Incidente completo: campi + timeline + remediation + debriefing + team correnti."""
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
    """Applica un override umano su severità e/o team. Loga l'azione in timeline.

    Valida team rispetto al catalogo (filtra silenziosamente quelli non validi).
    Solleva ValueError se l'incidente non esiste.
    """
    incident = db.get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")

    _, valid_ids = db.get_teams()

    before_sev = incident.get("severity")
    before_teams = db.get_incident_teams(incident_id)

    if override.severity is not None:
        db.update_incident_severity(incident_id, override.severity.value)

    add_teams = [t for t in override.add_teams if t in valid_ids]
    remove_teams = [t for t in override.remove_teams if t in valid_ids]
    for team_id in add_teams:
        db.add_timeline_event(incident_id, "involvement", actor, team_id)
    for team_id in remove_teams:
        db.add_timeline_event(incident_id, "disinvolvement", actor, team_id)

    log = json.dumps({
        "before": {"severity": before_sev, "teams": before_teams},
        "after": {
            "severity": override.severity.value if override.severity else before_sev,
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
    """Chiude un incidente (azione esplicita). Genera il debriefing e lancia il
    loop di apprendimento re-indicizzando l'incidente risolto.

    Solleva ValueError se la transizione RESOLVED non è consentita dallo stato.
    """
    incident = db.get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")

    # Guardia di stato: se RESOLVED non è una transizione valida dallo stato
    # corrente, advance_status restituisce lo stato invariato → blocchiamo con errore.
    new_status = advance_status(incident["status"], "RESOLVED")
    if new_status == incident["status"]:
        raise ValueError(f"Cannot resolve incident in status '{incident['status']}'")

    # Timestamp UTC formattato come testo "AAAA-MM-GG HH:MM:SS" (strftime = string
    # format time). UTC per avere un riferimento orario univoco.
    resolved_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db.set_incident_status(incident_id, new_status, resolved_at=resolved_at)
    db.add_timeline_event(incident_id, "resolution", provided_by, resolution_summary)

    # Debriefing: lo costruiamo e lo salviamo come JSON.
    debrief_report = _build_debrief_report(incident, resolution_summary)
    db.save_debrief_report(incident_id, json.dumps(debrief_report, ensure_ascii=False))

    # Loop di apprendimento: re-indicizziamo l'incidente risolto in LanceDB (append)
    # così diventa subito ricercabile dagli agenti per i casi futuri.
    try:
        _index_resolved_incident(incident, resolution_summary)
    except Exception:
        # SQLite e' la sorgente di verita': un guasto del vector DB non deve
        # annullare una chiusura gia' persistita correttamente.
        logger.exception("Failed to index resolved incident %s", incident_id)
    # Rileggiamo l'incidente aggiornato. get_incident è tipato "dict | None", ma qui
    # esiste di sicuro (l'abbiamo appena modificato): l'assert lo comunica al
    # type-checker, "restringendo" il tipo a dict.
    updated = db.get_incident(incident_id)
    assert updated is not None
    return updated


# reopen_incident delega alla logica generica di transizione esplicita.
def reopen_incident(incident_id: str, reopened_by: str) -> dict:
    return _explicit_transition(incident_id, "REOPENED", reopened_by)


def _explicit_transition(incident_id: str, event: str, actor: str) -> dict:
    """Applica un evento esplicito (REOPENED) con guardia di transizione."""
    incident = db.get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")
    new_status = advance_status(incident["status"], event)
    # Stessa guardia di resolve: se la transizione non è permessa, errore (→ HTTP 409).
    if new_status == incident["status"]:
        raise ValueError(f"Cannot apply {event} from status '{incident['status']}'")
    db.set_incident_status(incident_id, new_status)
    if event == "REOPENED":
        db.add_timeline_event(incident_id, "reopen", actor, "Incidente riaperto")
    # Come in resolve_incident: l'incidente esiste di sicuro qui (assert = narrowing).
    updated = db.get_incident(incident_id)
    assert updated is not None
    return updated


def get_metrics() -> dict:
    """Metriche per la dashboard: conteggi e MTTR."""
    by_status = db.count_by_column("status")
    return {
        "by_status": by_status,
        "by_severity": db.count_by_column("severity"),
        "mttr_seconds": db.mttr_seconds(),
        # sum(dict.values()) somma tutti i conteggi → totale incidenti.
        "total": sum(by_status.values()),
    }


# ---------------------------------------------------------------------------
# Helper interni: debriefing + indicizzazione
# ---------------------------------------------------------------------------

def _build_debrief_report(incident: dict, resolution_summary: str) -> dict:
    """Assembla un DebriefReport minimale (v1) a partire da incidente + timeline.
    Impact/detection/root_cause non sono derivati automaticamente in questa
    versione; resolution_steps contiene il riepilogo di chiusura fornito."""
    # Severity(stringa) prova a convertire il testo nell'Enum; se il valore è
    # mancante o non valido, ripieghiamo su SEV3 (un default ragionevole).
    try:
        severity = Severity(incident.get("severity"))
    except (ValueError, TypeError):
        severity = Severity.SEV3

    # Ricostruiamo la timeline come lista di oggetti TimelineEvent validati.
    timeline = []
    for row in db.get_timeline(incident["id"]):
        try:
            event = TimelineEvent(
                timestamp=row["timestamp"],
                event_type=row["event_type"],
                # `row["actor"] or ""` → "" se il valore è None (Pydantic vuole str).
                actor=row["actor"] or "",
                content=row["content"] or "",
            )
            timeline.append(event)
        except Exception:
            # `continue` salta all'iterazione successiva: scartiamo gli eventi con
            # dati non validi (es. timestamp non parsabile) invece di bloccare tutto.
            continue

    report = DebriefReport(
        incident_id=incident["id"],
        title=incident["title"],
        severity=severity,
        timeline=timeline,
        resolution=resolution_summary,
    )
    # Restituiamo un dict JSON-compatibile (così il chiamante può serializzarlo).
    return report.model_dump(mode="json")


def _index_resolved_incident(incident: dict, resolution_summary: str) -> None:
    """Re-indicizza l'incidente risolto in 'past_incidents' (append) così che sia
    immediatamente ricercabile dagli agenti. Stesso testo embeddato del seed."""
    inc_for_index = {
        "id": incident["id"],
        "title": incident["title"],
        "severity": incident.get("severity") or "",
        "description": incident["description"],
        "resolution": resolution_summary,
    }
    # Costruiamo il testo, lo embeddiamo e lo appendiamo a 'past_incidents'.
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
