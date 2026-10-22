import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from app.tools.web_search import search_web


def _unique_sources(items: List[Dict[str, Any]]) -> List[str]:
    seen = set()
    out = []
    for it in items:
        url = (it.get("url") or "").strip()
        if url and url not in seen:
            seen.add(url)
            out.append(url)
    return out


def _domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def recon_social_profile(platform: str, identifier: str) -> Dict[str, Any]:
    """
    Reconnaissance OSINT sur un profil / identifiant public.
    Ne confirme jamais un profil sans preuve (URL + snippet réel).
    """
    platform_clean = (platform or "").lower().strip()
    ident = (identifier or "").strip()
    if not ident:
        return {"status": "error", "message": "Identifiant manquant.", "confirmed": False}

    platform_aliases = {
        "x": "twitter",
        "twitter/x": "twitter",
        "yt": "youtube",
        "gh": "github",
        "li": "linkedin",
        "ig": "instagram",
        "fb": "facebook",
    }
    platform_clean = platform_aliases.get(platform_clean, platform_clean)

    site_map = {
        "linkedin": "linkedin.com",
        "youtube": "youtube.com",
        "github": "github.com",
        "twitter": "twitter.com",
        "instagram": "instagram.com",
        "facebook": "facebook.com",
        "tiktok": "tiktok.com",
        "reddit": "reddit.com",
        "medium": "medium.com",
        "telegram": "t.me",
    }

    queries: List[str] = []
    if platform_clean in site_map:
        site = site_map[platform_clean]
        queries.append(f'site:{site} "{ident}"')
        queries.append(f'"{ident}" {site}')
    elif platform_clean in ("auto", "any", "all", ""):
        queries.append(f'"{ident}"')
        queries.append(
            f'"{ident}" (site:linkedin.com OR site:facebook.com OR site:instagram.com '
            f"OR site:twitter.com OR site:x.com OR site:github.com OR site:youtube.com)"
        )
    else:
        queries.append(f'"{ident}" {platform_clean}')
        queries.append(f'"{ident}"')

    findings: List[Dict[str, Any]] = []
    for q in queries:
        web_res = search_web(query=q, max_results=5)
        if web_res.get("status") != "success":
            continue
        for r in web_res.get("results", []):
            url = r.get("url") or ""
            title = r.get("title") or ""
            content = r.get("content") or ""
            # Preuve minimale : l'identifiant apparaît dans titre, URL ou snippet
            blob = f"{title} {url} {content}".lower()
            if ident.lower() not in blob and ident.replace(" ", "").lower() not in blob.replace(" ", ""):
                continue
            findings.append({
                "title": title,
                "url": url,
                "snippet": content,
                "domain": _domain_of(url),
            })

    # Dédupliquer par URL
    dedup: List[Dict[str, Any]] = []
    seen_urls = set()
    for f in findings:
        if f["url"] in seen_urls:
            continue
        seen_urls.add(f["url"])
        dedup.append(f)

    if not dedup:
        return {
            "status": "no_results",
            "confirmed": False,
            "target": ident,
            "platform": platform or "auto",
            "message": (
                f"Aucune trace publique vérifiable trouvée pour '{ident}' "
                f"sur '{platform or 'auto'}'. Ne pas inventer de profil."
            ),
            "findings": [],
            "extracted_skills": [],
            "sources": [],
        }

    # Compétences uniquement si présentes dans les snippets (pas de défaut inventé)
    known_tags = [
        "python", "java", "javascript", "osint", "ctf", "soc", "pentest", "forensic",
        "marketing", "finance", "journalisme", "médecine", "droit", "éducation",
        "design", "photographie", "musique", "sport", "agriculture", "commerce",
    ]
    corpus = " ".join(f"{x['title']} {x['snippet']}" for x in dedup).lower()
    found_tags = [tag for tag in known_tags if tag in corpus]

    return {
        "status": "success",
        "confirmed": True,
        "target": ident,
        "platform": platform or "auto",
        "findings_count": len(dedup),
        "findings": dedup[:8],
        "intel_summary": "\n".join(
            f"• [{f['title']}]({f['url']}): {f['snippet']}" for f in dedup[:6]
        ),
        "extracted_skills": found_tags,
        "sources": _unique_sources(dedup),
    }


