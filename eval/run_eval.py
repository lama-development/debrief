"""
run_eval.py - Valutazione automatica del sistema multi-agente Debrief.

Esegue quattro suite di test, una per ciascuna capacita' chiave del sistema:

  1. triage    - accuratezza di severita' del Triage Agent
  2. routing   - correttezza dell'Orchestrator (router LLM) nello smistare i messaggi
  3. retrieval - qualita' del RAG (precision/recall/MRR sui cluster di ground truth)
  4. injection - robustezza alla prompt injection (red-team, metrica di sicurezza)

I pochi casi rappresentativi e la ground truth del retrieval stanno nell'unico
file cases.json.

Uso:
    uv run python eval/run_eval.py            # tutte le suite
    uv run python eval/run_eval.py triage     # solo una o piu' suite
    uv run python eval/run_eval.py retrieval routing
    uv run eval                                # entry point definito in pyproject

Note:
- Le suite triage, routing e injection chiamano gli LLM su Groq: serve GROQ_API_KEY
  nel file .env. Se manca, queste suite vengono saltate (la retrieval gira comunque,
  perche' usa solo embedding locali + LanceDB).
- Prima di lanciare la valutazione il database dev'essere popolato: `uv run seed`.
"""

import os
import sys
import json
import re
import time

# Su Windows il terminale usa spesso cp1252 e va in errore sulle emoji (🟣🔵...).
# Forziamo stdout/stderr in UTF-8 cosi' il report gira in qualsiasi terminale.
# reconfigure() esiste dai TextIOWrapper di Python 3.7+; il guard evita errori
# in contesti dove lo stream non lo supporta.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

# Aggiunge src/ al path di import, come seed/run_seed.py: così `import debrief...`
# funziona anche lanciando questo file direttamente
# direttamente con `uv run python eval/run_eval.py`.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Cartella che contiene runner e dataset unico.
EVAL_DIR = os.path.dirname(__file__)
SEED_DIR = os.path.join(EVAL_DIR, "..", "seed")
CASES_PATH = os.path.join(EVAL_DIR, "cases.json")


# Helper generici
def _load_json(path: str) -> dict | list:
    """Carica un file JSON con encoding esplicito UTF-8 (gli incidenti sono in italiano)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sev_to_int(value: str) -> int:
    """'SEV2' -> 2. Serve per misurare la distanza tra severita' (tolleranza +/-1)."""
    return int(value.replace("SEV", ""))


def _pct(numerator: float, denominator: float) -> float:
    """Percentuale robusta alla divisione per zero (ritorna 0.0 se denominatore nullo)."""
    return 100.0 * numerator / denominator if denominator else 0.0


def _line(passed: bool, label: str, detail: str = "") -> None:
    """Stampa una riga per-caso con spunta verde / croce rossa, stile coerente col repo."""
    mark = "🟢" if passed else "🔴"
    print(f"   {mark} {label}{(' - ' + detail) if detail else ''}")


def _require_vector_tables() -> None:
    """Blocca le suite RAG con un errore chiaro se il seed non è stato eseguito."""
    from debrief.rag.indexer import get_db

    # verified_solutions nasce a runtime quando arriva il primo contributo umano;
    # non fa parte del seed iniziale.
    required = {"past_incidents", "knowledge_base"}
    available = set(get_db().list_tables().tables)
    missing = required - available
    if missing:
        raise RuntimeError(
            f"Tabelle LanceDB mancanti: {sorted(missing)}. Eseguire prima `uv run seed`."
        )


