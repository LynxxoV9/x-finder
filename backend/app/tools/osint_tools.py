import json
import httpx
from typing import Dict, Any, List, Optional
from app.tools.web_search import search_web

# Outils spécialisés OSINT & Cyber Threat Intelligence (CTI) pour X-Finder

def recon_social_profile(platform: str, identifier: str) -> Dict[str, Any]:
    """
    Effectue une reconnaissance OSINT sur un profil public (LinkedIn, YouTube, GitHub, ou pseudonyme).
    Extrait les compétences, activités récentes et centres d'intérêt pour cibler les opportunités.
    """
    platform_clean = platform.lower().strip()
    results = {
        "status": "success",
        "target": identifier,
        "platform": platform,
        "intel_summary": "",
        "extracted_skills": [],
        "sources": []
    }

    # Recherche OSINT ciblée via le moteur Web
    search_query = f"site:{platform_clean}.com \"{identifier}\"" if platform_clean in ["linkedin", "youtube", "github"] else f"\"{identifier}\" cybersecurity OSINT CTF"
    web_res = search_web(query=search_query, max_results=4)

    snippets = []
    if web_res.get("status") == "success":
        for r in web_res.get("results", []):
            snippets.append(f"• [{r.get('title')}]({r.get('url')}): {r.get('content')}")
            results["sources"].append(r.get("url"))

    results["intel_summary"] = "\n".join(snippets) if snippets else f"Profil identifié pour '{identifier}'. Analyse des traces publiques en cours."
    
    # Détection de mots-clés de compétences
    known_tags = ["python", "osint", "ctf", "reverse", "web", "soc", "pentest", "forensic", "ia", "fastapi", "react"]
    found_tags = [tag for tag in known_tags if tag in results["intel_summary"].lower()]
    results["extracted_skills"] = found_tags or ["Cybersécurité", "Intelligence Artificielle", "Développement"]

    return results


def cti_threat_lookup(indicator_or_cve: str) -> Dict[str, Any]:
    """
    Interroge les flux de Threat Intelligence (CTI) pour une CVE, un acteur de menace (APT), un malware ou un IOC.
    Fournit le score de gravité, les vecteurs d'attaque et les mesures de remédiation.
    """
    search_query = f"{indicator_or_cve} vulnerability CVE threat intelligence exploit POC advisory"
    web_res = search_web(query=search_query, max_results=5, include_news=True)

    findings = []
    if web_res.get("status") == "success":
        for r in web_res.get("results", []):
            findings.append({
                "source": r.get("title"),
                "url": r.get("url"),
                "intel": r.get("content")
            })

    return {
        "status": "success",
        "indicator": indicator_or_cve,
        "findings_count": len(findings),
        "intelligence": findings,
        "sources": [f["url"] for f in findings],
        "advisory": f"Rapport CTI consolidé pour {indicator_or_cve}. Vérifier les bulletins CERT et appliquer les correctifs recommandés."
    }


def hunt_opportunities(opportunity_type: str = "stage", domain: str = "cybersécurité", location: str = "Togo, France, Remote") -> Dict[str, Any]:
    """
    Chasse les opportunités actives selon le profil : stages, offres d'emploi, hackathons et compétitions CTF.
    Idéal pour alimenter une mission et générer un rapport synthétique par email.
    """
    search_query = f"{opportunity_type} {domain} {location} 2026 hackathon CTF recrutement inscription"
    web_res = search_web(query=search_query, max_results=6, include_news=True)

    items = []
    if web_res.get("status") == "success":
        for r in web_res.get("results", []):
            items.append({
                "title": r.get("title"),
                "url": r.get("url"),
                "details": r.get("content")
            })

    return {
        "status": "success",
        "query": f"Chasse : {opportunity_type} en {domain} ({location})",
        "count": len(items),
        "opportunities": items,
        "sources": [it["url"] for it in items],
        "recommendation": "Sélectionnez les offres les plus pertinentes pour préparer une candidature ou planifier un rappel dans l'agenda."
    }
