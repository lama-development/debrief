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
from datetime import datetime, timezone

# Tipi di evento che Agno emette durante lo streaming di un agente: contenuto
# (token), completamento, inizio chiamata a un tool. Li riconosciamo con isinstance.
from agno.run.agent import RunContentEvent, RunCompletedEvent, ToolCallStartedEvent

from debrief import database as db
from debrief.agents.orchestrator import create_router_agent, route_message
from debrief.agents.triage import create_triage_agent, run_triage, validate_teams
from debrief.agents.investigator import create_investigator_agent, build_investigation_prompt
from debrief.agents.resolver import create_resolver_agent, build_resolution_prompt
from debrief.rag.indexer import get_db, add_past_incident, add_verified_solution, _build_incident_text
from debrief.schemas import AgentRole, PostMortem, Severity, TimelineEvent
from debrief.tools.embedding import embed_text


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
TRANSITIONS: dict[str, dict[str, str]] = {
    "TRIAGE_CLASSIFIED":          {"declared": "active", "awaiting_details": "active"},
    "TRIAGE_NEEDS_CLARIFICATION": {"declared": "awaiting_details", "awaiting_details": "awaiting_details"},
    "RESOLUTION_STARTED":         {"active": "in_resolution", "awaiting_details": "in_resolution",
                                "in_resolution": "in_resolution"},
    "RESOLVED":                   {"active": "resolved", "in_resolution": "resolved",
                                "awaiting_details": "resolved"},
    "ARCHIVED":                   {"resolved": "archived"},
    "REOPENED":                   {"resolved": "active"},
}

# Eventi prodotti automaticamente dall'attività degli agenti (durante la chat).
AUTOMATIC_EVENTS = {"TRIAGE_CLASSIFIED", "TRIAGE_NEEDS_CLARIFICATION", "RESOLUTION_STARTED"}
# Eventi che richiedono un'azione esplicita dell'utente/API (mai dalla chat).
EXPLICIT_EVENTS = {"RESOLVED", "ARCHIVED", "REOPENED"}


def advance_status(current: str, event: str) -> str:
    """Restituisce il nuovo stato per l'evento dato, o `current` invariato se
    la transizione non è consentita dallo stato corrente."""
    # Doppio .get con default:
    #   TRANSITIONS.get(event, {})  → la mappa dell'evento, o {} se evento ignoto
    #   .get(current, current)      → il nuovo stato, o `current` se la transizione
    #                                 non è prevista da questo stato.
    # Risultato: una transizione non valida NON cambia nulla (no eccezioni).
    return TRANSITIONS.get(event, {}).get(current, current)


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

        status = incident["status"]
        description = incident["description"]

        # 1. Persisti il messaggio dell'utente in timeline.
        db.add_timeline_event(incident_id, "message", user_id, message)

        # 2. Routing (bloccante, veloce: piccola decisione JSON). Emettiamo subito
        #    un evento "routing" così la UI può mostrare "sto pensando con X".
        router = create_router_agent()
        decision = route_message(router, message, status, description)
        yield {"type": "routing", "agent": decision.agent.value, "reason": decision.reason}

        # 3-4. Esegui l'agente scelto. `yield from sotto_generatore` inoltra al
        #      chiamante TUTTI gli eventi prodotti dal sotto-generatore e, alla fine,
        #      cattura il valore che quello RESTITUISCE con `return` (qui: il nome
        #      dell'evento di transizione di stato, o None). È il modo elegante per
        #      comporre generatori.
        if decision.agent == AgentRole.TRIAGE:
            event_name = yield from _stream_triage(incident_id, message)
        elif decision.agent == AgentRole.INVESTIGATOR:
            event_name = yield from _stream_investigator(incident_id, message, description)
        elif decision.agent == AgentRole.RESOLVER:
            event_name = yield from _stream_resolver(incident_id, message, description)
        else:  # AgentRole.NONE → nessun agente da eseguire
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


