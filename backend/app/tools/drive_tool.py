import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import settings

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

MOCK_DRIVE_DIR = (
    REPO_ROOT / "data" / "mock_drive"
    if (REPO_ROOT / "data").exists()
    else BACKEND_DIR / "data" / "mock_drive"
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

def _init_mock_drive() -> None:
    """Crée les documents de test Google Drive recommandés par l'énoncé."""
    MOCK_DRIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    doc1 = MOCK_DRIVE_DIR / "Proposition_de_projet_X-Finder.txt"
    if not doc1.exists():
        doc1.write_text(
            "Proposition de Projet : Agent Personnel X-Finder\n"
            "Auteur : Kokou Olivier FIABI (lynxxoven)\n"
            "Objectif : Agent autonome de nouvelle génération combinant le tool calling avec des capacités avancées "
            "de reconnaissance OSINT, de veille CTI et de détection d'opportunités (stages, CTF, hackathons).\n"
            "Architecture : FastAPI asynchrone, intégration RodiumAI, stockage SQLite et sécurité renforcée.\n"
            "Budget temps : 2 semaines pour validation complète et déploiement public.",
            encoding="utf-8"
        )

    doc2 = MOCK_DRIVE_DIR / "Assignment_Agents_IA_Tool_Calling.txt"
    if not doc2.exists():
        doc2.write_text(
            "Cahier des charges de l'Assignment :\n"
            "- Outils requis : Recherche Internet (Tavily), Météo, Google Calendar, Envoi Email (SMTP), "
            "Google Drive et Notion.\n"
            "- Exigence clé : L'agent doit choisir dynamiquement ses outils et combiner plusieurs outils "
            "dans un même workflow (défi final).\n"
            "- Sécurité : Les suppressions et envois d'emails doivent être confirmés par l'utilisateur.",
            encoding="utf-8"
        )

_init_mock_drive()


def _get_drive_service():
    """Initialise le service Google Drive officiel si credentials valides."""
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
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
            except Exception:
                creds = None

    if creds and creds.valid:
        try:
            return build("drive", "v3", credentials=creds)
        except Exception:
            return None
    return None


def search_drive_files(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Recherche des fichiers dans Google Drive par nom ou mot-clé dans le contenu.
    """
    service = _get_drive_service()
    if service:
        try:
            q_filter = f"name contains '{query}' or fullText contains '{query}'"
            response = service.files().list(
                q=q_filter,
                pageSize=max_results,
                fields="files(id, name, mimeType, webViewLink, createdTime)"
            ).execute()
            files = response.get("files", [])
            return {
                "status": "success",
                "source": "Google Drive API (Live)",
                "query": query,
                "count": len(files),
                "files": files
            }
        except Exception:
            pass

    # Recherche dans le dossier Drive local de test
    matches = []
    q_lower = query.lower()
    for file_path in MOCK_DRIVE_DIR.glob("*.*"):
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        if q_lower in file_path.name.lower() or q_lower in content.lower():
            matches.append({
                "id": file_path.stem,
                "name": file_path.name,
                "mimeType": "text/plain",
                "path": str(file_path),
                "preview": content[:150] + "..."
            })

    return {
        "status": "success",
        "source": "Google Drive (Espace de test/Démo)",
        "query": query,
        "count": len(matches),
        "files": matches
    }


def read_drive_file_content(file_id_or_name: str) -> Dict[str, Any]:
    """
    Lit et extrait le contenu textuel d'un document Google Drive (Google Docs ou fichier texte).
    """
    service = _get_drive_service()
    if service:
        try:
            # Récupération des métadonnées pour vérifier le mimeType
            file_meta = service.files().get(fileId=file_id_or_name, fields="name, mimeType").execute()
            mime = file_meta.get("mimeType", "")
            
            if "google-apps.document" in mime:
                # Exporter le Google Doc en texte brut
                content = service.files().export(fileId=file_id_or_name, mimeType="text/plain").execute()
                return {
                    "status": "success",
                    "source": "Google Drive API (Live)",
                    "name": file_meta.get("name"),
                    "content": content.decode("utf-8") if isinstance(content, bytes) else str(content)
                }
            else:
                content = service.files().get_media(fileId=file_id_or_name).execute()
                return {
                    "status": "success",
                    "source": "Google Drive API (Live)",
                    "name": file_meta.get("name"),
                    "content": content.decode("utf-8") if isinstance(content, bytes) else str(content)
                }
        except Exception:
            pass

    # Recherche dans le mock drive
    q_lower = file_id_or_name.lower()
    for file_path in MOCK_DRIVE_DIR.glob("*.*"):
        if q_lower in file_path.name.lower() or q_lower in file_path.stem.lower():
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            return {
                "status": "success",
                "source": "Google Drive (Espace de test/Démo)",
                "name": file_path.name,
                "file_id": file_path.stem,
                "content": content
            }

    return {"status": "error", "message": f"Fichier Google Drive '{file_id_or_name}' introuvable."}