def investigate_person_osint(full_name: str, location_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    OSINT sur un nom complet (civil / public), sans biais cybersécurité.
    Agrège uniquement des résultats web réels avec sources.
    """
    name = re.sub(r"\s+", " ", (full_name or "").strip())
    if len(name) < 3:
        return {"status": "error", "message": "Nom complet trop court ou manquant."}

    location = (location_hint or "").strip()
    queries = [
        f'"{name}"',
        (
            f'"{name}" (site:linkedin.com OR site:facebook.com OR site:instagram.com '
            f"OR site:twitter.com OR site:x.com OR site:wikipedia.org OR site:youtube.com)"
        ),
        f'"{name}" (profil OR biography OR biographie OR CV OR "about")',
    ]
    if location:
        queries.insert(1, f'"{name}" {location}')

    findings: List[Dict[str, Any]] = []
    emails_found: List[str] = []
    handles_found: List[str] = []
    email_re = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    handle_re = re.compile(r"(?:@|github\.com/|linkedin\.com/in/|twitter\.com/|x\.com/|instagram\.com/)([A-Za-z0-9_.-]{3,})")

    for q in queries:
        web_res = search_web(query=q, max_results=6)
        if web_res.get("status") != "success":
            continue
        for r in web_res.get("results", []):
            title = r.get("title") or ""
            url = r.get("url") or ""
            content = r.get("content") or ""
            blob = f"{title} {url} {content}"
            # Le nom (au moins un token significatif) doit apparaître
            tokens = [t for t in re.split(r"\s+", name) if len(t) >= 3]
            if tokens and not any(t.lower() in blob.lower() for t in tokens):
                continue
            findings.append({
                "title": title,
                "url": url,
                "snippet": content,
                "domain": _domain_of(url),
            })
            for em in email_re.findall(blob):
                if em.lower() not in emails_found:
                    emails_found.append(em.lower())
            for h in handle_re.findall(blob):
                if h.lower() not in [x.lower() for x in handles_found]:
                    handles_found.append(h)

    dedup: List[Dict[str, Any]] = []
    seen = set()
    for f in findings:
        if f["url"] in seen:
            continue
        seen.add(f["url"])
        dedup.append(f)

    if not dedup:
        return {
            "status": "no_results",
            "target_name": name,
            "location_hint": location or None,
            "message": (
                f"Aucune trace publique vérifiable pour « {name} ». "
                "Ne pas inventer de biographie, métier ou profil."
            ),
            "findings": [],
            "possible_emails": [],
            "possible_handles": [],
            "sources": [],
        }

    return {
        "status": "success",
        "target_name": name,
        "location_hint": location or None,
        "findings_count": len(dedup),
        "findings": dedup[:12],
        "possible_emails": emails_found[:8],
        "possible_handles": handles_found[:10],
        "sources": _unique_sources(dedup),
        "note": (
            "Résultats basés uniquement sur des sources web récupérées. "
            "Vérifier manuellement les homonymes avant toute conclusion."
        ),
    }


def cti_threat_lookup(indicator_or_cve: str) -> Dict[str, Any]:
    """Veille CTI sur CVE / menace / IOC — uniquement à partir de sources web réelles."""
    indicator = (indicator_or_cve or "").strip()
    if not indicator:
        return {"status": "error", "message": "Indicateur CTI manquant."}

    search_query = f"{indicator} vulnerability CVE threat intelligence advisory"
    web_res = search_web(query=search_query, max_results=5, include_news=True)

    findings = []
    if web_res.get("status") == "success":
        for r in web_res.get("results", []):
            findings.append({
                "source": r.get("title"),
                "url": r.get("url"),
                "intel": r.get("content"),
            })

    if not findings:
        return {
            "status": "no_results",
            "indicator": indicator,
            "findings_count": 0,
            "intelligence": [],
            "sources": [],
            "message": f"Aucune source CTI récupérable pour {indicator}.",
        }

    return {
        "status": "success",
        "indicator": indicator,
        "findings_count": len(findings),
        "intelligence": findings,
        "sources": [f["url"] for f in findings],
        "advisory": (
            f"{len(findings)} source(s) récupérée(s) pour {indicator}. "
            "Se baser uniquement sur ces liens ; ne pas inventer de score CVSS."
        ),
    }


def hunt_opportunities(
    opportunity_type: str = "stage",
    domain: str = "cybersécurité",
    location: str = "Togo, France, Remote",
) -> Dict[str, Any]:
    """Chasse d'opportunités (stages, emplois, hackathons, CTF) via recherche web réelle."""
    search_query = f"{opportunity_type} {domain} {location} 2026 recrutement inscription"
    web_res = search_web(query=search_query, max_results=6, include_news=True)

    items = []
    if web_res.get("status") == "success":
        for r in web_res.get("results", []):
            items.append({
                "title": r.get("title"),
                "url": r.get("url"),
                "details": r.get("content"),
            })

    if not items:
        return {
            "status": "no_results",
            "query": f"Chasse : {opportunity_type} en {domain} ({location})",
            "count": 0,
            "opportunities": [],
            "sources": [],
            "message": "Aucune opportunité récupérable pour cette requête.",
        }

    return {
        "status": "success",
        "query": f"Chasse : {opportunity_type} en {domain} ({location})",
        "count": len(items),
        "opportunities": items,
        "sources": [it["url"] for it in items],
    }
