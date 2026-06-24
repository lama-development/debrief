"""
test_orchestrator.py - Testa l'orchestratore end-to-end.

Uso:
    uv run python scripts/test_orchestrator.py                     # test suite predefinita
    uv run python scripts/test_orchestrator.py "messaggio" active  # singolo messaggio
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from debrief.agents.orchestrator import run_orchestrator


INCIDENT_DESCRIPTION = "Il PLC della linea estrusione si è fermato con errore Comm Fault sul modulo di I/O remoto. La linea è ferma."


def run_test(message: str, status: str, description: str = INCIDENT_DESCRIPTION, label: str = ""):
    """Esegue un singolo test e stampa il risultato."""
    if label:
        print(f"--- {label} ---")
    print(f"🔵 Status:  {status}")
    print(f"🔵 Message: {message}")
    print()

    result = run_orchestrator(
        message=message,
        incident_id="INC-TEST",
        incident_status=status,
        incident_description=description,
    )

    agent = result["agent"]
    reason = result["decision_reason"]
    response = result["response"]
    triage_output = result.get("triage_output")

    print(f"🟢 Agent routed to: {agent.upper()}")
    print(f"🔵 Reason: {reason}")
    print()

    if triage_output:
        print(f"   Title:    {triage_output.title}")
        print(f"   Severity: {triage_output.severity.value}")
        print(f"   Teams:    {', '.join(triage_output.suggested_teams) or 'none'}")
        print(f"   Needs clarification: {triage_output.needs_clarification}")
        print()

    if response:
        print("🟢 Response:")
        print()
        print(response)
    else:
        print("🔵 (no response - NONE agent)")
    print()


def main():
    print("=" * 60)
    print("DEBRIEF - Test Orchestrator")
    print("=" * 60)
    print()

    if len(sys.argv) > 1:
        message = sys.argv[1]
        status = sys.argv[2] if len(sys.argv) > 2 else "active"
        run_test(message, status)
        return

    print("Running predefined test suite...")
    print()

    # Test 1: incident declaration → TRIAGE expected
    run_test(
        message=INCIDENT_DESCRIPTION,
        status="open",
        label="Test 1: Incident declaration (→ TRIAGE)",
    )

    # Test 2: investigation question during active incident → INVESTIGATOR expected
    run_test(
        message="È già successo in passato questo tipo di errore sul PLC?",
        status="active",
        label="Test 2: Investigation question (→ INVESTIGATOR)",
    )

    # Test 3: ask for resolution → RESOLVER expected
    run_test(
        message="Come risolvo questo problema? Cosa devo fare?",
        status="active",
        label="Test 3: Resolution request (→ RESOLVER)",
    )

    # Test 4: resolved incident → NONE expected
    run_test(
        message="Grazie, il problema è stato risolto.",
        status="resolved",
        description="Incidente PLC risolto.",
        label="Test 4: Closed incident message (→ NONE)",
    )

    # Test 5: vague description → TRIAGE with clarification expected
    run_test(
        message="Ho un problema.",
        status="open",
        description="Ho un problema.",
        label="Test 5: Vague description (→ TRIAGE + clarification)",
    )


if __name__ == "__main__":
    main()