# Suite 1: TRIAGE
def eval_triage() -> dict:
    """Valuta severita' e gestione dei casi vaghi del Triage Agent.

    Severita' = sia esatta sia con tolleranza +/-1 livello (la severita' e'
    parzialmente soggettiva, quindi riportiamo entrambe).
    I casi con expected_severity=null verificano solo needs_clarification.
    """
    from debrief.agents.triage import create_triage_agent, run_triage, validate_teams

    data = _load_json(CASES_PATH)["triage"]
    teams = _load_json(os.path.join(SEED_DIR, "teams.json"))
    valid_team_ids = {t["id"] for t in teams}

    # Un solo agente riusato per tutti i casi: il catalogo team e' fisso.
    agent = create_triage_agent(teams)

    inc_total = 0                   # numero di casi-incidente (denominatore severita')
    sev_exact = sev_within1 = 0     # accuratezza severita' (solo casi-incidente)
    clar_total = clar_ok = 0        # correttezza del flag needs_clarification (tutti i casi)
    teams_violations = 0            # team suggeriti fuori catalogo dopo validate_teams (deve restare 0)
    execution_failures = 0
    confusion: dict[str, dict[str, int]] = {}

    print("\n🟣 SUITE: Triage (severita')\n")

    for case in data["cases"]:
        result = run_triage(agent, case["description"])
        if result is not None:
            result = validate_teams(result, valid_team_ids)

        is_incident = case["expected_severity"] is not None

        if result is None:
            execution_failures += 1
            _line(False, case["id"], "esecuzione fallita (rete, rate limit o output non valido)")
            continue

        # needs_clarification si valuta su TUTTI i casi.
        clar_total += 1
        got_clar = bool(result.needs_clarification)
        clar_match = got_clar == case["expected_needs_clarification"]
        clar_ok += int(clar_match)

        if not is_incident:
            # Caso vago/non-incidente: ci basta che chieda chiarimenti.
            _line(clar_match, case["id"], f"needs_clarification atteso={case['expected_needs_clarification']} ottenuto={got_clar}")
            continue

        inc_total += 1

        # Severita' (esatta e con tolleranza).
        got_sev = result.severity.value
        sev_match = got_sev == case["expected_severity"]
        sev_close = abs(_sev_to_int(got_sev) - _sev_to_int(case["expected_severity"])) <= 1
        sev_exact += int(sev_match)
        sev_within1 += int(sev_close)
        expected_sev = case["expected_severity"]
        confusion.setdefault(expected_sev, {})[got_sev] = (
            confusion.setdefault(expected_sev, {}).get(got_sev, 0) + 1
        )

        # Guardrail: nessun team fuori catalogo deve sopravvivere a validate_teams.
        if any(t not in valid_team_ids for t in result.suggested_teams):
            teams_violations += 1

        detail = f"sev attesa={case['expected_severity']}/ottenuta={got_sev}"
        _line(sev_close, case["id"], detail)

    metrics = {
        "severity_exact": _pct(sev_exact, inc_total),
        "severity_within_1": _pct(sev_within1, inc_total),
        "clarification_accuracy": _pct(clar_ok, clar_total),
        "team_catalog_violations": teams_violations,
        "severity_confusion_matrix": confusion,
        "execution_failures": execution_failures,
    }
    print()
    print(f"   Severita' (esatta):        {metrics['severity_exact']:.0f}%  ({sev_exact}/{inc_total})")
    print(f"   Severita' (+/-1 livello):  {metrics['severity_within_1']:.0f}%  ({sev_within1}/{inc_total})")
    print(f"   Chiarimenti (corretti):    {metrics['clarification_accuracy']:.0f}%  ({clar_ok}/{clar_total})")
    print(f"   Violazioni catalogo team:  {teams_violations} (atteso 0)")
    print(f"   Fallimenti di esecuzione:  {execution_failures}")
    return metrics


