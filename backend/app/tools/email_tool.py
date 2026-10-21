import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from pathlib import Path
import json
from datetime import datetime
from app.config import settings

OUTBOX_LOG_FILE = Path("./data/email_outbox.json")

def _log_sent_email(to_email: str, subject: str, body: str, status: str) -> None:
    """Enregistre l'historique des emails envoyés (pour traçabilité et démonstration)."""
    OUTBOX_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    history = []
    if OUTBOX_LOG_FILE.exists():
        try:
            history = json.loads(OUTBOX_LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    history.append({
        "timestamp": datetime.utcnow().isoformat(),
        "to": to_email,
        "subject": subject,
        "body": body,
        "status": status
    })
    OUTBOX_LOG_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")


def prepare_email_draft(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Prépare un projet d'email et le présente pour confirmation obligatoire par l'utilisateur.
    Conformément aux consignes de sécurité, aucun email n'est expédié sans accord explicite.
    """
    if not to_email or "@" not in to_email:
        return {
            "status": "need_info",
            "missing_field": "to_email",
            "message": "Adresse email du destinataire invalide ou manquante."
        }
    if not subject:
        return {
            "status": "need_info",
            "missing_field": "subject",
            "message": "Veuillez renseigner un objet pour cet email."
        }
    if not body:
        return {
            "status": "need_info",
            "missing_field": "body",
            "message": "Le contenu de l'email est vide."
        }

    # Projet d'email prêt, nécessite confirmation explicite
    return {
        "status": "draft_ready",
        "requires_confirmation": True,
        "confirmation_action": "send_email",
        "draft": {
            "to": to_email,
            "subject": subject,
            "body": body,
            "from": settings.SMTP_FROM_EMAIL or "agent-xfinder@ai.local"
        },
        "message": (
            f"Brouillon d'email préparé pour **{to_email}** avec l'objet *'{subject}'*.\n\n"
            f"**Aperçu du contenu :**\n> {body.replace(chr(10), chr(10) + '> ')}\n\n"
            "⚠️ **Confirmation requise :** Souhaitez-vous que j'expédie cet email maintenant ?"
        )
    }


def send_email_confirmed(to_email: str, subject: str, body: str) -> Dict[str, Any]:
    """
    Exécute l'envoi effectif de l'email via SMTP une fois la confirmation utilisateur obtenue.
    """
    # Si les identifiants SMTP réels sont configurés
    if settings.SMTP_USER and settings.SMTP_PASSWORD:
        try:
            msg = MIMEMultipart()
            msg["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USER
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            if settings.SMTP_PORT == 465:
                # SSL direct
                with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)
            else:
                # STARTTLS
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
                    if settings.SMTP_USE_TLS:
                        server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)

            _log_sent_email(to_email, subject, body, status="sent_live_smtp")
            return {
                "status": "success",
                "message": f"Email envoyé avec succès à {to_email} via le serveur SMTP.",
                "recipient": to_email,
                "subject": subject
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Échec de l'envoi SMTP : {str(e)}",
                "recipient": to_email
            }

    # Mode démonstration / Sandbox sécurisé (si SMTP non configuré)
    _log_sent_email(to_email, subject, body, status="simulated_sandbox")
    return {
        "status": "success",
        "mode": "Sandbox / Démonstration sécurisée",
        "message": f"[Simulation d'envoi réussi] L'email à destination de {to_email} a été validé et archivé dans le dossier d'expédition de test (data/email_outbox.json).",
        "recipient": to_email,
        "subject": subject
    }
