import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
from app.config import settings

# Google Calendar API imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BACKEND_DIR.parent
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Stockage local de repli (Mock / Démo sécurisée pour tests sans identifiants privés)
MOCK_CALENDAR_FILE = (
    REPO_ROOT / "data" / "mock_calendar.json"
    if (REPO_ROOT / "data").exists()
    else BACKEND_DIR / "data" / "mock_calendar.json"
)

def _find_google_file(filename: str) -> Path:
    candidates = [
        Path(filename),
        REPO_ROOT / filename,
        BACKEND_DIR / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

def _load_mock_calendar() -> List[Dict[str, Any]]:
    """Charge les événements du calendrier de démonstration si aucun compte Google n'est connecté."""
    if MOCK_CALENDAR_FILE.exists():
        try:
            return json.loads(MOCK_CALENDAR_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Événements par défaut
    now = datetime.utcnow()
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    mock_events = [
        {
            "id": "evt_demo_01",
            "summary": "Réunion Stratégique OSINT & IA",
            "description": "Point d'étape sur le projet X-Finder et architecture agentique.",
            "start": f"{tomorrow}T10:00:00Z",
            "end": f"{tomorrow}T11:30:00Z",
            "location": "Visioconférence Google Meet"
        },
        {
            "id": "evt_demo_02",
            "summary": "Atelier Cybersécurité & CTF",
            "description": "Préparation du CTF universitaire et veille CTI.",
            "start": f"{tomorrow}T14:00:00Z",
            "end": f"{tomorrow}T16:00:00Z",
            "location": "Salle Réseau 402"
        }
    ]
    MOCK_CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    MOCK_CALENDAR_FILE.write_text(json.dumps(mock_events, indent=2), encoding="utf-8")
    return mock_events

def _save_mock_calendar(events: List[Dict[str, Any]]) -> None:
    MOCK_CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    MOCK_CALENDAR_FILE.write_text(json.dumps(events, indent=2), encoding="utf-8")


def _get_calendar_service():
    """Tente d'initialiser le service officiel Google Calendar API OAuth2."""
    if not GOOGLE_LIBS_AVAILABLE:
        return None

    creds = None
    token_path = _find_google_file(settings.GOOGLE_TOKEN_FILE)
    secrets_path = _find_google_file(settings.GOOGLE_CLIENT_SECRETS_FILE)

    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        elif secrets_path.exists():
            # Nécessite un flux interactif local si token absent
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
            except Exception:
                creds = None

    if creds:
        try:
            return build("calendar", "v3", credentials=creds)
        except Exception:
            return None
    return None


def list_events(max_results: int = 10, time_min: Optional[str] = None) -> Dict[str, Any]:
    """
    Affiche les événements à venir dans le Google Calendar.
    """
    service = _get_calendar_service()
    if service:
        try:
            if not time_min:
                time_min = datetime.utcnow().isoformat() + "Z"
            events_result = service.events().list(
                calendarId="primary",
                timeMin=time_min,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            items = events_result.get("items", [])
            formatted = []
            for item in items:
                start = item.get("start", {}).get("dateTime", item.get("start", {}).get("date"))
                end = item.get("end", {}).get("dateTime", item.get("end", {}).get("date"))
                formatted.append({
                    "id": item.get("id"),
                    "summary": item.get("summary", "Sans titre"),
                    "description": item.get("description", ""),
                    "start": start,
                    "end": end,
                    "location": item.get("location", "")
                })
            return {
                "status": "success",
                "source": "Google Calendar API (Live)",
                "count": len(formatted),
                "events": formatted
            }
        except Exception as e:
            pass

    # Mode démonstration sécurisée (si non connecté aux serveurs Google)
    events = _load_mock_calendar()
    return {
        "status": "success",
        "source": "Google Calendar (Environnement de test/Démo)",
        "count": len(events),
        "events": events[:max_results],
        "note": "Connectez vos credentials.json pour synchroniser un compte Google réel."
    }


def search_events(query: str, date: Optional[str] = None) -> Dict[str, Any]:
    """
    Recherche des événements par mot-clé ou pour une date donnée.
    """
    service = _get_calendar_service()
    if service:
        try:
            time_min = f"{date}T00:00:00Z" if date else datetime.utcnow().isoformat() + "Z"
            time_max = f"{date}T23:59:59Z" if date else None
            
            kwargs = {
                "calendarId": "primary",
                "q": query,
                "singleEvents": True,
                "orderBy": "startTime",
                "timeMin": time_min
            }
            if time_max:
                kwargs["timeMax"] = time_max

            events_result = service.events().list(**kwargs).execute()
            items = events_result.get("items", [])
            formatted = [{
                "id": it.get("id"),
                "summary": it.get("summary"),
                "start": it.get("start", {}).get("dateTime", it.get("start", {}).get("date")),
                "end": it.get("end", {}).get("dateTime", it.get("end", {}).get("date")),
                "description": it.get("description", "")
            } for it in items]
            return {"status": "success", "source": "Google Calendar API (Live)", "events": formatted}
        except Exception:
            pass

    # Recherche dans le calendrier de démo
    events = _load_mock_calendar()
    filtered = []
    q_lower = query.lower() if query else ""
    for ev in events:
        match_q = (q_lower in ev.get("summary", "").lower()) or (q_lower in ev.get("description", "").lower()) if q_lower else True
        match_date = date in ev.get("start", "") if date else True
        if match_q and match_date:
            filtered.append(ev)

    return {
        "status": "success",
        "source": "Google Calendar (Environnement de test/Démo)",
        "query": query,
        "date_filter": date,
        "events": filtered
    }


def create_event(summary: str, start_time: str, end_time: Optional[str] = None, description: str = "", location: str = "") -> Dict[str, Any]:
    """
    Crée un nouvel événement dans le calendrier.
    start_time et end_time doivent être au format ISO (ex: '2026-10-22T10:00:00Z').
    """
    if not end_time:
        # Par défaut 1 heure de durée
        try:
            dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_time = (dt + timedelta(hours=1)).isoformat()
        except Exception:
            end_time = start_time

    service = _get_calendar_service()
    if service:
        try:
            event_body = {
                "summary": summary,
                "description": description,
                "location": location,
                "start": {"dateTime": start_time},
                "end": {"dateTime": end_time}
            }
            created = service.events().insert(calendarId="primary", body=event_body).execute()
            return {
                "status": "success",
                "source": "Google Calendar API (Live)",
                "message": f"Événement '{summary}' planifié avec succès.",
                "event_id": created.get("id"),
                "link": created.get("htmlLink")
            }
        except Exception as e:
            pass

    # Ajout dans le calendrier de démo
    events = _load_mock_calendar()
    new_event = {
        "id": f"evt_{int(datetime.utcnow().timestamp())}",
        "summary": summary,
        "description": description,
        "location": location,
        "start": start_time,
        "end": end_time
    }
    events.append(new_event)
    _save_mock_calendar(events)

    return {
        "status": "success",
        "source": "Google Calendar (Environnement de test/Démo)",
        "message": f"Événement '{summary}' planifié avec succès pour {start_time}.",
        "event": new_event
    }


def delete_event(event_id: str) -> Dict[str, Any]:
    """
    Supprime un événement existant dans le calendrier.
    Note : L'agent doit exiger la confirmation de l'utilisateur avant d'appeler cette fonction.
    """
    service = _get_calendar_service()
    if service:
        try:
            service.events().delete(calendarId="primary", eventId=event_id).execute()
            return {"status": "success", "message": f"Événement ID {event_id} supprimé du Google Calendar."}
        except Exception as e:
            return {"status": "error", "message": f"Échec de la suppression sur Google Calendar : {str(e)}"}

    # Suppression dans le calendrier de test
    events = _load_mock_calendar()
    new_events = [e for e in events if e.get("id") != event_id]
    if len(new_events) < len(events):
        _save_mock_calendar(new_events)
        return {"status": "success", "message": f"Événement ID {event_id} supprimé avec succès."}
    return {"status": "warning", "message": f"Événement ID {event_id} introuvable."}