# Suite 2: ROUTING
def eval_routing() -> dict:
    """Valuta l'Orchestrator: dato messaggio + stato incidente, sceglie l'agente giusto?"""
    from debrief.agents.orchestrator import create_router_agent, route_message

    data = _load_json(CASES_PATH)["routing"]
    router = create_router_agent()

    total = ok = fallbacks = 0
    confusion: dict[str, dict[str, int]] = {}
    print("\n🟣 SUITE: Routing (orchestrator)\n")

    for case in data["cases"]:
        decision = route_message(
            router,
            case["message"],
            case["incident_status"],
            case["incident_description"],
        )
        got = decision.agent.value
        match = got == case["expected_agent"]
        is_fallback = decision.reason.startswith("fallback:")
        fallbacks += int(is_fallback)
        total += 1
        ok += int(match)
        expected = case["expected_agent"]
        confusion.setdefault(expected, {})[got] = confusion.setdefault(expected, {}).get(got, 0) + 1
        _line(match, case["id"], f"[{case['incident_status']}] atteso={case['expected_agent']} ottenuto={got}")

    metrics = {
        "routing_accuracy": _pct(ok, total),
        "fallback_count": fallbacks,
        "confusion_matrix": confusion,
    }
    print()
    print(f"   Accuratezza routing:  {metrics['routing_accuracy']:.0f}%  ({ok}/{total})")
    return metrics


# Suite 3: RESOLVER
def eval_resolver() -> dict:
    """Misura groundedness delle citazioni e recupero di almeno una fonte attesa."""
    from debrief.agents.resolver import create_resolver_agent, resolve

    _require_vector_tables()
    data = _load_json(CASES_PATH)["resolver"]
    incidents = _load_json(os.path.join(SEED_DIR, "incidents.json"))
    valid_ids = {item["id"] for item in incidents}
    agent = create_resolver_agent()
    agent.model.temperature = 0

    total = grounded = expected_hit = cited_any = execution_failures = 0
    print("\n🟣 SUITE: Resolver (groundedness e provenance)\n")
    for case in data["cases"]:
        output = resolve(agent, case["description"])
        if output.startswith("Resolution failed:"):
            execution_failures += 1
            _line(False, case["id"], "esecuzione fallita")
            continue
        cited = set(re.findall(r"\b(?:INC|VS)-\d{3}\b", output.upper()))
        unknown = cited - valid_ids
        expected = set(case["expected_any_ids"])
        is_grounded = not unknown
        has_expected = bool(cited & expected)
        grounded += int(is_grounded)
        expected_hit += int(has_expected)
        cited_any += int(bool(cited))
        total += 1
        _line(
            is_grounded and has_expected,
            case["id"],
            f"citate={sorted(cited)} sconosciute={sorted(unknown)}",
        )

    return {
        "grounded_citation_rate": _pct(grounded, total),
        "expected_source_hit_rate": _pct(expected_hit, total),
        "citation_rate": _pct(cited_any, total),
        "execution_failures": execution_failures,
    }


# Suite 4: RETRIEVAL
def eval_retrieval() -> dict:
    """Valuta il RAG sugli incidenti passati usando i cluster come ground truth.

    Per ogni query calcola precision@k, recall@k, MRR e hit@1, poi fa la media.
    Non usa LLM: solo embedding locali + LanceDB, quindi gira anche senza GROQ_API_KEY.
    """
    from debrief.config import SIMILARITY_THRESHOLD
    from debrief.rag.retriever import retrieve_similar_incidents

    _require_vector_tables()
    data = _load_json(CASES_PATH)["retrieval"]
    k = data.get("top_k", 5)

    sum_prec = sum_rec = sum_mrr = 0.0
    hit1 = 0
    n = 0
    print(f"\n🟣 SUITE: Retrieval (RAG, top_k={k}, soglia={SIMILARITY_THRESHOLD})\n")

    for case in data["cases"]:
        results = retrieve_similar_incidents(case["query"], k=k, threshold=SIMILARITY_THRESHOLD)
        retrieved = [r["id"] for r in results]
        relevant = set(case["relevant_ids"])

        hits = [rid for rid in retrieved if rid in relevant]
        precision = len(hits) / len(retrieved) if retrieved else 0.0
        recall = len(hits) / len(relevant) if relevant else 0.0

        # MRR: reciproco del rango (1-based) del primo risultato rilevante.
        rr = 0.0
        for rank, rid in enumerate(retrieved, start=1):
            if rid in relevant:
                rr = 1.0 / rank
                break

        is_hit1 = bool(retrieved) and retrieved[0] in relevant
        hit1 += int(is_hit1)

        sum_prec += precision
        sum_rec += recall
        sum_mrr += rr
        n += 1

        detail = (
            f"P@{k}={precision:.2f} R@{k}={recall:.2f} MRR={rr:.2f} "
            f"| recuperati={retrieved}"
        )
        # Consideriamo "ok" la riga se ha trovato almeno meta' del cluster.
        _line(recall >= 0.5, f"{case['id']} [{case['cluster']}]", detail)

    metrics = {
        "precision_at_k": _pct(sum_prec, n),
        "recall_at_k": _pct(sum_rec, n),
        "mrr": sum_mrr / n if n else 0.0,
        "hit_at_1": _pct(hit1, n),
        "top_k": k,
    }
    print()
    print(f"   Precision@{k}:  {metrics['precision_at_k']:.0f}%")
    print(f"   Recall@{k}:     {metrics['recall_at_k']:.0f}%")
    print(f"   MRR:           {metrics['mrr']:.2f}")
    print(f"   Hit@1:         {metrics['hit_at_1']:.0f}%  ({hit1}/{n})")
    return metrics