def _stream_triage(incident_id: str, message: str):
    """Triage: output STRUTTURATO, quindi gira bloccante (non si fa token streaming
    di un oggetto Pydantic). Emette i dati strutturati + il summary testuale, poi
    persiste la classificazione. Restituisce l'evento di transizione."""
    teams, valid_ids = db.get_teams()
    agent = create_triage_agent(teams)
    triage = run_triage(agent, message)

    if triage is None:
        text = "Impossibile classificare l'incidente. Riprova con una descrizione più dettagliata."
        yield {"type": "token", "content": text}
        db.add_timeline_event(incident_id, "triage", "triage", text)
        return None  # `return None` da un generatore = valore catturato dal `yield from`: nessuna transizione

    triage = validate_teams(triage, valid_ids)
    # .model_dump(mode="json") = metodo Pydantic che converte l'oggetto in un dict
    # JSON-compatibile (es. gli Enum diventano stringhe, le date diventano testo).
    # Emettiamo un evento "triage" con i dati STRUTTURATI: la UI può disegnarci una card.
    yield {"type": "triage", "data": triage.model_dump(mode="json")}

    if triage.needs_clarification:
        questions = "\n".join(
            f"{i + 1}. {q}" for i, q in enumerate(triage.clarifying_questions)
        )
        text = f"{triage.summary}\n\nHo bisogno di alcune informazioni aggiuntive:\n{questions}"
    else:
        text = triage.summary
    # Emettiamo anche il testo (summary) come evento "token" da mostrare in chat.
    yield {"type": "token", "content": text}

    # Persisti la classificazione prodotta dal triage. .value estrae la stringa dall'Enum.
    db.update_incident_classification(
        incident_id, triage.title, triage.category.value, triage.severity.value
    )
    # Un evento di timeline per ogni team coinvolto (tracciabilità).
    for team_id in triage.suggested_teams:
        db.add_timeline_event(incident_id, "involvement", "triage", team_id)
    db.add_timeline_event(incident_id, "triage", "triage", text)

    # Restituiamo il nome della transizione: classificato OK vs servono dettagli.
    return "TRIAGE_NEEDS_CLARIFICATION" if triage.needs_clarification else "TRIAGE_CLASSIFIED"


def _stream_investigator(incident_id: str, message: str, description: str):
    """Investigator: prosa, token streaming reale. Non cambia lo stato."""
    agent = create_investigator_agent()
    prompt = build_investigation_prompt(message, description)
    # yield from: inoltra tutti gli eventi token/tool E cattura il testo completo
    # accumulato (quello che _stream_agent_prose restituisce con `return full`).
    full = yield from _stream_agent_prose(agent, prompt)
    db.add_timeline_event(incident_id, "message", "investigator", full)
    return None   # l'indagine non fa avanzare lo stato dell'incidente


def _stream_resolver(incident_id: str, message: str, description: str):
    """Resolver: prosa, token streaming reale. Porta lo stato a in_resolution."""
    agent = create_resolver_agent()
    prompt = build_resolution_prompt(description, f"User request: {message}")
    full = yield from _stream_agent_prose(agent, prompt)
    db.add_timeline_event(incident_id, "resolution", "resolver", full)
    return "RESOLUTION_STARTED"   # proporre una soluzione porta a 'in_resolution'


def _stream_agent_prose(agent, prompt: str):
    """Itera `agent.run(stream=True)` inoltrando i delta come eventi 'token'
    (e i tool call come eventi 'tool', opzionali per la UX). Restituisce il testo
    completo accumulato, da persistere in timeline."""
    full = ""   # qui accumuliamo l'intera risposta pezzo per pezzo
    try:
        # Con stream=True, agent.run NON restituisce un valore unico ma è ITERABILE:
        # produce una sequenza di eventi via via che il modello genera. Il for li
        # consuma uno a uno.
        for ev in agent.run(prompt, stream=True, stream_events=True):
            if isinstance(ev, ToolCallStartedEvent):
                # L'agente sta chiamando un tool di ricerca. getattr(obj, "attr",
                # default) legge un attributo in modo sicuro (default se assente).
                name = getattr(ev.tool, "tool_name", None) if ev.tool else None
                if name:
                    yield {"type": "tool", "name": name}   # la UI può mostrare "🔍 sto cercando..."
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
    return full


# ---------------------------------------------------------------------------
# Ciclo di vita dell'incidente (non-streaming)
# ---------------------------------------------------------------------------

def create_incident(description: str, created_by: str) -> dict:
    """Crea un incidente in stato 'declared'. La classificazione (triage) NON
    avviene qui: il client apre la chat con la descrizione come primo messaggio,
    e il router (declared -> triage) la classifica. Così tutto il lavoro degli
    agenti passa da un unico percorso (stream_chat)."""
    return db.create_incident(description, created_by)


def list_incidents(status: str | None = None, limit: int = 100) -> list[dict]:
    return db.list_incidents(status=status, limit=limit)


def get_incident_detail(incident_id: str) -> dict | None:
    """Incidente completo: campi + timeline + remediation + post-mortem."""
    incident = db.get_incident(incident_id)
    if incident is None:
        return None
    # `**incident` "spacchetta" tutte le chiavi dell'incidente dentro questo nuovo
    # dict, a cui aggiungiamo le tre liste correlate. È un modo compatto per dire
    # "tutti i campi dell'incidente, più questi altri tre".
    return {
        **incident,
        "timeline": db.get_timeline(incident_id),
        "remediation": db.get_remediation(incident_id),
        "post_mortem": db.get_post_mortem(incident_id),
    }


