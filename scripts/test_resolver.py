"""
test_resolver.py - Testa il resolver agent.

Uso:
    uv run python scripts/test_resolver.py                          # test suite predefinita
    uv run python scripts/test_resolver.py "descrizione incidente"  # query singola
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from debrief.agents.resolver import create_resolver_agent, resolve


def run_test(agent, description, context=None, label=""):
    """Esegue un singolo test e stampa il risultato."""
    if label:
        print(f"--- {label} ---")
    print(f"🔵 Incident: {description[:100]}...")
    if context:
        print(f"🔵 Context: {context[:80]}...")
    print()

    result = resolve(agent, description, context or "")

    print("🟢 Remediation:")
    print()
    print(result)
    print()


def main():
    print("=" * 60)
    print("DEBRIEF - Test Resolver Agent")
    print("=" * 60)
    print()

    print("🔵 Creating resolver agent...")
    agent = create_resolver_agent()
    print()

    if len(sys.argv) > 1:
        description = " ".join(sys.argv[1:])
        run_test(agent, description)
    else:
        print("Running predefined test suite...")
        print()

        # Test 1: PLC - dovrebbe trovare verified solutions
        run_test(
            agent,
            "Il PLC della linea estrusione si è fermato. La sonda di temperatura sembra difettosa, legge valori fuori range e il blocco di sicurezza non si resetta.",
            "Triage: SEV2, HARDWARE. Team suggeriti: PLC_VENDOR, PRODUCTION.",
            "Test 1: PLC sensor (should find VS-001)"
        )

        # Test 2: Disco pieno - dovrebbe trovare past incidents + KB
        run_test(
            agent,
            "Il server srv-file1 ha il disco pieno al 100%. Nessuno riesce ad accedere alle cartelle condivise. RDP non funziona.",
            "Triage: SEV1, INFRASTRUCTURE. Team suggeriti: IT_INTERNAL, IT_EXTERNAL.",
            "Test 2: Disk full (should find INC-011 + KB)"
        )

        # Test 3: Problema nuovo - dovrebbe usare general knowledge
        run_test(
            agent,
            "Il condizionatore della sala server è guasto e la temperatura sta salendo. Siamo a 35 gradi.",
            "Triage: SEV2, INFRASTRUCTURE. Team suggeriti: IT_INTERNAL, MANAGEMENT.",
            "Test 3: Server room cooling (should use general knowledge)"
        )


if __name__ == "__main__":
    main()