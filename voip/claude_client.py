import json
import os
import re
from pathlib import Path

import anthropic

SKILL_DIR = Path(__file__).parent.parent / "skill/skills/virtual-cod"

_VOICE_INSTRUCTIONS = """
# ISTRUZIONI CANALE VOCALE

Stai operando come operatore della Virtual COD tramite telefono VoIP.
Le tue risposte vengono sintetizzate vocalmente e lette ad alta voce all'utente.

REGOLE OBBLIGATORIE:
1. Rispondi SOLO in italiano parlato — niente markdown, asterischi, trattini elenco, grassetti, titoli o simboli
2. Massimo 120 parole per risposta — l'utente ascolta, non legge
3. Usa frasi naturali e complete, come in una telefonata reale
4. Non usare sigle senza spiegarle la prima volta (es. "CDI, cioè Centro Diurno Integrato")
5. Non elencare mai dati in forma di lista: incorporali nel parlato ("ha un'invalidità parziale del 75% e attualmente non riceve aiuti economici")

MARCATORI DI SISTEMA
Includi all'INIZIO della risposta (prima del testo parlato) quando necessario.
I marcatori vengono estratti automaticamente e non vengono mai letti all'utente.

[ANAGRAFICA:JSON] — Includi quando hai raccolto TUTTI i campi obbligatori della checklist anagrafica.
  Il JSON deve essere conforme allo schema COD Intake Form.
  Esempio: [ANAGRAFICA:{"utente":{"data_contatto":"2026-06-08","nome":"Mario","cognome":"Rossi","chiama_per_se":false},"assistito":{...}}]

[SEND_EMAIL:indirizzo@email.com] — Includi quando l'utente fornisce o conferma il suo indirizzo email
  per ricevere il riepilogo. Includi sempre subito dopo anche [EMAIL_BODY:testo] con il corpo completo
  dell'email da inviare, seguendo i template dei servizi discussi.
  Esempio: [SEND_EMAIL:mario@example.com][EMAIL_BODY:Gentile Sig. Rossi,\\nCome concordato...\\nCordiali saluti,\\nLa COD]

[END_CALL] — Includi quando la conversazione è conclusa e l'utente non ha ulteriori domande.

Esempio di risposta con marcatori:
[ANAGRAFICA:{...}] Perfetto, ho raccolto tutti i dati necessari. Mi spieghi ora il motivo per cui ci sta contattando.
"""


def _build_system_prompt() -> str:
    parts: list[str] = []

    def _read(rel: str) -> str:
        return (SKILL_DIR / rel).read_text(encoding="utf-8")

    parts.append(_read("SKILL.md"))
    parts.append(_read("workflow/phase-1-anagrafica.md"))
    parts.append(_read("workflow/phase-2-bisogni.md"))
    parts.append(_read("references/servizi/panoramica-servizi.md"))

    for p in sorted((SKILL_DIR / "references/servizi").glob("*.md")):
        if p.name != "panoramica-servizi.md":
            parts.append(p.read_text(encoding="utf-8"))

    parts.append(_VOICE_INSTRUCTIONS)
    return "\n\n---\n\n".join(parts)


def _parse_markers(text: str) -> tuple[str, dict]:
    """Return (clean_spoken_text, markers_dict)."""
    markers: dict = {}
    clean = text

    # [ANAGRAFICA:JSON] — greedy but stop before next marker
    m = re.search(r"\[ANAGRAFICA:(\{.*?\})\]", text, re.DOTALL)
    if m:
        try:
            markers["anagrafica"] = json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
        clean = clean.replace(m.group(0), "", 1)

    # [EMAIL_BODY:...] — extract before SEND_EMAIL so the body isn't left in clean text
    m = re.search(r"\[EMAIL_BODY:(.*?)\]", clean, re.DOTALL)
    if m:
        markers["email_body"] = m.group(1).replace("\\n", "\n").strip()
        clean = clean.replace(m.group(0), "", 1)

    # [SEND_EMAIL:address]
    m = re.search(r"\[SEND_EMAIL:([^\]]+)\]", clean)
    if m:
        markers["email"] = m.group(1).strip()
        clean = clean.replace(m.group(0), "", 1)

    # [END_CALL]
    if "[END_CALL]" in clean:
        markers["end_call"] = True
        clean = clean.replace("[END_CALL]", "", 1)

    return clean.strip(), markers


_MODEL = os.getenv("AWS_BEDROCK_MODEL_ID", "eu.anthropic.claude-sonnet-4-6")


class ClaudeClient:
    def __init__(self) -> None:
        self._client = anthropic.AnthropicBedrock()
        self._system = _build_system_prompt()

    def get_response(
        self, history: list[dict], user_message: str
    ) -> tuple[str, dict, list[dict]]:
        """
        Returns (clean_spoken_text, markers, updated_history).
        updated_history includes both the new user message and the assistant reply
        (with raw markers intact, so context is preserved for Claude).
        """
        messages = history + [{"role": "user", "content": user_message}]

        response = self._client.messages.create(
            model=_MODEL,
            max_tokens=600,
            system=self._system,
            messages=messages,
        )

        raw = response.content[0].text
        clean, markers = _parse_markers(raw)
        updated_history = messages + [{"role": "assistant", "content": raw}]

        return clean, markers, updated_history

    def generate_email_body(self, history: list[dict], anagrafica: dict | None) -> str:
        """Dedicated call to produce the follow-up email body."""
        nome = ""
        if anagrafica:
            a = anagrafica.get("assistito", {})
            u = anagrafica.get("utente", {})
            nome = a.get("nome") or u.get("nome") or ""

        prompt = (
            f"Basandoti sulla conversazione precedente, genera il testo completo "
            f"dell'email di follow-up da inviare all'utente della Virtual COD. "
            f"{'Il nome del paziente assistito è ' + nome + '.' if nome else ''} "
            f"L'email deve: essere in italiano formale; iniziare con 'Gentile [nome],' "
            f"se il nome è noto; riassumere i servizi discussi e i passi pratici consigliati; "
            f"terminare con 'Cordiali saluti, La Centrale Operativa Demenze'. "
            f"Massimo 300 parole. Restituisci SOLO il testo dell'email, senza altri commenti."
        )

        response = self._client.messages.create(
            model=_MODEL,
            max_tokens=600,
            system=self._system,
            messages=history + [{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
