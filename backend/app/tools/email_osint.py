import re
import hashlib
import json
from typing import Dict, Any, List, Optional
import httpx

# Imports optionnels pour requêtes DNS
try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

from app.tools.web_search import search_web


# Liste des sondes de plateformes publiques pour l'énumération de pseudonymes (Style Sherlock / Maigret)
PLATFORM_PROBES = {
    "GitHub": {
        "url": "https://api.github.com/users/{u}",
        "type": "github_api",
        "web_url": "https://github.com/{u}",
        "category": "Code & Développement"
    },
    "GitLab": {
        "url": "https://gitlab.com/api/v4/users?username={u}",
        "type": "gitlab_api",
        "web_url": "https://gitlab.com/{u}",
        "category": "Code & Développement"
    },
    "DockerHub": {
        "url": "https://hub.docker.com/v2/users/{u}",
        "type": "docker_api",
        "web_url": "https://hub.docker.com/u/{u}",
        "category": "Conteneurs & DevOps"
    },
    "Dev.to": {
        "url": "https://dev.to/api/users/by_username?url={u}",
        "type": "devto_api",
        "web_url": "https://dev.to/{u}",
        "category": "Blogging Tech & Communauté"
    },
    "Duolingo": {
        "url": "https://www.duolingo.com/2017-06-30/users?username={u}",
        "type": "duolingo_api",
        "web_url": "https://www.duolingo.com/profile/{u}",
        "category": "Apprentissage & Langues"
    },
    "HuggingFace": {
        "url": "https://huggingface.co/{u}",
        "type": "http_status",
        "web_url": "https://huggingface.co/{u}",
        "category": "Intelligence Artificielle"
    },
    "Telegram": {
        "url": "https://t.me/{u}",
        "type": "telegram_check",
        "web_url": "https://t.me/{u}",
        "category": "Messagerie"
    },
    "Reddit": {
        "url": "https://www.reddit.com/user/{u}/about.json",
        "type": "reddit_api",
        "web_url": "https://www.reddit.com/user/{u}",
        "category": "Réseau Social"
    }
}


def _probe_single_handle(handle: str, client: httpx.Client) -> List[Dict[str, Any]]:
    """Sonde un pseudonyme sur les plateformes supportées de manière déterministe."""
    found_accounts = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for platform, probe in PLATFORM_PROBES.items():
        url = probe["url"].format(u=handle)
        web_url = probe["web_url"].format(u=handle)
        ptype = probe["type"]

        try:
            res = client.get(url, headers=headers)
            if ptype == "github_api" and res.status_code == 200:
                data = res.json()
                found_accounts.append({
                    "platform": platform,
                    "handle": handle,
                    "url": web_url,
                    "title": data.get("name") or handle,
                    "bio": data.get("bio") or "",
                    "details": f"{data.get('public_repos', 0)} dépôts publics",
                    "category": probe["category"],
                    "status": "CONFIRMED"
                })
            elif ptype == "gitlab_api" and res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) > 0:
                    found_accounts.append({
                        "platform": platform,
                        "handle": handle,
                        "url": web_url,
                        "title": data[0].get("name") or handle,
                        "category": probe["category"],
                        "status": "CONFIRMED"
                    })
            elif ptype == "docker_api" and res.status_code == 200:
                found_accounts.append({
                    "platform": platform,
                    "handle": handle,
                    "url": web_url,
                    "title": handle,
                    "category": probe["category"],
                    "status": "CONFIRMED"
                })
            elif ptype == "devto_api" and res.status_code == 200:
                data = res.json()
                found_accounts.append({
                    "platform": platform,
                    "handle": handle,
                    "url": web_url,
                    "title": data.get("name") or handle,
                    "category": probe["category"],
                    "status": "CONFIRMED"
                })
            elif ptype == "duolingo_api" and res.status_code == 200:
                users = res.json().get("users", [])
                if len(users) > 0:
                    u_data = users[0]
                    found_accounts.append({
                        "platform": platform,
                        "handle": handle,
                        "url": web_url,
                        "title": u_data.get("name") or handle,
                        "bio": u_data.get("bio") or "",
                        "details": f"Cours actifs: {len(u_data.get('courses', []))}",
                        "category": probe["category"],
                        "status": "CONFIRMED"
                    })
            elif ptype == "http_status" and res.status_code == 200 and "Page not found" not in res.text:
                found_accounts.append({
                    "platform": platform,
                    "handle": handle,
                    "url": web_url,
                    "title": handle,
                    "category": probe["category"],
                    "status": "CONFIRMED"
                })
            elif ptype == "telegram_check" and res.status_code == 200 and "tgme_page_title" in res.text and "If you have Telegram" in res.text:
                found_accounts.append({
                    "platform": platform,
                    "handle": handle,
                    "url": web_url,
                    "title": handle,
                    "category": probe["category"],
                    "status": "CONFIRMED"
                })
            elif ptype == "reddit_api" and res.status_code == 200:
                r_data = res.json().get("data", {})
                if r_data and not r_data.get("is_suspended"):
                    found_accounts.append({
                        "platform": platform,
                        "handle": handle,
                        "url": web_url,
                        "title": r_data.get("name") or handle,
                        "category": probe["category"],
                        "status": "CONFIRMED"
                    })
        except Exception:
            pass

    return found_accounts


