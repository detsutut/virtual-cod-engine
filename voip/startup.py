import logging
import os

import httpx
from twilio.rest import Client as TwilioClient

import config

logger = logging.getLogger(__name__)


async def configure_twilio_webhook() -> str:
    """
    1. Detect the public URL from a running ngrok tunnel (localhost:4040).
       Falls back to the BASE_URL env var if ngrok is not running.
    2. Update the Twilio phone number webhook to point at /call/answer.
    3. Set config.BASE_URL so TwiML builders pick up the correct host.
    """
    base_url = os.getenv("BASE_URL", "").rstrip("/")

    if not base_url:
        base_url = await _get_ngrok_url()

    if not base_url:
        raise RuntimeError(
            "Could not determine BASE_URL. "
            "Start ngrok (`ngrok http 8000`) or set BASE_URL in .env"
        )

    config.BASE_URL = base_url
    logger.info("BASE_URL set to %s", base_url)

    try:
        await _update_twilio_webhook(base_url)
    except Exception as exc:
        logger.warning("Twilio webhook auto-config failed: %s", exc)
    return base_url


async def _get_ngrok_url() -> str:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get("http://127.0.0.1:4040/api/tunnels")
            resp.raise_for_status()
            tunnels = resp.json().get("tunnels", [])
            for t in tunnels:
                if t.get("proto") == "https":
                    return t["public_url"].rstrip("/")
    except Exception as exc:
        logger.warning("Could not reach ngrok API: %s", exc)
    return ""


async def _update_twilio_webhook(base_url: str) -> None:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    phone_sid = os.getenv("TWILIO_PHONE_NUMBER_SID")

    if not all([account_sid, auth_token, phone_sid]):
        logger.warning(
            "Twilio credentials incomplete — skipping webhook auto-config. "
            "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER_SID in .env"
        )
        return

    twilio = TwilioClient(account_sid, auth_token)
    twilio.incoming_phone_numbers(phone_sid).update(
        voice_url=f"{base_url}/call/answer",
        voice_method="POST",
        status_callback=f"{base_url}/call/hangup",
        status_callback_method="POST",
    )
    logger.info("Twilio webhook updated → %s/call/answer", base_url)
