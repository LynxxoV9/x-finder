import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings

MOCK_NOTION_FILE = Path("./data/mock_notion.json")

def _load_mock_notion() -> List[Dict[str, Any]]:
    """Charge les notes de démonstration Notion."""
    if MOCK_NOTION_FILE.exists():
        try:
            return json.loads(MOCK_NOTION_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Notes par défaut alignées avec les exemples de l'énoncé
    default_notes = [
        {
            "id": "notion_page_01",
            "title": "Notes sur le Machine Learning",
            "content": (
                "Rappel des fondamentaux : Gradient Descent, Transformers, Attention Mechanism.\n"
                "Différence entre Fine-tuning et In-Context Learning.\n"
                "Les agents autonomes exploitent le Tool Calling pour combler le manque de données temps réel."
            ),
            "tags": ["Machine Learning", "IA", "Cours"]
        },
        {
            "id": "notion_page_02",
            "title": "Compte rendu de la dernière réunion",
            "content": (
                "Ordre du jour : Conception de l'agent X-Finder.\n"
                "Décisions prises :\n"
                "1. Spécialisation OSINT & CTI pour la veille de menaces.\n"
                "2. Intégration de la recherche multimodale (image + texte).\n"
                "3. Déploiement sécurisé avec validation explicite des actions sensibles (emails, suppressions)."
            ),
            "tags": ["Réunion", "Projet", "X-Finder"]
        },
        {
            "id": "notion_page_03",
            "title": "Recherches sur les agents IA",
            "content": (
                "Étude comparative : ReAct (Reasoning + Acting), LangGraph, PydanticAI.\n"
                "Importance du tool calling dynamique et de la gestion des états."
            ),
            "tags": ["Recherche", "Agents"]
        }
    ]
    MOCK_NOTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    MOCK_NOTION_FILE.write_text(json.dumps(default_notes, indent=2), encoding="utf-8")
    return default_notes

def _save_mock_notion(notes: List[Dict[str, Any]]) -> None:
    MOCK_NOTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    MOCK_NOTION_FILE.write_text(json.dumps(notes, indent=2), encoding="utf-8")


def search_notion(query: str) -> Dict[str, Any]:
    """
    Recherche des pages et des notes dans Notion correspondant à une requête.
    """
    # Si la clé Notion officielle est présente
    if settings.NOTION_API_KEY and settings.NOTION_API_KEY.startswith("secret_"):
        try:
            url = "https://api.notion.com/v1/search"
            headers = {
                "Authorization": f"Bearer {settings.NOTION_API_KEY}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            payload = {"query": query, "page_size": 5}
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    pages = []
                    for item in data.get("results", []):
                        title = "Sans titre"
                        title_props = item.get("properties", {}).get("title", {}).get("title", [])
                        if title_props:
                            title = title_props[0].get("plain_text", title)
                        pages.append({
                            "id": item.get("id"),
                            "title": title,
                            "url": item.get("url"),
                            "type": item.get("object")
                        })
                    return {
                        "status": "success",
                        "source": "Notion API (Live)",
                        "count": len(pages),
                        "results": pages
                    }
        except Exception:
            pass

    # Mode démonstration sécurisée
    notes = _load_mock_notion()
    q_lower = query.lower()
    matches = []
    for n in notes:
        if q_lower in n.get("title", "").lower() or q_lower in n.get("content", "").lower():
            matches.append({
                "id": n.get("id"),
                "title": n.get("title"),
                "summary": n.get("content")[:120] + "...",
                "tags": n.get("tags", [])
            })
    return {
        "status": "success",
        "source": "Notion (Espace de test/Démo)",
        "query": query,
        "count": len(matches),
        "results": matches
    }


def read_notion_page(page_id: str) -> Dict[str, Any]:
    """
    Lit le contenu textuel complet d'une page ou d'une note Notion.
    """
    if settings.NOTION_API_KEY and settings.NOTION_API_KEY.startswith("secret_"):
        try:
            url = f"https://api.notion.com/v1/blocks/{page_id}/children"
            headers = {
                "Authorization": f"Bearer {settings.NOTION_API_KEY}",
                "Notion-Version": "2022-06-28"
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.get(url, headers=headers)
                if res.status_code == 200:
                    blocks = res.json().get("results", [])
                    extracted_text = []
                    for b in blocks:
                        b_type = b.get("type")
                        content_list = b.get(b_type, {}).get("rich_text", [])
                        for c in content_list:
                            extracted_text.append(c.get("plain_text", ""))
                    return {
                        "status": "success",
                        "source": "Notion API (Live)",
                        "page_id": page_id,
                        "content": "\n".join(extracted_text)
                    }
        except Exception:
            pass

    # Recherche dans le mock
    notes = _load_mock_notion()
    for n in notes:
        if n.get("id") == page_id or page_id.lower() in n.get("title", "").lower():
            return {
                "status": "success",
                "source": "Notion (Espace de test/Démo)",
                "page_id": n.get("id"),
                "title": n.get("title"),
                "content": n.get("content")
            }

    return {"status": "error", "message": f"Page Notion ID '{page_id}' introuvable."}


def create_notion_page(title: str, content: str, parent_page_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Crée une nouvelle page ou note dans Notion.
    """
    parent_id = parent_page_id or settings.NOTION_DEFAULT_PARENT_PAGE_ID
    if settings.NOTION_API_KEY and parent_id:
        try:
            url = "https://api.notion.com/v1/pages"
            headers = {
                "Authorization": f"Bearer {settings.NOTION_API_KEY}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json"
            }
            payload = {
                "parent": {"page_id": parent_id},
                "properties": {
                    "title": [{"type": "text", "text": {"content": title}}]
                },
                "children": [
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": content}}]
                        }
                    }
                ]
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    return {
                        "status": "success",
                        "source": "Notion API (Live)",
                        "message": f"Page '{title}' créée dans Notion.",
                        "page_id": res.json().get("id")
                    }
        except Exception:
            pass

    # Ajout local dans le mock
    notes = _load_mock_notion()
    new_page = {
        "id": f"notion_page_{int(datetime_now().timestamp())}",
        "title": title,
        "content": content,
        "tags": ["Agent X-Finder"]
    }
    notes.append(new_page)
    _save_mock_notion(notes)

    return {
        "status": "success",
        "source": "Notion (Espace de test/Démo)",
        "message": f"Page '{title}' créée avec succès dans Notion.",
        "page_id": new_page["id"]
    }


def append_to_notion_page(page_id: str, content_to_append: str) -> Dict[str, Any]:
    """
    Ajoute du contenu supplémentaire à une page Notion existante.
    """
    notes = _load_mock_notion()
    for n in notes:
        if n.get("id") == page_id or page_id.lower() in n.get("title", "").lower():
            n["content"] = n.get("content", "") + "\n" + content_to_append
            _save_mock_notion(notes)
            return {
                "status": "success",
                "message": f"Contenu ajouté à la page '{n.get('title')}'.",
                "page_id": n.get("id")
            }

    return {"status": "error", "message": f"Page '{page_id}' introuvable pour ajout."}

from datetime import datetime
def datetime_now():
    return datetime.utcnow()
