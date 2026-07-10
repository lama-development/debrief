"""Smoke test end-to-end con database temporanei e agenti reali."""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if callable(_reconfigure):
        _reconfigure(encoding="utf-8")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register(client, username: str, team_id: str) -> str:
    response = client.post(
        "/auth/register",
        json={"username": username, "password": "demo-password", "team_id": team_id},
    )
    response.raise_for_status()
    return response.json()["token"]


def _sse_events(response) -> list[dict]:
    response.raise_for_status()
    return [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    source_lance = project_root / "data" / "lancedb"
    if not source_lance.exists():
        raise RuntimeError("LanceDB non trovato. Eseguire prima `uv run seed`.")

    with tempfile.TemporaryDirectory() as directory:
        temp_root = Path(directory)
        temp_lance = temp_root / "lancedb"
        shutil.copytree(source_lance, temp_lance)
        os.environ["SQLITE_PATH"] = str(temp_root / "debrief.db")
        os.environ["LANCEDB_PATH"] = str(temp_lance)

        from fastapi.testclient import TestClient
        from debrief.api.app import app

        with TestClient(app) as client:
            alice = _register(client, "demo-alice", "IT_INTERNAL")
            bob = _register(client, "demo-bob", "IT_EXTERNAL")
            created = client.post(
                "/incidents",
                json={
                    "description": (
                        "FortiClient non avvia la VPN e segnala che il certificato "
                        "client aziendale è scaduto."
                    )
                },
                headers=_headers(alice),
            )
            created.raise_for_status()
            incident_id = created.json()["id"]

            assert client.get("/incidents", headers=_headers(bob)).json() == []
            denied = client.get(f"/incidents/{incident_id}", headers=_headers(bob))
            assert denied.status_code == 404

            involved = client.patch(
                f"/incidents/{incident_id}/classification",
                json={"add_teams": ["IT_EXTERNAL"]},
                headers=_headers(alice),
            )
            involved.raise_for_status()
            joined = client.get(f"/incidents/{incident_id}", headers=_headers(bob))
            joined.raise_for_status()
            assert {p["username"] for p in joined.json()["participants"]} == {
                "demo-alice", "demo-bob"
            }

            chat = client.post(
                f"/incidents/{incident_id}/chat",
                json={"message": "Il certificato risulta scaduto da ieri."},
                headers=_headers(bob),
            )
            events = _sse_events(chat)
            event_types = {event["type"] for event in events}
            assert {"routing", "triage", "done"} <= event_types

            learned = client.post(
                f"/incidents/{incident_id}/human-solutions",
                json={"solution": "Rigenerare e distribuire il certificato client VPN."},
                headers=_headers(alice),
            )
            learned.raise_for_status()
            assert learned.json()["provided_by"] == "demo-alice"

        with TestClient(app) as client:
            conversations = client.get("/incidents", headers=_headers(alice))
            conversations.raise_for_status()
            assert incident_id in {item["id"] for item in conversations.json()}

        print(f"OK demo smoke: {incident_id}")
        print(f"Eventi SSE: {sorted(event_types)}")
        print(f"Soluzione acquisita: {learned.json()['id']}")


if __name__ == "__main__":
    main()
