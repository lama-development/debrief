"""Valutazione automatica di agenti, RAG e controlli di sicurezza di Debrief."""

import os
import sys
import json
import re
import time

from dotenv import load_dotenv

# Uniforma la codifica dei risultati anche sui terminali Windows.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if callable(_reconfigure):
        _reconfigure(encoding="utf-8")

# Supporta anche l'esecuzione diretta del file.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

EVAL_DIR = os.path.dirname(__file__)
SEED_DIR = os.path.join(EVAL_DIR, "..", "seed")
CASES_PATH = os.path.join(EVAL_DIR, "cases.json")

load_dotenv(os.path.join(EVAL_DIR, "..", ".env"))

CASE_IDS = {
    "triage": {"TRI-01", "TRI-05"},
    "routing": {"ROU-01", "ROU-03", "ROU-04"},
    "resolver": {"RES-01"},
    "injection": {"INJ-01"},
}


def _load_json(path: str) -> dict | list:
    """Carica un file JSON UTF-8."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_json_records(path: str) -> list[dict]:
    """Carica un array JSON composto esclusivamente da oggetti."""
    data = _load_json(path)
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError(f"Formato non valido in {path}: atteso un array di oggetti JSON")
    return data


def _suite_data(name: str) -> dict:
    """Carica i casi selezionati per una suite."""
    suites = _load_json(CASES_PATH)
    if not isinstance(suites, dict):
        raise ValueError(f"Formato non valido in {CASES_PATH}: atteso un oggetto JSON")

    data = suites[name]
    selected = CASE_IDS.get(name)
    if not selected:
        return data

    return {
        **data,
        "cases": [case for case in data["cases"] if case["id"] in selected],
    }


def _sev_to_int(value: str) -> int:
    """Converte una severità nel suo livello numerico."""
    return int(value.replace("SEV", ""))


def _pct(numerator: float, denominator: float) -> float:
    """Calcola una percentuale evitando divisioni per zero."""
    return 100.0 * numerator / denominator if denominator else 0.0


def _require_vector_tables() -> None:
    """Blocca le suite RAG se manca il caricamento iniziale."""
    from debrief.rag.indexer import get_db

    required = {"past_incidents", "knowledge_base"}
    available = set(get_db().list_tables().tables)
    missing = required - available
    if missing:
        raise RuntimeError(
            f"Tabelle LanceDB mancanti: {sorted(missing)}. Eseguire prima `uv run seed`."
        )


# Suite 1: TRIAGE
def eval_triage() -> dict:
    """Valuta severità e richieste di chiarimento del triage."""
    from debrief.agents.triage import create_triage_agent, run_triage, validate_teams

    data = _suite_data("triage")
    teams = _load_json_records(os.path.join(SEED_DIR, "teams.json"))
    valid_team_ids = {t["id"] for t in teams}

    agent = create_triage_agent(teams)

    inc_total = 0
    sev_exact = sev_within1 = 0
    clar_total = clar_ok = 0
    teams_violations = 0
    execution_failures = 0
    confusion: dict[str, dict[str, int]] = {}

    print("\n== Suite: Triage (severita') ==\n")

    for case in data["cases"]:
        result = run_triage(agent, case["description"])
        if result is not None:
            result = validate_teams(result, valid_team_ids)

        is_incident = case["expected_severity"] is not None

        if result is None:
            execution_failures += 1
            print(f"   [FAIL] {case['id']} - esecuzione fallita (rete, rate limit o output non valido)")
            continue

        clar_total += 1
        got_clar = bool(result.needs_clarification)
        clar_match = got_clar == case["expected_needs_clarification"]
        clar_ok += int(clar_match)

        if not is_incident:
            mark = "PASS" if clar_match else "FAIL"
            print(
                f"   [{mark}] {case['id']} - "
                f"needs_clarification atteso={case['expected_needs_clarification']} ottenuto={got_clar}"
            )
            continue

        inc_total += 1

        got_sev = result.severity.value
        sev_match = got_sev == case["expected_severity"]
        sev_close = abs(_sev_to_int(got_sev) - _sev_to_int(case["expected_severity"])) <= 1
        sev_exact += int(sev_match)
        sev_within1 += int(sev_close)
        expected_sev = case["expected_severity"]
        confusion.setdefault(expected_sev, {})[got_sev] = (
            confusion.setdefault(expected_sev, {}).get(got_sev, 0) + 1
        )

        if any(t not in valid_team_ids for t in result.suggested_teams):
            teams_violations += 1

        detail = f"sev attesa={case['expected_severity']}/ottenuta={got_sev}"
        mark = "PASS" if sev_close else "FAIL"
        print(f"   [{mark}] {case['id']} - {detail}")

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

    data = _suite_data("routing")
    router = create_router_agent()

    total = ok = fallbacks = 0
    confusion: dict[str, dict[str, int]] = {}
    print("\n== Suite: Routing (orchestrator) ==\n")

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
        mark = "PASS" if match else "FAIL"
        print(
            f"   [{mark}] {case['id']} - "
            f"[{case['incident_status']}] atteso={case['expected_agent']} ottenuto={got}"
        )

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
    """Verifica validità delle citazioni e recupero di una fonte attesa."""
    from debrief.agents.resolver import create_resolver_agent, resolve

    _require_vector_tables()
    data = _suite_data("resolver")
    incidents = _load_json_records(os.path.join(SEED_DIR, "incidents.json"))
    valid_ids = {item["id"] for item in incidents}
    agent = create_resolver_agent(temperature=0)

    total = grounded = expected_hit = cited_any = execution_failures = 0
    print("\n== Suite: Resolver (groundedness e provenance) ==\n")
    for case in data["cases"]:
        output = resolve(agent, case["description"])
        if output.startswith("Resolution failed:"):
            execution_failures += 1
            print(f"   [FAIL] {case['id']} - esecuzione fallita")
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
        mark = "PASS" if is_grounded and has_expected else "FAIL"
        print(f"   [{mark}] {case['id']} - citate={sorted(cited)} sconosciute={sorted(unknown)}")

    return {
        "grounded_citation_rate": _pct(grounded, total),
        "expected_source_hit_rate": _pct(expected_hit, total),
        "citation_rate": _pct(cited_any, total),
        "execution_failures": execution_failures,
    }


# Suite 4: RETRIEVAL
def eval_retrieval() -> dict:
    """Valuta precision, recall, MRR e hit@1 del recupero semantico."""
    from debrief.config import INCIDENT_SIMILARITY_THRESHOLD
    from debrief.rag.retriever import retrieve_similar_incidents

    _require_vector_tables()
    data = _suite_data("retrieval")
    k = data.get("top_k", 5)

    sum_prec = sum_rec = sum_mrr = 0.0
    hit1 = 0
    n = 0
    print(f"\n== Suite: Retrieval (RAG, top_k={k}, soglia={INCIDENT_SIMILARITY_THRESHOLD}) ==\n")

    for case in data["cases"]:
        results = retrieve_similar_incidents(case["query"], k=k, threshold=INCIDENT_SIMILARITY_THRESHOLD)
        retrieved = [r["id"] for r in results]
        relevant = set(case["relevant_ids"])

        hits = [rid for rid in retrieved if rid in relevant]
        precision = len(hits) / len(retrieved) if retrieved else 0.0
        recall = len(hits) / len(relevant) if relevant else 0.0

        # Reciproco del rango del primo risultato rilevante.
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
        # Soglia di successo per il singolo caso.
        mark = "PASS" if recall >= 0.5 else "FAIL"
        print(f"   [{mark}] {case['id']} - {detail}")

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
    """Verifica che una soluzione umana alimenti il ciclo di apprendimento."""
    import tempfile

    from debrief.config import INCIDENT_SIMILARITY_THRESHOLD
    from debrief.rag.indexer import get_db, search, upsert_past_incident, _build_incident_text
    from debrief.tools.embedding import embed_text

    print("\n== Suite: Learning loop ==\n")

    query = "FortiClient rifiuta la VPN perché il certificato client è scaduto"
    unrelated = {
        "id": "INC-X",
        "title": "Stampante senza carta",
        "severity": "SEV4",
        "description": "Stampante etichette ferma per materiale esaurito",
        "resolution": "Caricare un nuovo rotolo di etichette",
    }
    learned = {
        "id": "INC-Y",
        "title": "VPN bloccata per certificato client scaduto",
        "severity": "SEV2",
        "description": query,
        "resolution": "Rigenerare e distribuire il certificato client FortiClient",
    }

    with tempfile.TemporaryDirectory() as directory:
        database = get_db(directory)
        query_vector = embed_text(query)
        upsert_past_incident(database, unrelated, embed_text(_build_incident_text(unrelated)))
        before = search(database, "past_incidents", query_vector, k=3, threshold=INCIDENT_SIMILARITY_THRESHOLD)
        upsert_past_incident(database, learned, embed_text(_build_incident_text(learned)))
        after = search(
            database, "past_incidents", query_vector, k=3,
            threshold=INCIDENT_SIMILARITY_THRESHOLD,
        )

    before_ids = {item["id"] for item in before}
    after_ids = {item["id"] for item in after}
    passed = learned["id"] not in before_ids and learned["id"] in after_ids
    mark = "PASS" if passed else "FAIL"
    print(f"   [{mark}] human-knowledge-loop - prima={sorted(before_ids)} dopo={sorted(after_ids)}")
    return {"learning_loop_success": 100.0 if passed else 0.0}


# Suite 6: INJECTION (test offensivi)
def eval_injection() -> dict:
    """Verifica che le stringhe proibite non compaiano nella risposta."""
    from debrief.agents.triage import create_triage_agent, run_triage, validate_teams
    from debrief.agents.orchestrator import create_router_agent, route_message

    data = _suite_data("injection")
    teams = _load_json_records(os.path.join(SEED_DIR, "teams.json"))
    valid_team_ids = {t["id"] for t in teams}

    triage_agent = create_triage_agent(teams)
    router = create_router_agent()

    total = blocked = 0
    print("\n== Suite: Injection (red-team, robustezza) ==\n")

    for case in data["cases"]:
        # Raccoglie tutta la risposta osservabile per cercare le stringhe proibite.
        if case["target"] == "triage":
            result = run_triage(triage_agent, case["description"])
            if result is None:
                haystack = ""
            else:
                result = validate_teams(result, valid_team_ids)
                haystack = " ".join([
                    result.title,
                    result.summary,
                    " ".join(result.clarifying_questions),
                    " ".join(result.suggested_teams),
                ])
        else:
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
        mark = "PASS" if is_blocked else "FAIL"
        print(f"   [{mark}] {case['id']} - {detail}")

    metrics = {"injection_block_rate": _pct(blocked, total)}
    print()
    print(f"   Tasso di blocco:  {metrics['injection_block_rate']:.0f}%  ({blocked}/{total})")
    return metrics


# Le suite LLM vengono saltate senza chiave Groq.
SUITES = {
    "triage":    {"fn": eval_triage,    "llm": True},
    "routing":   {"fn": eval_routing,   "llm": True},
    "resolver":  {"fn": eval_resolver,  "llm": True},
    "retrieval": {"fn": eval_retrieval, "llm": False},
    "learning":  {"fn": eval_learning_loop, "llm": False},
    "injection": {"fn": eval_injection, "llm": True},
}


def main() -> None:
    if len(sys.argv) > 1:
        print("[ERROR] Questo runner usa un solo comando: `uv run eval`.")
        sys.exit(2)

    requested = list(SUITES.keys())

    have_key = bool(os.getenv("GROQ_API_KEY"))
    needs_llm = any(SUITES[name]["llm"] for name in requested)

    print("\n================================================")
    print(" Debrief - Valutazione automatica")
    print("================================================")
    if needs_llm and not have_key:
        print("[INFO] GROQ_API_KEY assente: le suite che usano LLM verranno saltate.")

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

    print("\n================================================")
    print(" Riepilogo")
    print("================================================")
    for name, metrics in summary.items():
        pretty = "  ".join(
            f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}"
            for k, v in metrics.items()
        )
        print(f"   [OK] {name}: {pretty}")
    for name in skipped:
        print(f"   [SKIP] {name}: SALTATA (manca GROQ_API_KEY)")
    print()

    incomplete = sum(
        int(metrics.get("execution_failures", 0)) + int(metrics.get("fallback_count", 0))
        for metrics in summary.values()
    )
    if incomplete:
        print(f"[ERROR] Valutazione incompleta: {incomplete} esecuzioni LLM fallite o in fallback.")
        sys.exit(1)


if __name__ == "__main__":
    main()
