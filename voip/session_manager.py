import json
from db import get_conn


def create_session(call_sid: str, caller_number: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (call_sid, caller_number) VALUES (?, ?)",
            (call_sid, caller_number),
        )


def get_session(call_sid: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE call_sid = ?", (call_sid,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    d["conversation_history"] = json.loads(d["conversation_history"] or "[]")
    d["anagrafica"] = json.loads(d["anagrafica"]) if d["anagrafica"] else None
    return d


def update_session(
    call_sid: str,
    history: list,
    anagrafica: dict | None = None,
    email: str | None = None,
) -> None:
    fields = ["conversation_history = ?", "updated_at = CURRENT_TIMESTAMP"]
    values: list = [json.dumps(history, ensure_ascii=False)]

    if anagrafica is not None:
        fields.append("anagrafica = ?")
        values.append(json.dumps(anagrafica, ensure_ascii=False))
    if email is not None:
        fields.append("email = ?")
        values.append(email)

    values.append(call_sid)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE sessions SET {', '.join(fields)} WHERE call_sid = ?",
            values,
        )


def increment_no_input(call_sid: str) -> int:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET no_input_count = no_input_count + 1, "
            "updated_at = CURRENT_TIMESTAMP WHERE call_sid = ?",
            (call_sid,),
        )
        row = conn.execute(
            "SELECT no_input_count FROM sessions WHERE call_sid = ?", (call_sid,)
        ).fetchone()
    return row["no_input_count"] if row else 1


def reset_no_input(call_sid: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET no_input_count = 0, updated_at = CURRENT_TIMESTAMP "
            "WHERE call_sid = ?",
            (call_sid,),
        )


def complete_session(call_sid: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET status = 'completed', updated_at = CURRENT_TIMESTAMP "
            "WHERE call_sid = ?",
            (call_sid,),
        )
