import json
from typing import Dict, Any, Callable
from app.tools.web_search import search_web
from app.tools.weather import get_weather
from app.tools.calendar_tool import list_events, search_events, create_event, delete_event
from app.tools.email_tool import prepare_email_draft, send_email_confirmed
from app.tools.notion_tool import search_notion, read_notion_page, create_notion_page, append_to_notion_page
from app.tools.drive_tool import search_drive_files, read_drive_file_content
from app.tools.osint_tools import (
    recon_social_profile,
    investigate_person_osint,
    cti_threat_lookup,
    hunt_opportunities,
)
from app.tools.vision_recon import analyze_image_intel
from app.tools.rag_engine import query_local_knowledge
from app.tools.email_osint import (
    investigate_email_osint,
    investigate_username_osint,
    harvest_domain_intel,
    generate_osint_graph,
)

# Définition des schémas des outils au standard OpenAI / RodiumAI
TOOL_DEFINITIONS = [
    # 1. Recherche Internet
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Recherche web temps réel (Tavily si clé valide, sinon DuckDuckGo). Retourne titres, URLs, extraits et indicateur security_authority. Pour toute question sur la CVE la plus récente, interroger la période actuelle et vérifier les dates dans des sources officielles ; l'ordre du moteur n'est pas chronologique.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "La requête de recherche en texte clair"},
                    "search_depth": {"type": "string", "enum": ["basic", "advanced"], "default": "basic"},
                    "max_results": {"type": "integer", "default": 5},
                    "include_news": {"type": "boolean", "default": False, "description": "Filtrer spécifiquement sur les actualités récentes"}
                },
                "required": ["query"]
            }
        }
    },
    # 2. Météo
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Consulte la météo actuelle et les prévisions pour une ou plusieurs villes (comparaison possible).",
            "parameters": {
                "type": "object",
                "properties": {
                    "cities": {
                        "type": "string",
                        "description": "Nom de la ville ou liste de villes séparées par des virgules (ex: 'Lomé' ou 'Lagos, Accra')"
                    },
                    "days": {"type": "integer", "default": 1, "description": "Nombre de jours de prévisions"}
                },
                "required": ["cities"]
            }
        }
    },
    # 3. Google Calendar
    {
        "type": "function",
        "function": {
            "name": "list_calendar_events",
            "description": "Liste les prochains événements programmés dans Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "default": 10},
                    "time_min": {"type": "string", "description": "Date de départ en format ISO (ex: '2026-10-22T00:00:00Z')"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_calendar_events",
            "description": "Recherche des événements dans Google Calendar par mot-clé ou date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Mot-clé ou objet de l'événement"},
                    "date": {"type": "string", "description": "Date au format AAAA-MM-JJ (ex: '2026-10-22')"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": "Planifie un nouvel événement dans Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Titre ou objet de l'événement"},
                    "start_time": {"type": "string", "description": "Date et heure de début en ISO (ex: '2026-10-22T14:00:00Z')"},
                    "end_time": {"type": "string", "description": "Date et heure de fin en ISO"},
                    "description": {"type": "string", "description": "Description détaillée"},
                    "location": {"type": "string", "description": "Lieu ou lien de réunion"}
                },
                "required": ["summary", "start_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": "Supprime un événement Google Calendar. Attention : requiert la confirmation explicite de l'utilisateur.",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {"type": "string", "description": "Identifiant de l'événement à supprimer"}
                },
                "required": ["event_id"]
            }
        }
    },
    # 4. Envoi d'emails (SMTP)
    {
        "type": "function",
        "function": {
            "name": "prepare_email_draft",
            "description": "Prépare un brouillon d'email (ex: envoyer un rapport OSINT/météo à flowoliv@gmail.com) pour validation AVANT envoi. Corps = faits issus des outils uniquement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_email": {"type": "string", "description": "Adresse email du destinataire (ex: flowoliv@gmail.com)"},
                    "subject": {"type": "string", "description": "Objet de l'email"},
                    "body": {"type": "string", "description": "Contenu complet : rapport synthétique avec sources/URLs réelles"}
                },
                "required": ["to_email", "subject", "body"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "send_email_confirmed",
            "description": "Expédition SMTP réelle après confirmation explicite. Échoue clairement si SMTP_PASSWORD absent (pas de faux succès silencieux).",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_email": {"type": "string", "description": "Adresse email du destinataire"},
                    "subject": {"type": "string", "description": "Objet"},
                    "body": {"type": "string", "description": "Corps du message"}
                },
                "required": ["to_email", "subject", "body"]
            }
        }
    },
    # 5. Notion
    {
        "type": "function",
        "function": {
            "name": "search_notion",
            "description": "Recherche des pages, documents et notes dans l'espace Notion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Terme ou sujet à rechercher dans Notion"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_notion_page",
            "description": "Lit le contenu textuel complet d'une page Notion à partir de son identifiant ou titre.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "ID ou titre de la page Notion"}
                },
                "required": ["page_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_notion_page",
            "description": "Crée une nouvelle page ou note dans Notion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Titre de la nouvelle page"},
                    "content": {"type": "string", "description": "Contenu textuel de la page"},
                    "parent_page_id": {"type": "string", "description": "ID optionnel de la page parente"}
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_notion_page",
            "description": "Ajoute du texte ou des notes à une page Notion existante.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "ID ou titre de la page Notion"},
                    "content_to_append": {"type": "string", "description": "Nouveau contenu à ajouter"}
                },
                "required": ["page_id", "content_to_append"]
            }
        }
    },
    # 6. Google Drive
    {
        "type": "function",
        "function": {
            "name": "search_drive_files",
            "description": "Recherche des documents et fichiers dans Google Drive.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Nom de fichier ou sujet à rechercher"},
                    "max_results": {"type": "integer", "default": 5}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_drive_file_content",
            "description": "Extrait et lit le contenu textuel d'un document Google Drive (Google Docs, texte, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_id_or_name": {"type": "string", "description": "Identifiant ou nom du fichier Drive"}
                },
                "required": ["file_id_or_name"]
            }
        }
    },
    # 7. Super-pouvoirs OSINT & CTI & Hunter
    {
        "type": "function",
        "function": {
            "name": "recon_social_profile",
            "description": "Reconnaissance OSINT sur un identifiant public pour une plateforme donnée. Ne confirme un profil que s'il y a des preuves web.",
            "parameters": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "description": "Plateforme (linkedin, github, twitter, instagram, facebook, youtube, auto, ...)"},
                    "identifier": {"type": "string", "description": "Nom d'utilisateur, URL ou pseudonyme"}
                },
                "required": ["platform", "identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "investigate_person_osint",
            "description": "OSINT sur un NOM COMPLET (civil/public), tous secteurs. Pas pour un email. Retourne sources web, emails/handles éventuels sans invention.",
            "parameters": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string", "description": "Nom et prénom(s) de la cible"},
                    "location_hint": {"type": "string", "description": "Indice géographique optionnel (ex: Togo, Lomé, France)"}
                },
                "required": ["full_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "investigate_username_osint",
            "description": "OSINT sur un PSEUDONYME/HANDLE : sondage multi-plateformes (social, jeux, musique, code...) + traces web. Pas limité au milieu tech.",
            "parameters": {
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "Pseudonyme sans @ (ex: flowoliv, Lynxxov9)"}
                },
                "required": ["username"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cti_threat_lookup",
            "description": "Veille CTI sur une CVE nommée, un acteur de menace, un malware ou un IOC. Pour déterminer la CVE la plus récente, cet outil seul ne suffit pas : effectuer une recherche datée dans les sources officielles CVE/NVD/CISA.",
            "parameters": {
                "type": "object",
                "properties": {
                    "indicator_or_cve": {"type": "string", "description": "Référence CVE (ex: 'CVE-2024-3094') ou nom de menace"}
                },
                "required": ["indicator_or_cve"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "hunt_opportunities",
            "description": "Chasse les opportunités : stages, offres d'emploi, hackathons et compétitions CTF.",
            "parameters": {
                "type": "object",
                "properties": {
                    "opportunity_type": {"type": "string", "enum": ["stage", "emploi", "hackathon", "ctf"], "default": "stage"},
                    "domain": {"type": "string", "default": "cybersécurité"},
                    "location": {"type": "string", "default": "Togo, France, Remote"}
                }
            }
        }
    },
    # 8. Analyse visuelle multimodale (Image)
    {
        "type": "function",
        "function": {
            "name": "analyze_image_intel",
            "description": "Analyse une image pour investigation OSINT : OCR, métadonnées EXIF, schémas techniques et indices visuels.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path_or_base64": {"type": "string", "description": "Chemin local du fichier image ou chaîne base64"},
                    "task": {"type": "string", "default": "general_osint", "description": "Objectif d'analyse"}
                },
                "required": ["image_path_or_base64"]
            }
        }
    },
    # 9. RAG local
    {
        "type": "function",
        "function": {
            "name": "query_local_knowledge",
            "description": "Interroge la base de connaissances locale (RAG) pour retrouver des cours, playbooks et documentations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Question ou terme de recherche"},
                    "top_k": {"type": "integer", "default": 3}
                },
                "required": ["query"]
            }
        }
    },
    # 10. Investigation OSINT Avancée sur Email (Style Holehe / Footprint)
    {
        "type": "function",
        "function": {
            "name": "investigate_email_osint",
            "description": "À utiliser STRICTEMENT et UNIQUEMENT lorsqu'une adresse email valide (format user@domain.tld ou user.name@domain.sousdomain) est fournie. NE PAS UTILISER pour des noms de personnes. Investigation OSINT approfondie sur une adresse email : détection de profil Gravatar, traces GitHub, commits, présences de comptes et indices de confiance avec preuves.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "Adresse email cible à investiguer (ex: 'user@domain.com')"}
                },
                "required": ["email"]
            }
        }
    },
    # 11. Récolte theHarvester sur un nom de domaine
    {
        "type": "function",
        "function": {
            "name": "harvest_domain_intel",
            "description": "Récolte OSINT façon theHarvester sur un domaine : DNS (MX, SPF, DMARC), sous-domaines (crt.sh) et adresses emails associées à l'organisation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string", "description": "Nom de domaine cible (ex: 'gouv.tg' ou 'entreprise.com')"},
                    "max_emails": {"type": "integer", "default": 15}
                },
                "required": ["domain"]
            }
        }
    },
    # 12. Génération d'organigramme / Graphe relationnel Maltego
    {
        "type": "function",
        "function": {
            "name": "generate_osint_graph",
            "description": "Génère un diagramme Mermaid d'organigramme relationnel reliant l'email cible à son domaine, ses comptes et ses emails collaborateurs (style Maltego).",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_email": {"type": "string", "description": "L'email cible"},
                    "domain": {"type": "string", "description": "Le nom de domaine"},
                    "associated_names": {"type": "array", "items": {"type": "string"}, "description": "Noms réels découverts"},
                    "discovered_accounts": {"type": "array", "items": {"type": "object"}, "description": "Plateformes découvertes"},
                    "related_emails": {"type": "array", "items": {"type": "string"}, "description": "Emails reliés dans la même organisation"},
                    "repositories": {"type": "array", "items": {"type": "string"}, "description": "Dépôts ou projets publics découverts"},
                    "skills_or_bio": {"type": "string", "description": "Biographie ou compétences extraites"}
                },
                "required": ["target_email"]
            }
        }
    }
]

