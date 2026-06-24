"""
test_triage.py - Testa il triage agent con una descrizione di incidente.

Uso:
    uv run python scripts/test_triage.py "Il PLC della linea estrusione si è fermato con errore Comm Fault"
    uv run python scripts/test_triage.py  (usa un esempio predefinito)
"""

import os
import sys
import json

# Path setup
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from debrief.agents.triage import create_triage_agent, run_triage, validate_teams


def main():
    # Carica il catalogo team
    teams_path = os.path.join(os.path.dirname(__file__), "..", "seed", "teams.json")
    with open(teams_path, encoding="utf-8") as f:
        teams = json.load(f)

    valid_team_ids = {t["id"] for t in teams}
    team_names = {t["id"]: t["name"] for t in teams}

    # Prendi la descrizione dalla riga di comando o usa un esempio
    if len(sys.argv) > 1:
        description = " ".join(sys.argv[1:])
    else:
        description = (
            "Il PLC della linea estrusione si è fermato con errore Comm Fault. "
            "La linea è completamente bloccata e il capoturno non riesce a resettare l'allarme."
        )

    print("\n🟣 Test Triage Agent\n")
    print(f"🔵 Description: {description}\n")
    print("🔵 Creating triage agent...")
    agent = create_triage_agent(teams)

    print("🔵 Running triage...\n")

    result = run_triage(agent, description)

    if result is None:
        print("🔴 Triage failed. Check the error above.")
        return

    # Valida i team suggeriti
    result = validate_teams(result, valid_team_ids)

    # Mostra il risultato
    print("🟢 Triage completed!\n")
    print(f"   Title:       {result.title}")
    print(f"   Severity:    {result.severity.value}")
    print(f"   Confidence:  {result.confidence:.0%}")
    print(f"   Systems:     {', '.join(result.affected_systems) if result.affected_systems else '-'}")
    print(f"   Teams:       {', '.join(team_names.get(t, t) for t in result.suggested_teams)}")
    print(f"   Summary:     {result.summary}")

    if result.needs_clarification:
        print("\n🔵 Clarification needed:")
        for q in result.clarifying_questions:
            print(f"   ? {q}")

    print()

    # Mostra anche il JSON grezzo per debug
    print("--- Raw JSON ---")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()