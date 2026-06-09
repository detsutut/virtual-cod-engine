import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from claude_client import ClaudeClient


def send_followup(
    to_email: str,
    history: list[dict],
    anagrafica: dict | None,
    email_body: str | None,
    claude: ClaudeClient,
) -> None:
    """Generate (if needed) and send the follow-up email via SMTP."""
    if not email_body:
        email_body = claude.generate_email_body(history, anagrafica)

    nome_assistito = ""
    if anagrafica:
        a = anagrafica.get("assistito", {})
        u = anagrafica.get("utente", {})
        nome_assistito = a.get("nome") or u.get("nome") or ""

    subject = (
        f"Virtual COD — Riepilogo informazioni"
        + (f" per {nome_assistito}" if nome_assistito else "")
    )

    msg = MIMEMultipart()
    msg["From"] = os.environ["FROM_EMAIL"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(email_body, "plain", "utf-8"))

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        smtp.sendmail(os.environ["FROM_EMAIL"], to_email, msg.as_string())
