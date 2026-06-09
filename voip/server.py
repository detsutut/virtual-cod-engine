import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form
from fastapi.responses import Response

load_dotenv()

from anagrafica_store import save_anagrafica
from claude_client import ClaudeClient
from db import init_db
from email_sender import send_followup
from session_manager import (
    complete_session,
    create_session,
    get_session,
    increment_no_input,
    reset_no_input,
    update_session,
)
from startup import configure_twilio_webhook
from twiml_builder import gather_response, hangup_response

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger(__name__)

_GREETING = (
    "Benvenuto alla Centrale Operativa Demenze della provincia di Pavia. "
    "Sono un operatore virtuale. "
    "Per orientarla al meglio, ho bisogno di raccogliere alcuni dati. "
    "Come si chiama?"
)
_ERROR = "Si è verificato un errore interno. La preghiamo di richiamare più tardi."
_NO_ANSWER = "Non ricevo risposta. La richiamiamo appena possibile. Arrivederci."

claude = ClaudeClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await configure_twilio_webhook()
    yield


app = FastAPI(lifespan=lifespan)

XML = "application/xml"


@app.post("/call/answer")
async def call_answer(
    CallSid: str = Form(...),
    From: str = Form(default="unknown"),
):
    create_session(CallSid, From)
    logger.info("Incoming call %s from %s", CallSid, From)
    return Response(content=gather_response(_GREETING), media_type=XML)


@app.post("/call/transcribed")
async def call_transcribed(
    background_tasks: BackgroundTasks,
    CallSid: str = Form(...),
    SpeechResult: str = Form(default=""),
    Confidence: str = Form(default="0"),
):
    session = get_session(CallSid)
    if not session:
        return Response(content=hangup_response(_ERROR), media_type=XML)

    speech = SpeechResult.strip()
    if not speech:
        return Response(
            content=gather_response("Scusi, non ho sentito. Può ripetere?"),
            media_type=XML,
        )

    reset_no_input(CallSid)
    logger.info("CallSid=%s  speech=%r  confidence=%s", CallSid, speech, Confidence)

    history = session["conversation_history"]
    clean, markers, updated_history = claude.get_response(history, speech)

    new_anagrafica = session.get("anagrafica")
    new_email = session.get("email")

    if "anagrafica" in markers:
        new_anagrafica = markers["anagrafica"]
        background_tasks.add_task(save_anagrafica, CallSid, new_anagrafica)
        logger.info("CallSid=%s  anagrafica saved", CallSid)

    if "email" in markers:
        new_email = markers["email"]
        email_body = markers.get("email_body")
        background_tasks.add_task(
            _send_email_bg, new_email, updated_history, new_anagrafica, email_body
        )
        logger.info("CallSid=%s  email queued → %s", CallSid, new_email)

    update_session(
        CallSid,
        history=updated_history,
        anagrafica=new_anagrafica if "anagrafica" in markers else None,
        email=new_email if "email" in markers else None,
    )

    if markers.get("end_call"):
        complete_session(CallSid)
        farewell = clean or "Grazie per aver contattato la Centrale Operativa Demenze. Arrivederci."
        return Response(content=hangup_response(farewell), media_type=XML)

    return Response(content=gather_response(clean), media_type=XML)


@app.post("/call/no-input")
async def call_no_input(CallSid: str = Form(...)):
    count = increment_no_input(CallSid)
    if count >= 2:
        complete_session(CallSid)
        return Response(content=hangup_response(_NO_ANSWER), media_type=XML)
    return Response(
        content=gather_response("Scusi, è ancora in linea? Può ripetere?"),
        media_type=XML,
    )


@app.post("/call/hangup")
async def call_hangup(CallSid: str = Form(default="")):
    if CallSid:
        complete_session(CallSid)
        logger.info("CallSid=%s  hung up", CallSid)
    return Response(content="", media_type=XML)


def _send_email_bg(
    to_email: str,
    history: list[dict],
    anagrafica: dict | None,
    email_body: str | None,
) -> None:
    try:
        send_followup(to_email, history, anagrafica, email_body, claude)
        logger.info("Follow-up email sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