# Table d'aiguillage reliant les noms de fonctions aux implémentations Python
FUNCTION_MAP: Dict[str, Callable] = {
    "search_web": search_web,
    "get_weather": get_weather,
    "list_calendar_events": list_events,
    "search_calendar_events": search_events,
    "create_calendar_event": create_event,
    "delete_calendar_event": delete_event,
    "prepare_email_draft": prepare_email_draft,
    "send_email_confirmed": send_email_confirmed,
    "search_notion": search_notion,
    "read_notion_page": read_notion_page,
    "create_notion_page": create_notion_page,
    "append_to_notion_page": append_to_notion_page,
    "search_drive_files": search_drive_files,
    "read_drive_file_content": read_drive_file_content,
    "recon_social_profile": recon_social_profile,
    "investigate_person_osint": investigate_person_osint,
    "investigate_username_osint": investigate_username_osint,
    "cti_threat_lookup": cti_threat_lookup,
    "hunt_opportunities": hunt_opportunities,
    "analyze_image_intel": analyze_image_intel,
    "query_local_knowledge": query_local_knowledge,
    "investigate_email_osint": investigate_email_osint,
    "harvest_domain_intel": harvest_domain_intel,
    "generate_osint_graph": generate_osint_graph,
}

def _attach_grounding(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Annotate tool output so the LLM cannot treat weak/ambiguous hits as hard facts."""
    if not isinstance(result, dict):
        return {"status": "error", "message": "Résultat d'outil invalide."}

    out = dict(result)
    out["_grounding"] = {
        "tool": tool_name,
        "rule": (
            "N'affirme un fait que s'il apparaît explicitement dans ce JSON. "
            "Sources reliability=low (Facebook/forums) = indices seulement. "
            "Si le champ demandé est absent : répondre « Non confirmé »."
        ),
    }

    if tool_name == "search_web" and isinstance(out.get("results"), list):
        hard = [r for r in out["results"] if r.get("use_as_hard_fact") or r.get("reliability") == "high"]
        weak = [r for r in out["results"] if r.get("reliability") == "low"]
        cyber_authorities = [r for r in out["results"] if r.get("security_authority") is True]
        out["hard_fact_candidates"] = [
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
            for r in hard
        ]
        out["cyber_authority_candidates"] = [
            {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
            for r in cyber_authorities
        ]
        out["weak_sources_do_not_assert_from_alone"] = [
            {"title": r.get("title"), "url": r.get("url")}
            for r in weak
        ]
        if out.get("results") and not cyber_authorities:
            out["cybersecurity_grounding_advice"] = (
                "Aucun avis officiel CVE/NVD/CISA ou fournisseur identifié. "
                "N'affirme pas de détails techniques ni de classement chronologique de CVE."
            )
        if not hard and out.get("results"):
            out["grounding_advice"] = (
                "Aucune source high-reliability. Ne confirme pas de faits biographiques "
                "sensibles ; dis « Non confirmé » ou cite prudemment avec URLs."
            )

    return out


def execute_tool_call(tool_name: str, arguments_json: str) -> Dict[str, Any]:
    """Exécute un appel d'outil de manière sécurisée en analysant ses arguments JSON."""
    if tool_name not in FUNCTION_MAP:
        return {"status": "error", "message": f"Outil '{tool_name}' non enregistré."}

    func = FUNCTION_MAP[tool_name]
    try:
        kwargs = json.loads(arguments_json) if arguments_json else {}
    except Exception as e:
        return {"status": "error", "message": f"Arguments JSON invalides : {str(e)}"}

    try:
        result = func(**kwargs)
        if isinstance(result, dict):
            return _attach_grounding(tool_name, result)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": f"Erreur lors de l'exécution de '{tool_name}' : {str(e)}"}