# Suite 5: LEARNING LOOP
def eval_learning_loop() -> dict:
    """Verifica che una soluzione umana diventi recuperabile dopo la cattura."""
    import tempfile

    from debrief.config import SIMILARITY_THRESHOLD
    from debrief.rag.indexer import add_verified_solution, get_db, search
    from debrief.tools.embedding import embed_text

    query = "FortiClient rifiuta la VPN perché il certificato client è scaduto"
    unrelated = {
        "id": "VS-UNRELATED",
        "incident_id": "INC-X",
        "problem_context": "Stampante senza carta",
        "solution": "Caricare un nuovo rotolo di etichette",
        "provided_by": "test",
    }
    learned = {
        "id": "VS-LEARNED",
        "incident_id": "INC-Y",
        "problem_context": query,
        "solution": "Rigenerare e distribuire il certificato client FortiClient",
        "provided_by": "human-expert",
    }

    with tempfile.TemporaryDirectory() as directory:
        database = get_db(directory)
        unrelated_text = unrelated["problem_context"] + " " + unrelated["solution"]
        add_verified_solution(database, unrelated, embed_text(unrelated_text))
        query_vector = embed_text(query)
        before = search(
            database, "verified_solutions", query_vector, k=3,
            threshold=SIMILARITY_THRESHOLD,
        )
        learned_text = learned["problem_context"] + " " + learned["solution"]
        add_verified_solution(database, learned, embed_text(learned_text))
        after = search(
            database, "verified_solutions", query_vector, k=3,
            threshold=SIMILARITY_THRESHOLD,
        )

    before_ids = {item["id"] for item in before}
    after_ids = {item["id"] for item in after}
    passed = learned["id"] not in before_ids and learned["id"] in after_ids
    _line(passed, "human-knowledge-loop", f"prima={sorted(before_ids)} dopo={sorted(after_ids)}")
    return {"learning_loop_success": 100.0 if passed else 0.0}


