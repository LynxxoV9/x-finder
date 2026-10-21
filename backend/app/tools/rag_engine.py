import os
import re
import math
from pathlib import Path
from typing import Dict, Any, List
from collections import Counter
from app.config import settings

# Moteur RAG local (Retrieval-Augmented Generation) pour base de connaissances

KNOWLEDGE_DIR = Path(settings.RAG_DATA_DIR)

def _init_sample_knowledge():
    """Initialise un recueil de connaissances OSINT / Cybersécurité / Agent pour le RAG."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    doc_path = KNOWLEDGE_DIR / "osint_cti_playbook.md"
    if not doc_path.exists():
        doc_path.write_text(
            "# Playbook OSINT & CTI - X-Finder Intelligence Hub\n\n"
            "## 1. Méthodologie OSINT (Open Source Intelligence)\n"
            "- Étape 1 : Collecte passive d'empreintes numériques (DNS, WHOIS, profils sociaux LinkedIn, GitHub, YouTube).\n"
            "- Étape 2 : Corrélation des identifiants et cartographie des relations.\n"
            "- Étape 3 : Analyse des métadonnées (EXIF, répertoires ouverts, versions de logiciels).\n"
            "- Étape 4 : Synthèse exploitable et diffusion sécurisée.\n\n"
            "## 2. Cyber Threat Intelligence (CTI)\n"
            "- Frameworks clés : MITRE ATT&CK, Cyber Kill Chain, Diamond Model.\n"
            "- Indicateurs de compromission (IOC) : Hash SHA256, adresses IP malveillantes, domaines de C2.\n"
            "- CVE Priority Scoring : CVSS v3.1, exploitation active 'in the wild' (CISA KEV catalog).\n\n"
            "## 3. Chasse aux Opportunités Cybersécurité\n"
            "- Plateformes de CTF : CTFtime, Hack The Box, TryHackMe, Root-Me.\n"
            "- Hackathons tech : Devpost, MLH, défis de sécurité gouvernementaux et universitaires.\n"
            "- Bonnes pratiques CV : Mettre en avant les scores CTF, certifications (eJPT, OSCP, CEH) et projets GitHub d'agents IA.\n",
            encoding="utf-8"
        )

_init_sample_knowledge()


def _tokenize(text: str) -> List[str]:
    """Nettoie et segmente un texte en mots-clés minuscules."""
    return [w for w in re.findall(r"\w+", text.lower()) if len(w) > 2]


def query_local_knowledge(query: str, top_k: int = 3) -> Dict[str, Any]:
    """
    Interroge la base de connaissances locale (RAG) pour retrouver les documents et procédures pertinents.
    """
    _init_sample_knowledge()
    query_tokens = _tokenize(query)
    if not query_tokens:
        return {"status": "empty_query", "results": []}

    chunks = []
    # Parcours des fichiers du répertoire de connaissances
    for file_path in KNOWLEDGE_DIR.glob("**/*.*"):
        if file_path.suffix.lower() in [".md", ".txt", ".json"]:
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                # Découpage par sections (titres Markdown ou paragraphes)
                sections = re.split(r"\n(?=##? |\n)", content)
                for i, sec in enumerate(sections):
                    clean_sec = sec.strip()
                    if clean_sec:
                        chunks.append({
                            "file": file_path.name,
                            "section_index": i,
                            "content": clean_sec
                        })
            except Exception:
                pass

    if not chunks:
        return {"status": "no_documents", "message": "Aucun document indexé dans le RAG.", "results": []}

    # Calcul de score de pertinence (TF-IDF simplifié)
    scored_chunks = []
    query_set = set(query_tokens)
    for chunk in chunks:
        chunk_tokens = _tokenize(chunk["content"])
        if not chunk_tokens:
            continue
        token_counts = Counter(chunk_tokens)
        
        # Score basé sur la correspondance des termes
        score = sum(token_counts[t] for t in query_set if t in token_counts)
        if score > 0:
            scored_chunks.append((score, chunk))

    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    top_matches = [c[1] for c in scored_chunks[:top_k]]

    return {
        "status": "success",
        "source": "Local RAG Knowledge Engine",
        "query": query,
        "matches_count": len(top_matches),
        "results": top_matches
    }