def resolve_incident(incident_id: str, resolution_summary: str, provided_by: str,
                    verified_solution: str | None = None) -> dict:
    """Chiude un incidente (azione esplicita). Genera il post-mortem e lancia il
    loop di apprendimento: re-indicizza l'incidente risolto e, se è stata fornita
    una soluzione umana, la indicizza come fonte verificata ad alta priorità.

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

    # Post-mortem: lo costruiamo e lo salviamo come JSON.
    post_mortem = _build_post_mortem(incident, resolution_summary)
    db.save_post_mortem(incident_id, json.dumps(post_mortem, ensure_ascii=False))

    # Loop di apprendimento: re-indicizziamo l'incidente risolto in LanceDB (append)
    # così diventa subito ricercabile dagli agenti per i casi futuri.
    _index_resolved_incident(incident, resolution_summary)
    # Se è stata fornita anche una soluzione umana, la indicizziamo come fonte
    # verificata ad alta priorità.
    if verified_solution:
        _index_verified_solution(incident_id, incident, verified_solution, provided_by)

    # Rileggiamo l'incidente aggiornato. get_incident è tipato "dict | None", ma qui
    # esiste di sicuro (l'abbiamo appena modificato): l'assert lo comunica al
    # type-checker, "restringendo" il tipo a dict.
    updated = db.get_incident(incident_id)
    assert updated is not None
    return updated


# archive_incident e reopen_incident sono "scorciatoie": delegano entrambe alla
# stessa logica generica, passando solo il nome dell'evento. Evita codice duplicato.
def archive_incident(incident_id: str) -> dict:
    return _explicit_transition(incident_id, "ARCHIVED")


def reopen_incident(incident_id: str) -> dict:
    return _explicit_transition(incident_id, "REOPENED")


def _explicit_transition(incident_id: str, event: str) -> dict:
    """Applica un evento esplicito (ARCHIVED/REOPENED) con guardia di transizione."""
    incident = db.get_incident(incident_id)
    if incident is None:
        raise ValueError(f"Incident {incident_id} not found")
    new_status = advance_status(incident["status"], event)
    # Stessa guardia di resolve: se la transizione non è permessa, errore (→ HTTP 409).
    if new_status == incident["status"]:
        raise ValueError(f"Cannot apply {event} from status '{incident['status']}'")
    db.set_incident_status(incident_id, new_status)
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
        "by_category": db.count_by_column("category"),
        "mttr_seconds": db.mttr_seconds(),
        # sum(dict.values()) somma tutti i conteggi → totale incidenti.
        "total": sum(by_status.values()),
    }


# ---------------------------------------------------------------------------
# Helper interni: post-mortem + indicizzazione
# ---------------------------------------------------------------------------

def _build_post_mortem(incident: dict, resolution_summary: str) -> dict:
    """Assembla un PostMortem minimale (v1) a partire da incidente + timeline.
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

    pm = PostMortem(
        incident_id=incident["id"],
        title=incident["title"],
        severity=severity,
        timeline=timeline,
        impact="",
        detection="",
        root_cause="",
        # `[x] if x else []` → lista con un elemento se c'è un riepilogo, altrimenti vuota.
        resolution_steps=[resolution_summary] if resolution_summary else [],
        action_items=[],
        references=[],
    )
    # Restituiamo un dict JSON-compatibile (così il chiamante può serializzarlo).
    return pm.model_dump(mode="json")


def _index_resolved_incident(incident: dict, resolution_summary: str) -> None:
    """Re-indicizza l'incidente risolto in 'past_incidents' (append) così che sia
    immediatamente ricercabile dagli agenti. Stesso testo embeddato del seed."""
    inc_for_index = {
        "id": incident["id"],
        "title": incident["title"],
        "category": incident.get("category") or "",
        "severity": incident.get("severity") or "",
        "description": incident["description"],
        "root_cause": "",
        "resolution_steps": [resolution_summary] if resolution_summary else [],
    }
    # Costruiamo il testo, lo embeddiamo e lo appendiamo a 'past_incidents'.
    vector = embed_text(_build_incident_text(inc_for_index))
    add_past_incident(get_db(), inc_for_index, vector)


def _index_verified_solution(incident_id: str, incident: dict, solution_text: str,
                            provided_by: str) -> None:
    """Indicizza una soluzione fornita da un umano come fonte verificata.
    L'id `VS-<incident_id>` è univoco per incidente e tracciabile."""
    solution = {
        "id": f"VS-{incident_id}",          # id univoco e tracciabile (VS = Verified Solution)
        "incident_id": incident_id,
        "problem_context": incident["description"],
        "solution": solution_text,
        "provided_by": provided_by,
    }
    # Embeddiamo contesto + soluzione insieme e la appendiamo a 'verified_solutions'.
    text = solution["problem_context"] + " " + solution["solution"]
    add_verified_solution(get_db(), solution, embed_text(text))
