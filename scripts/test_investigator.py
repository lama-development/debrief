"""
test_investigator.py - Testa l'investigator agent.

Uso:
    uv run python scripts/test_investigator.py                                     # esegue tutti i test predefiniti
    uv run python scripts/test_investigator.py "domanda libera"                    # esegue solo la tua domanda
    uv run python scripts/test_investigator.py "domanda" --context "descrizione"   # domanda + contesto incidente
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from debrief.agents.investigator import create_investigator_agent, investigate


def run_single_query(agent, question, context=None):
    """Esegue una singola query e stampa il risultato."""
    if context:
        print(f"🔵 Context: {context[:80]}...")
    print(f"🔵 Question: {question}")
    print()

    result = investigate(agent, question, context or "")

    print("🟢 Result:")
    print()
    print(result)
    print()


def main():
    print("=" * 60)
    print("DEBRIEF - Test Investigator Agent")
    print("=" * 60)
    print()

    print("🔵 Creating investigator agent...")
    agent = create_investigator_agent()
    print()

    # Parsing argomenti
    args = sys.argv[1:]
    context = None
    question = None

    if "--context" in args:
        ctx_index = args.index("--context")
        context = args[ctx_index + 1] if ctx_index + 1 < len(args) else None
        args = args[:ctx_index]

    if args:
        question = " ".join(args)

    if question:
        # Modalita' singola query da CLI
        run_single_query(agent, question, context)
    else:
        # Modalita' test suite completa
        print("Running predefined test suite...")
        print()

        # Test 1: PLC con contesto
        print("-" * 40)
        print("Test 1: PLC incident with context")
        print("-" * 40)
        run_single_query(
            agent,
            "Ci sono stati incidenti simili in passato?",
            "Il PLC della linea estrusione si è fermato con errore Comm Fault. La linea è completamente bloccata."
        )

        # Test 2: Disco pieno senza contesto
        print("-" * 40)
        print("Test 2: Disk full, no context")
        print("-" * 40)
        run_single_query(
            agent,
            "Abbiamo mai avuto problemi con il disco pieno sui server?"
        )

        # Test 3: Outlook senza contesto
        print("-" * 40)
        print("Test 3: Outlook, no context")
        print("-" * 40)
        run_single_query(
            agent,
            "Ci sono stati problemi con Outlook o la posta in passato?"
        )

        # Test 4: Domanda senza match
        print("-" * 40)
        print("Test 4: No match expected")
        print("-" * 40)
        run_single_query(
            agent,
            "Abbiamo mai avuto un attacco ransomware riuscito?"
        )


if __name__ == "__main__":
    main()