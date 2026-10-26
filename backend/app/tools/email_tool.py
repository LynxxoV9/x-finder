import smtplib
import re
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, List, Union
from pathlib import Path
import json
from datetime import datetime, timezone
import uuid
import httpx
from app.config import settings

OUTBOX_LOG_FILE = Path("./data/email_outbox.json")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def smtp_status() -> Dict[str, Any]:
    """État de la configuration email sans exposer les clés."""
    user = (settings.SMTP_USER or "").strip()
    password = (settings.SMTP_PASSWORD or "").strip()
    from_email = (settings.SMTP_FROM_EMAIL or "").strip()
    api_ready = bool((settings.BREVO_API_KEY or "").strip() and from_email)
    smtp_ready = bool(user and password and from_email)
    ready = api_ready or smtp_ready
    return {
        "configured": ready,
        "brevo_api_configured": api_ready,
        "host": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
        "user": user or None,
        "from_email": from_email or None,
        "use_tls": settings.SMTP_USE_TLS,
        "mode": "brevo_api" if api_ready else ("live_smtp" if smtp_ready else "sandbox_simulation"),
        "hint": None
        if ready
        else (
            "Configurez BREVO_API_KEY et SMTP_FROM_EMAIL avec un expéditeur validé dans Brevo. "
            "SMTP_USER/SMTP_PASSWORD restent disponibles comme solution de repli."
        ),
    }


def _normalize_recipients(to_email: Union[str, List[str], None]) -> List[str]:
    if isinstance(to_email, str):
        values = re.split(r"[,;]", to_email)
    elif isinstance(to_email, list):
        values = [email for value in to_email if isinstance(value, str) for email in re.split(r"[,;]", value)]
    else:
        values = []
    recipients = list(dict.fromkeys(email.strip() for email in values if email.strip()))
    if not recipients or any(not EMAIL_RE.match(email) for email in recipients):
        return []
    return recipients


