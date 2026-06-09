from twilio.twiml.voice_response import Gather, VoiceResponse

import config

# Polly.Bianca is Amazon Polly Italian female, available on standard Twilio accounts.
# Fallback: use voice="alice" language="it-IT" if Polly is not enabled on your account.
_VOICE = "Polly.Bianca"
_LANGUAGE = "it-IT"


def _transcribe_url() -> str:
    return f"{config.BASE_URL}/call/transcribed"


def _no_input_url() -> str:
    return f"{config.BASE_URL}/call/no-input"


def gather_response(text: str) -> str:
    """Say `text` while listening for speech (barge-in enabled). On timeout → /call/no-input."""
    r = VoiceResponse()
    gather = Gather(
        input="speech",
        action=_transcribe_url(),
        method="POST",
        speech_timeout="auto",
        timeout=10,
        language=_LANGUAGE,
    )
    gather.say(text, voice=_VOICE)
    r.append(gather)
    # Fallthrough if Gather times out without speech
    r.redirect(_no_input_url(), method="POST")
    return str(r)


def hangup_response(text: str) -> str:
    """Say `text` then hang up."""
    r = VoiceResponse()
    r.say(text, voice=_VOICE)
    r.hangup()
    return str(r)
