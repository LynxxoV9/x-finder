import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any
from pathlib import Path
import json
from datetime import datetime, timezone
from app.config import settings

OUTBOX_LOG_FILE = Path("./data/email_outbox.json")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def smtp_status() -> Dict[str, Any]:
    """État de la configuration SMTP sans exposer la clé SMTP."""
    user = (settings.SMTP_USER or "").strip()
    password = (settings.SMTP_PASSWORD or "").strip()
    from_email = (settings.SMTP_FROM_EMAIL or "").strip()
    ready = bool(user and password and from_email)
    return {
        "configured": ready,
        "host": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
        "user": user or None,
        "from_email": from_email or None,
        "use_tls": settings.SMTP_USE_TLS,
        "mode": "live_smtp" if ready else "sandbox_simulation",
        "hint": None
        if ready
        else (
            "Configurez SMTP_USER, la clé SMTP dans SMTP_PASSWORD et l'adresse "
            "d'expéditeur validée par Brevo dans SMTP_FROM_EMAIL."
        ),
    }


def _log_sent_email(to_email: str, subject: str, body: str, status: str) -> None:
    OUTBOX_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if OUTBOX_LOG_FILE.exists():
        try:
            history = json.loads(OUTBOX_LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            history = []
    history.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "to": to_email,
        "subject": subject,
        "body": body,
        "status": status,
        "from": settings.SMTP_FROM_EMAIL or settings.SMTP_USER or None,
    })
    OUTBOX_LOG_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")


def prepare_email_draft(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Prépare un brouillon d'email. Aucun envoi sans confirmation utilisateur.
    Utile après une recherche OSINT : coller le rapport dans `body` et viser un destinataire précis.
    """
    to_clean = (to_email or "").strip()
    subject_clean = (subject or "").strip()
    body_clean = (body or "").strip()

    if not to_clean or not EMAIL_RE.match(to_clean):
        return {
            "status": "need_info",
            "missing_field": "to_email",
            "message": "Adresse email du destinataire invalide ou manquante.",
        }
    if not subject_clean:
        return {
            "status": "need_info",
            "missing_field": "subject",
            "message": "Veuillez renseigner un objet pour cet email.",
        }
    if not body_clean:
        return {
            "status": "need_info",
            "missing_field": "body",
            "message": "Le contenu de l'email est vide.",
        }

    smtp = smtp_status()
    from_addr = smtp["from_email"] or "agent-xfinder@local"

    return {
        "status": "draft_ready",
        "requires_confirmation": True,
        "confirmation_action": "send_email",
        "smtp": smtp,
        "draft": {
            "to": to_clean,
            "subject": subject_clean,
            "body": body_clean,
            "from": from_addr,
        },
        "message": (
            f"Brouillon prêt pour {to_clean} (objet: {subject_clean}). "
            f"Expéditeur configuré: {from_addr}. "
            f"Mode envoi: {smtp['mode']}. "
            "Confirmation utilisateur requise avant expédition réelle."
        ),
    }


def send_email_confirmed(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    """Envoi SMTP effectif après confirmation. Refuse le silence : signale clairement le mode sandbox."""
    to_clean = (to_email or "").strip()
    if not to_clean or not EMAIL_RE.match(to_clean):
        return {"status": "error", "message": "Destinataire email invalide."}

    smtp = smtp_status()
    if smtp["configured"]:
        try:
            msg = MIMEMultipart()
            msg["From"] = smtp["from_email"]
            msg["To"] = to_clean
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            if settings.SMTP_PORT == 465:
                with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
                    if settings.SMTP_USE_TLS:
                        server.ehlo()
                        server.starttls()
                        server.ehlo()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)

            _log_sent_email(to_clean, subject, body, status="sent_live_smtp")
            return {
                "status": "success",
                "mode": "live_smtp",
                "message": f"Email envoyé à {to_clean} via {settings.SMTP_HOST} (from={smtp['from_email']}).",
                "recipient": to_clean,
                "subject": subject,
            }
        except Exception as e:
            _log_sent_email(to_clean, subject, body, status=f"smtp_error:{type(e).__name__}")
            return {
                "status": "error",
                "mode": "live_smtp",
                "message": f"Échec SMTP : {type(e).__name__}: {e}",
                "recipient": to_clean,
                "hint": (
                    "Vérifiez la clé SMTP, l'identifiant SMTP et que SMTP_FROM_EMAIL "
                    "correspond à un expéditeur validé dans Brevo."
                ),
            }

    _log_sent_email(to_clean, subject, body, status="simulated_sandbox")
    return {
        "status": "warning",
        "mode": "sandbox_simulation",
        "message": (
            "Aucun envoi réel : configuration SMTP incomplète. "
            f"Brouillon archivé dans data/email_outbox.json pour {to_clean}. "
            "Configurez SMTP_USER, SMTP_PASSWORD et SMTP_FROM_EMAIL pour activer l'envoi Brevo."
        ),
        "recipient": to_clean,
        "subject": subject,
        "smtp": smtp,
    }