# Suite 6: INJECTION (red-team)
def eval_injection() -> dict:
    """Valuta la robustezza alla prompt injection.

    Un caso PASSA se nessuna delle stringhe 'forbidden' compare nell'output
    dell'agente (confronto case-insensitive). E' una metrica di SICUREZZA:
    l'obiettivo e' il 100%.
    """
    from debrief.agents.triage import create_triage_agent, run_triage, validate_teams
    from debrief.agents.orchestrator import create_router_agent, route_message

    data = _load_json(CASES_PATH)["injection"]
    teams = _load_json(os.path.join(SEED_DIR, "teams.json"))
    valid_team_ids = {t["id"] for t in teams}

    triage_agent = create_triage_agent(teams)
    router = create_router_agent()

    total = blocked = 0
    print("\n🟣 SUITE: Injection (red-team, robustezza)\n")

    for case in data["cases"]:
        # Costruiamo un "haystack" = tutto il testo prodotto dall'agente attaccato,
        # in cui cerchiamo le canary proibite.
        if case["target"] == "triage":
            result = run_triage(triage_agent, case["description"])
            if result is None:
                # Rifiuto/fallimento sicuro: nessun output, nessuna canary trapelata.
                haystack = ""
            else:
                result = validate_teams(result, valid_team_ids)
                haystack = " ".join([
                    result.title,
                    result.summary,
                    " ".join(result.clarifying_questions),
                    " ".join(result.suggested_teams),
                ])
        else:  # router
            decision = route_message(
                router,
                case["message"],
                case["incident_status"],
                case["incident_description"],
            )
            haystack = f"{decision.agent.value} {decision.reason}"

        hay_low = haystack.lower()
        leaked = [f for f in case["forbidden"] if f.lower() in hay_low]
        is_blocked = not leaked
        total += 1
        blocked += int(is_blocked)
        detail = f"{case['target']}" + ("" if is_blocked else f" | TRAPELATO: {leaked}")
        _line(is_blocked, case["id"], detail)

    metrics = {"injection_block_rate": _pct(blocked, total)}
    print()
    print(f"   Tasso di blocco:  {metrics['injection_block_rate']:.0f}%  ({blocked}/{total})")
    return metrics


# Orchestrazione delle suite
# Una suite e' "LLM" se chiama Groq: viene saltata se manca la chiave API.
SUITES = {
    "triage":    {"fn": eval_triage,    "llm": True},
    "routing":   {"fn": eval_routing,   "llm": True},
    "resolver":  {"fn": eval_resolver,  "llm": True},
    "retrieval": {"fn": eval_retrieval, "llm": False},
    "learning":  {"fn": eval_learning_loop, "llm": False},
    "injection": {"fn": eval_injection, "llm": True},
}


def main() -> None:
    # Argomenti = nomi delle suite da eseguire; nessun argomento = tutte.
    requested = sys.argv[1:] or list(SUITES.keys())

    unknown = [s for s in requested if s not in SUITES]
    if unknown:
        print(f"🔴 Suite sconosciute: {unknown}. Disponibili: {list(SUITES.keys())}")
        sys.exit(2)

    # Se manca la chiave Groq, le suite LLM non possono girare: le segnaliamo.
    have_key = bool(os.getenv("GROQ_API_KEY"))

    print("\n🟣 ============================================")
    print("🟣  Debrief - Valutazione automatica")
    print("🟣 ============================================")
    if not have_key:
        print("🔵 GROQ_API_KEY assente: le suite che usano LLM verranno saltate.")

    summary: dict[str, dict] = {}
    skipped: list[str] = []

    for name in requested:
        suite = SUITES[name]
        if suite["llm"] and not have_key:
            skipped.append(name)
            continue
        started = time.perf_counter()
        summary[name] = suite["fn"]()
        summary[name]["duration_seconds"] = round(time.perf_counter() - started, 2)

    # Riepilogo finale compatto.
    print("\n🟣 ============================================")
    print("🟣  RIEPILOGO")
    print("🟣 ============================================")
    for name, metrics in summary.items():
        pretty = "  ".join(
            f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}"
            for k, v in metrics.items()
        )
        print(f"   🟢 {name}: {pretty}")
    for name in skipped:
        print(f"   🔵 {name}: SALTATA (manca GROQ_API_KEY)")
    print()

    incomplete = sum(
        int(metrics.get("execution_failures", 0)) + int(metrics.get("fallback_count", 0))
        for metrics in summary.values()
    )
    if incomplete:
        print(f"🔴 Valutazione incompleta: {incomplete} esecuzioni LLM fallite o in fallback.")
        sys.exit(1)


if __name__ == "__main__":
    main()
