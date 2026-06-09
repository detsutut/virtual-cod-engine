import json
from datetime import datetime
from pathlib import Path
from db import get_conn

DATA_DIR = Path(__file__).parent / "data" / "anagrafiche"


def save_anagrafica(call_sid: str, data: dict) -> str:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    utente = data.get("utente", {})
    nome = (utente.get("nome") or "unknown").replace(" ", "_")
    cognome = (utente.get("cognome") or "unknown").replace(" ", "_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"anagrafica_{nome}_{cognome}_{timestamp}.json"
    file_path = DATA_DIR / filename

    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    with get_conn() as conn:
        conn.execute(
            "INSERT INTO anagrafiche (call_sid, nome, cognome, file_path, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                call_sid,
                utente.get("nome"),
                utente.get("cognome"),
                str(file_path),
                json.dumps(data, ensure_ascii=False),
            ),
        )

    return str(file_path)