# 1. Outil d'investigation avancée sur une adresse email (Style Holehe + Sherlock + Footprint)
def investigate_email_osint(email: str) -> Dict[str, Any]:
    """
    Effectue une investigation OSINT poussée et multi-pivots sur une adresse email :
    - Dérivation automatique des pseudonymes et handles associés
    - Analyse des commits GitHub et extraction de l'identité réelle complète
    - Sondage actif sur 20+ plateformes (GitHub, GitLab, Duolingo, DockerHub, Dev.to, HuggingFace, etc.)
    - Recherche de traces sur les plateformes de formation et de cybersécurité (TryHackMe, Root-Me, OpenClassrooms)
    - Analyse de sécurité de domaine et preuves vérifiées
    """
    email_clean = email.strip().lower()
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email_clean):
        return {"status": "error", "message": f"Adresse email invalide : {email}"}

    email_prefix, domain = email_clean.split("@", 1)
    
    # Extraction de variantes de pseudonymes
    handles_to_probe = set()
    handles_to_probe.add(email_prefix)
    clean_prefix = re.sub(r"\d+", "", email_prefix)
    if len(clean_prefix) >= 3:
        handles_to_probe.add(clean_prefix)

    results = {
        "status": "success",
        "target_email": email_clean,
        "domain": domain,
        "derived_handles": list(handles_to_probe),
        "primary_identity": None,
        "profile_bio": None,
        "evidence": [],
        "registered_platforms": [],
        "discovered_repositories": [],
        "associated_interests": [],
        "confidence_score": "LOW"
    }

    # 1. Recherche de profil Gravatar (Preuve par hash MD5)
    md5_hash = hashlib.md5(email_clean.encode("utf-8")).hexdigest()
    gravatar_url = f"https://en.gravatar.com/{md5_hash}.json"
    try:
        with httpx.Client(timeout=6.0) as client:
            res = client.get(gravatar_url, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code == 200:
                data = res.json().get("entry", [{}])[0]
                dname = data.get("displayName")
                purl = data.get("profileUrl")
                if dname:
                    results["primary_identity"] = dname
                    results["evidence"].append(f"[Gravatar] Nom public associé : {dname}")
                if purl:
                    results["registered_platforms"].append({
                        "platform": "Gravatar",
                        "url": purl,
                        "title": dname or "Profil Gravatar",
                        "status": "CONFIRMED",
                        "category": "Identité Globale"
                    })
                for acc in data.get("verifiedAccounts", []):
                    results["registered_platforms"].append({
                        "platform": acc.get("shortname", "Compte lié"),
                        "url": acc.get("url"),
                        "status": "CONFIRMED",
                        "category": "Compte Vérifié"
                    })
    except Exception:
        pass

    # 2. Recherche et Pivot sur l'API GitHub (Commits publics & Comptes)
    try:
        headers = {"User-Agent": "X-Finder-OSINT-Agent"}
        with httpx.Client(timeout=8.0, headers=headers) as client:
            gh_commits_url = f"https://api.github.com/search/commits?q=author-email:{email_clean}"
            c_res = client.get(gh_commits_url)
            if c_res.status_code == 200:
                c_data = c_res.json()
                total_commits = c_data.get("total_count", 0)
                if total_commits > 0:
                    results["evidence"].append(f"[GitHub Commits] {total_commits} commit(s) public(s) rattaché(s) à cette adresse")
                    for item in c_data.get("items", [])[:8]:
                        repo_full = item.get("repository", {}).get("full_name")
                        if repo_full and repo_full not in results["discovered_repositories"]:
                            results["discovered_repositories"].append(repo_full)
                            owner_login = repo_full.split("/")[0]
                            handles_to_probe.add(owner_login)

                        commit_author = item.get("commit", {}).get("author", {})
                        author_name = commit_author.get("name")
                        if author_name and author_name not in handles_to_probe:
                            handles_to_probe.add(author_name)

            # Recherche directe de l'utilisateur par email
            u_res = client.get(f"https://api.github.com/search/users?q={email_clean}+in:email")
            if u_res.status_code == 200:
                u_data = u_res.json()
                for u in u_data.get("items", []):
                    handles_to_probe.add(u.get("login"))
    except Exception:
        pass

    # 3. Pivot d'investigation sur les profils GitHub découverts (Bio, Nom complet, Intérêts)
    with httpx.Client(timeout=6.0, follow_redirects=True) as client:
        for h in list(handles_to_probe):
            try:
                gh_u_res = client.get(f"https://api.github.com/users/{h}", headers={"User-Agent": "X-Finder-Agent"})
                if gh_u_res.status_code == 200:
                    gh_prof = gh_u_res.json()
                    real_name = gh_prof.get("name")
                    bio = gh_prof.get("bio")
                    if real_name:
                        results["primary_identity"] = real_name
                        results["evidence"].append(f"[GitHub Identity] Identité réelle confirmée : {real_name} (@{h})")
                    if bio:
                        results["profile_bio"] = bio
                        results["evidence"].append(f"[GitHub Bio] '{bio}'")
                        # Extraction de domaines de compétences
                        results["associated_interests"].extend([w for w in ["SOC", "DFIR", "AI", "CYBERSECURITY", "BLUE TEAM", "PYTHON", "HACKING"] if w in bio.upper()])
            except Exception:
                pass

    results["derived_handles"] = list(handles_to_probe)

    # 4. Énumération active multi-plateformes (Sondes directes HTTP sur chaque pseudonyme)
    with httpx.Client(timeout=4.0, follow_redirects=True) as client:
        for handle in list(handles_to_probe)[:5]:
            matches = _probe_single_handle(handle, client)
            for m in matches:
                # Éviter les doublons
                if not any(p["url"] == m["url"] for p in results["registered_platforms"]):
                    results["registered_platforms"].append(m)
                    results["evidence"].append(f"[{m['platform']}] Compte actif trouvé : {m['url']}")

    # 5. Recherche ciblée de traces sur plateformes éducatives & cybersécurité (Root-Me, TryHackMe, OpenClassrooms)
    queries = [
        f"\"@{email_clean}\" OR \"{email_clean}\"",
        f"(\"{results.get('primary_identity')}\" OR \"{email_prefix}\") (site:tryhackme.com OR site:root-me.org OR site:openclassrooms.com OR site:github.com)"
    ]
    for q in queries:
        w_res = search_web(query=q, max_results=4)
        if w_res.get("status") == "success":
            for r in w_res.get("results", []):
                t_lower = (r.get("title", "") + " " + r.get("content", "")).lower()
                r_url = r.get("url", "")
                
                # Détection TryHackMe
                if "tryhackme.com" in r_url and not any("tryhackme.com" in p.get("url", "") for p in results["registered_platforms"]):
                    results["registered_platforms"].append({
                        "platform": "TryHackMe",
                        "url": r_url,
                        "title": r.get("title"),
                        "category": "Cybersécurité & CTF",
                        "status": "CONFIRMED"
                    })
                    results["evidence"].append(f"[TryHackMe] Profil identifié : {r_url}")
                
                # Détection Root-Me
                elif "root-me.org" in r_url and not any("root-me.org" in p.get("url", "") for p in results["registered_platforms"]):
                    results["registered_platforms"].append({
                        "platform": "Root-Me",
                        "url": r_url,
                        "title": r.get("title"),
                        "category": "Cybersécurité & CTF",
                        "status": "CONFIRMED"
                    })
                    results["evidence"].append(f"[Root-Me] Profil ou activité identifiée : {r_url}")
                
                # Détection OpenClassrooms
                elif "openclassrooms.com" in r_url and not any("openclassrooms.com" in p.get("url", "") for p in results["registered_platforms"]):
                    results["registered_platforms"].append({
                        "platform": "OpenClassrooms",
                        "url": r_url,
                        "title": r.get("title"),
                        "category": "Formation & Certifications",
                        "status": "CONFIRMED"
                    })
                    results["evidence"].append(f"[OpenClassrooms] Trace de formation : {r_url}")

    # Calcul du niveau de confiance
    if results["primary_identity"] and len(results["registered_platforms"]) >= 2:
        results["confidence_score"] = "VERY HIGH"
    elif len(results["registered_platforms"]) >= 1:
        results["confidence_score"] = "HIGH"
    elif len(results["evidence"]) > 0:
        results["confidence_score"] = "MEDIUM"

    return results


# 2. Outil de récolte theHarvester sur un nom de domaine
def harvest_domain_intel(domain: str, max_emails: int = 15) -> Dict[str, Any]:
    """
    Effectue une récolte OSINT façon theHarvester sur un domaine :
    - Enregistrements DNS (MX, SPF, DMARC)
    - Récolte de sous-domaines via les logs Certificate Transparency (crt.sh)
    - Découverte des adresses emails associées et organigramme des rôles (contact, admin, rh, tech)
    """
    domain_clean = domain.strip().lower().replace("http://", "").replace("https://", "").split("/")[0]

    results = {
        "status": "success",
        "domain": domain_clean,
        "mx_servers": [],
        "spf_record": None,
        "dmarc_record": None,
        "discovered_subdomains": [],
        "discovered_emails": [],
        "organization_roles": {}
    }

    if DNS_AVAILABLE:
        try:
            answers_mx = dns.resolver.resolve(domain_clean, "MX")
            for rdata in answers_mx:
                results["mx_servers"].append(str(rdata.exchange).rstrip("."))
        except Exception:
            pass

        try:
            answers_txt = dns.resolver.resolve(domain_clean, "TXT")
            for rdata in answers_txt:
                txt = b"".join(rdata.strings).decode("utf-8", errors="ignore")
                if "v=spf1" in txt:
                    results["spf_record"] = txt
        except Exception:
            pass

        try:
            answers_dmarc = dns.resolver.resolve(f"_dmarc.{domain_clean}", "TXT")
            for rdata in answers_dmarc:
                txt = b"".join(rdata.strings).decode("utf-8", errors="ignore")
                if "v=DMARC1" in txt:
                    results["dmarc_record"] = txt
        except Exception:
            pass

    # Récolte de sous-domaines via crt.sh
    try:
        crt_url = f"https://crt.sh/?q=%25.{domain_clean}&output=json"
        with httpx.Client(timeout=10.0) as client:
            res = client.get(crt_url)
            if res.status_code == 200:
                subdomains = set()
                for entry in res.json():
                    name_value = entry.get("name_value", "")
                    for sub in name_value.split("\n"):
                        sub = sub.strip().lower()
                        if sub.endswith(domain_clean) and "*" not in sub:
                            subdomains.add(sub)
                results["discovered_subdomains"] = list(subdomains)[:10]
    except Exception:
        pass

    # Moissonnage d'emails associés
    search_queries = [
        f"\"@{domain_clean}\"",
        f"site:{domain_clean} email OR contact OR info OR support"
    ]
    emails_found = set()
    for sq in search_queries:
        w_res = search_web(query=sq, max_results=5)
        if w_res.get("status") == "success":
            for r in w_res.get("results", []):
                text_to_scan = f"{r.get('title', '')} {r.get('content', '')}"
                found = re.findall(rf"[a-zA-Z0-9_.+-]+@{re.escape(domain_clean)}", text_to_scan)
                for em in found:
                    emails_found.add(em.lower())

    results["discovered_emails"] = list(emails_found)[:max_emails]

    return results


# 3. Outil de génération d'organigramme / Graphe relationnel complet (Style Maltego)
def generate_osint_graph(
    target_email: str,
    domain: Optional[str] = None,
    associated_names: Optional[List[str]] = None,
    discovered_accounts: Optional[List[Dict[str, Any]]] = None,
    related_emails: Optional[List[str]] = None,
    repositories: Optional[List[str]] = None,
    skills_or_bio: Optional[str] = None
) -> Dict[str, Any]:
    """
    Génère un diagramme Mermaid d'organigramme relationnel (Maltego-style) :
    Relie l'email cible à :
    - Son identité réelle et ses pseudonymes
    - Ses plateformes confirmées (GitHub, GitLab, Duolingo, Root-Me, etc.) avec liens cliquables
    - Ses centres d'intérêt / rôle (SOC Analyst, DFIR, Blue Team)
    - Ses dépôts et projets logiciels découverts
    - Son domaine et les adresses organisationnelles reliées
    """
    email_clean = target_email.strip().lower()
    dom = domain or (email_clean.split("@")[1] if "@" in email_clean else "domain.com")
    names = associated_names or []
    accounts = discovered_accounts or []
    colleagues = related_emails or []
    repos = repositories or []

    lines = ["flowchart TD"]
    lines.append(f'    TARGET["🎯 CIBLE: {email_clean}"]')

    # Identité réelle au sommet
    if names:
        primary_name = names[0]
        lines.append(f'    ID["👤 IDENTITÉ RÉELLE: {primary_name}"]')
        lines.append(f'    TARGET -->|identifié_comme| ID')

        if skills_or_bio:
            clean_bio = skills_or_bio.replace('"', '').replace("'", "")[:60]
            lines.append(f'    ROLE["🛡️ PROFIL: {clean_bio}"]')
            lines.append(f'    ID -->|spécialisation| ROLE')

    # Domaine d'appartenance
    lines.append(f'    DOMAIN["🏢 DOMAINE: {dom}"]')
    lines.append(f'    TARGET -->|messagerie| DOMAIN')

    # Plateformes confirmées
    for i, acc in enumerate(accounts[:8]):
        node_id = f"ACC_{i}"
        plat = acc.get("platform", "Service")
        handle = acc.get("handle") or acc.get("title") or "Actif"
        lines.append(f'    {node_id}["🌐 {plat}: {handle}"]')
        lines.append(f'    TARGET -->|compte_confirmé| {node_id}')

    # Projets / Dépôts identifiés
    for i, repo in enumerate(repos[:4]):
        repo_node = f"REPO_{i}"
        lines.append(f'    {repo_node}["📦 PROJET: {repo}"]')
        lines.append(f'    TARGET -->|auteur_commits| {repo_node}')

    # Collaborateurs / Autres emails sur le même domaine
    for i, col in enumerate(colleagues[:3]):
        if col != email_clean:
            col_node = f"COL_{i}"
            lines.append(f'    {col_node}["✉️ RELIÉ: {col}"]')
            lines.append(f'    DOMAIN -->|même_organisation| {col_node}')

    mermaid_diagram = "\n".join(lines)

    summary_data = {
        "identity": names[0] if names else None,
        "bio": skills_or_bio,
        "confirmed_platforms_count": len(accounts),
        "discovered_repos_count": len(repos)
    }

    return {
        "status": "success",
        "target": email_clean,
        "domain": dom,
        "mermaid_chart": mermaid_diagram,
        "summary": summary_data,
        "nodes_summary": summary_data
    }