def _build_calendar_ics(event: Dict[str, Any]) -> str:
    summary = str(event.get("summary") or "").strip()
    if not summary:
        raise ValueError("Le titre de l'événement est obligatoire.")

    try:
        start = datetime.fromisoformat(str(event["start"]).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(event["end"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Les dates de début et de fin doivent être des dates ISO valides.") from exc
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("Les dates de l'événement doivent inclure un fuseau horaire.")
    if end <= start:
        raise ValueError("La fin de l'événement doit être postérieure au début.")

    def escape(value: Any) -> str:
        return (
            str(value or "").replace("\\", "\\\\").replace("\r\n", "\n")
            .replace("\r", "\n").replace("\n", "\\n")
            .replace(",", "\\,").replace(";", "\\;")
        )

    def utc_stamp(value: datetime) -> str:
        return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//X-Finder//Calendar Invitation//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid4()}@x-finder",
        f"DTSTAMP:{utc_stamp(datetime.now(timezone.utc))}",
        f"DTSTART:{utc_stamp(start)}",
        f"DTEND:{utc_stamp(end)}",
        f"SUMMARY:{escape(summary)}",
    ]
    if event.get("description"):
        lines.append(f"DESCRIPTION:{escape(event['description'])}")
    if event.get("location"):
        lines.append(f"LOCATION:{escape(event['location'])}")
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\r\n".join(lines) + "\r\n"


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


def prepare_email_draft(
    to_email: Union[str, List[str]],
    subject: str,
    body: str,
    event_summary: str = "",
    event_start: str = "",
    event_end: str = "",
    event_description: str = "",
    event_location: str = "",
) -> Dict[str, Any]:
    """
    Prépare un brouillon d'email. Aucun envoi sans confirmation utilisateur.
    Utile après une recherche OSINT : coller le rapport dans `body` et viser un destinataire précis.
    """
    recipients = _normalize_recipients(to_email)
    subject_clean = (subject or "").strip()
    body_clean = (body or "").strip()

    if not recipients:
        return {
            "status": "need_info",
            "missing_field": "to_email",
            "message": "Adresse(s) email invalide(s) ou manquante(s). Séparez-les par des virgules.",
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

    calendar_event = None
    if any((event_summary, event_start, event_end, event_description, event_location)):
        calendar_event = {
            "summary": event_summary,
            "start": event_start,
            "end": event_end,
            "description": event_description,
            "location": event_location,
        }
        try:
            _build_calendar_ics(calendar_event)
        except ValueError as exc:
            return {
                "status": "need_info",
                "missing_field": "event_details",
                "message": str(exc),
            }

    smtp = smtp_status()
    from_addr = smtp["from_email"] or "agent-xfinder@local"
    draft_recipients: Union[str, List[str]] = recipients[0] if len(recipients) == 1 else recipients
    draft = {
        "to": draft_recipients,
        "subject": subject_clean,
        "body": body_clean,
        "from": from_addr,
    }
    if calendar_event:
        draft["calendar_event"] = calendar_event

    return {
        "status": "draft_ready",
        "requires_confirmation": True,
        "confirmation_action": "send_email",
        "smtp": smtp,
        "draft": draft,
        "message": (
            f"Brouillon prêt pour {len(recipients)} destinataire(s) (objet: {subject_clean}). "
            f"Expéditeur configuré: {from_addr}. "
            f"Mode envoi: {smtp['mode']}. "
            "Confirmation utilisateur requise avant expédition réelle."
            + (" Une pièce jointe invitation.ics sera ajoutée." if calendar_event else "")
        ),
    }


def send_email_confirmed(
    to_email: Union[str, List[str]],
    subject: str,
    body: str,
    calendar_event: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Envoie après confirmation explicite, avec un message distinct par destinataire."""
    recipients = _normalize_recipients(to_email)
    if not recipients:
        return {"status": "error", "message": "Adresse(s) email destinataire(s) invalide(s)."}
    if not subject.strip() or not body.strip():
        return {"status": "error", "message": "L'objet et le contenu de l'email sont obligatoires."}
    try:
        calendar_ics = _build_calendar_ics(calendar_event) if calendar_event else None
    except ValueError as exc:
        return {"status": "error", "message": f"Invitation calendrier invalide : {exc}"}

    smtp = smtp_status()
    if smtp["brevo_api_configured"]:
        results = []
        for recipient in recipients:
            try:
                response = httpx.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={
                        "accept": "application/json",
                        "api-key": settings.BREVO_API_KEY.strip(),
                        "content-type": "application/json",
                    },
                    json={
                        "sender": {"email": smtp["from_email"], "name": "X-Finder"},
                        "to": [{"email": recipient}],
                        "subject": subject,
                        "textContent": body,
                        **({
                            "attachment": [{
                                "name": "invitation.ics",
                                "content": base64.b64encode(calendar_ics.encode("utf-8")).decode("ascii"),
                            }]
                        } if calendar_ics else {}),
                    },
                    timeout=20,
                )
                if 200 <= response.status_code < 300:
                    _log_sent_email(recipient, subject, body, status="sent_brevo_api")
                    results.append({"recipient": recipient, "status": "success"})
                else:
                    _log_sent_email(recipient, subject, body, status=f"brevo_api_error:{response.status_code}")
                    results.append({
                        "recipient": recipient,
                        "status": "error",
                        "message": f"Brevo API a répondu HTTP {response.status_code}.",
                    })
            except httpx.HTTPError as exc:
                _log_sent_email(recipient, subject, body, status=f"brevo_api_error:{type(exc).__name__}")
                results.append({
                    "recipient": recipient,
                    "status": "error",
                    "message": f"Connexion à l'API Brevo impossible ({type(exc).__name__}).",
                })
        succeeded = sum(item["status"] == "success" for item in results)
        result_status = "success" if succeeded == len(recipients) else ("warning" if succeeded else "error")
        return {
            "status": result_status,
            "mode": "brevo_api",
            "message": f"{succeeded}/{len(recipients)} email(s) accepté(s) par l'API Brevo.",
            "recipient_results": results,
            "subject": subject,
        }

    if smtp["configured"]:
        results = []
        for recipient in recipients:
            msg = MIMEMultipart()
            msg["From"] = smtp["from_email"]
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))
            if calendar_ics:
                attachment = MIMEBase("text", "calendar", method="PUBLISH", name="invitation.ics")
                attachment.set_payload(calendar_ics.encode("utf-8"))
                encoders.encode_base64(attachment)
                attachment.add_header("Content-Disposition", "attachment", filename="invitation.ics")
                msg.attach(attachment)

            try:
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
                _log_sent_email(recipient, subject, body, status="sent_live_smtp")
                results.append({"recipient": recipient, "status": "success"})
            except (smtplib.SMTPException, OSError, TimeoutError) as exc:
                _log_sent_email(recipient, subject, body, status=f"smtp_error:{type(exc).__name__}")
                results.append({
                    "recipient": recipient,
                    "status": "error",
                    "message": f"Échec SMTP : {type(exc).__name__}. Sur Render, configurez BREVO_API_KEY pour utiliser HTTPS.",
                })
        succeeded = sum(item["status"] == "success" for item in results)
        result_status = "success" if succeeded == len(recipients) else ("warning" if succeeded else "error")
        return {
            "status": result_status,
            "mode": "live_smtp",
            "message": f"{succeeded}/{len(recipients)} email(s) envoyé(s) via SMTP.",
            "recipient_results": results,
            "subject": subject,
        }

    for recipient in recipients:
        _log_sent_email(recipient, subject, body, status="simulated_sandbox")
    return {
        "status": "warning",
        "mode": "sandbox_simulation",
        "message": (
            "Aucun envoi réel : configuration SMTP incomplète. "
            "Brouillon archivé dans data/email_outbox.json. Configurez BREVO_API_KEY et "
            "SMTP_FROM_EMAIL pour activer l'envoi Brevo par HTTPS."
        ),
        "recipient_count": len(recipients),
        "subject": subject,
        "smtp": smtp,
    }
