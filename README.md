# virtual-cod-engine

```
skill/
└── skills/
    └── virtual-cod/    ← the skill to use in Claude
voip/
├── data/
    ├── sessions.db     ← the SQLite database with sessions
    └── anagrafiche/    ← the SQLite database with sessions
├── config.py           ← module-level BASE_URL, mutated at startup
├── db.py               ← SQLite init: sessions + anagrafiche tables
├── session_manager.py  ← CRUD for call sessions
├── anagrafica_store.py ← writes anagrafica_[Nome]_[Cognome]_[ts].json + DB row
├── claude_client.py    ← loads all skill/ files into system prompt, parses markers
├── twiml_builder.py    ← gather_response() / hangup_response() using Polly.Bianca
├── email_sender.py     ← SMTP send, delegates to Claude if no body provided
├── startup.py          ← detects ngrok URL, updates Twilio webhook on boot
├── server.py           ← FastAPI: /call/answer → /call/transcribed → /call/hangup
├── requirements.txt
├── .env                ← environment variables (e.g. API keys, LLM specs, etc)
└── .env.example        ← .env empty example template
```

## How it works end-to-end
Start ngrok: `ngrok http 8000`
`pip install -r requirements.txt`
`python server.py` — on startup, detects ngrok URL and auto-updates Twilio webhook
Call your Twilio number → Claude runs the Virtual COD skill over voice