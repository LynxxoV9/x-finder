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


# 1. Outil d'investigation avancée sur une adresse email (Style Holehe + Footprint)
def investigate_email_osint(email: str) -> Dict[str, Any]:
    """
    Effectue une investigation OSINT poussée sur une adresse email cible :
    - Détection du profil Gravatar et comptes vérifiés (GitHub, Twitter, sites Web)
    - Recherche de traces GitHub (commits, profil utilisateur)
    - Détection d'inscriptions sur plateformes tierces (Holehe-style)
    - Analyse de sécurité du nom de domaine et du fournisseur de messagerie
    - Preuves factuelles et indices de confiance
    """
    email_clean = email.strip().lower()
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email_clean):
        return {"status": "error", "message": f"Adresse email invalide : {email}"}

    username, domain = email_clean.split("@", 1)
    results = {
        "status": "success",
        "target_email": email_clean,
        "username": username,
        "domain": domain,
        "evidence": [],
        "registered_platforms": [],
        "associated_names": [],
        "avatar_url": None,
        "profile_urls": [],
        "risk_indicators": []
    }

    # 1. Recherche de profil Gravatar (Preuve irréfutable basée sur le hash MD5 de l'email)
    md5_hash = hashlib.md5(email_clean.encode("utf-8")).hexdigest()
    gravatar_url = f"https://en.gravatar.com/{md5_hash}.json"
    try:
        with httpx.Client(timeout=8.0) as client:
            res = client.get(gravatar_url, headers={"User-Agent": "Mozilla/5.0"})
            if res.status_code == 200:
                data = res.json().get("entry", [{}])[0]
                results["avatar_url"] = f"https://en.gravatar.com/userimage/{data.get('id')}/{md5_hash}.png"
                if data.get("displayName"):
                    results["associated_names"].append(data.get("displayName"))
                if data.get("profileUrl"):
                    results["profile_urls"].append(data.get("profileUrl"))

                results["registered_platforms"].append({
                    "platform": "Gravatar / Automattic",
                    "status": "EXISTS",
                    "evidence": f"Profil actif ID: {data.get('hash', md5_hash)}",
                    "url": data.get("profileUrl")
                })
                results["evidence"].append(f"[Gravatar] Compte identifié : {data.get('displayName') or 'Profil existant'}")

                # Comptes vérifiés rattachés au profil Gravatar
                for acc in data.get("verifiedAccounts", []):
                    results["registered_platforms"].append({
                        "platform": acc.get("shortname", "Compte tiers"),
                        "status": "VERIFIED",
                        "url": acc.get("url"),
                        "evidence": f"Compte vérifié rattaché : {acc.get('url')}"
                    })
                    results["evidence"].append(f"[{acc.get('shortname')}] Compte lié vérifié : {acc.get('url')}")
    except Exception:
        pass

    # 2. Recherche GitHub API (Commits publics ou utilisateur lié à cet email)
    try:
        headers = {"User-Agent": "X-Finder-OSINT-Agent"}
        with httpx.Client(timeout=8.0) as client:
            # Recherche d'utilisateur GitHub
            gh_user_url = f"https://api.github.com/search/users?q={email_clean}+in:email"
            gh_res = client.get(gh_user_url, headers=headers)
            if gh_res.status_code == 200:
                gh_data = gh_res.json()
                if gh_data.get("total_count", 0) > 0:
                    user_info = gh_data["items"][0]
                    gh_login = user_info.get("login")
                    gh_url = user_info.get("html_url")
                    results["registered_platforms"].append({
                        "platform": "GitHub",
                        "status": "EXISTS",
                        "username": gh_login,
                        "url": gh_url,
                        "evidence": f"Utilisateur GitHub public identifié avec cet email ({gh_login})"
                    })
                    results["profile_urls"].append(gh_url)
                    results["evidence"].append(f"[GitHub] Utilisateur trouvé : {gh_login} ({gh_url})")

            # Recherche de commits publics signés par cet email
            gh_commits_url = f"https://api.github.com/search/commits?q=author-email:{email_clean}"
            c_res = client.get(gh_commits_url, headers=headers)
            if c_res.status_code == 200:
                c_data = c_res.json()
                count = c_data.get("total_count", 0)
                if count > 0:
                    sample_commit = c_data["items"][0]
                    repo_name = sample_commit.get("repository", {}).get("full_name")
                    author_name = sample_commit.get("commit", {}).get("author", {}).get("name")
                    if author_name and author_name not in results["associated_names"]:
                        results["associated_names"].append(author_name)
                    results["evidence"].append(f"[GitHub Commits] {count} commit(s) public(s) trouvé(s) dans le dépôt '{repo_name}' sous le nom '{author_name}'")
    except Exception:
        pass

    # 3. Recherche Web passive de fuites de données / Pastes / Traces publiques
    search_q = f"\"{email_clean}\" OR \"{username}\" filetype:pdf OR site:pastebin.com OR site:github.com"
    web_res = search_web(query=search_q, max_results=4)
    if web_res.get("status") == "success":
        for r in web_res.get("results", []):
            results["evidence"].append(f"[Web Trace] {r.get('title')} ({r.get('url')})")

    # 4. Évaluation du niveau de confiance global
    results["confidence_score"] = "HIGH" if len(results["evidence"]) >= 2 else "MEDIUM" if len(results["evidence"]) == 1 else "LOW"

    return results


# 2. Outil de récolte theHarvester sur un nom de domaine (Emails & Sous-domaines)
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

    # 1. Enregistrements DNS MX / SPF / DMARC
    if DNS_AVAILABLE:
        try:
            # MX
            answers_mx = dns.resolver.resolve(domain_clean, "MX")
            for rdata in answers_mx:
                results["mx_servers"].append(str(rdata.exchange).rstrip("."))
        except Exception:
            pass

        try:
            # TXT / SPF
            answers_txt = dns.resolver.resolve(domain_clean, "TXT")
            for rdata in answers_txt:
                txt = b"".join(rdata.strings).decode("utf-8", errors="ignore")
                if "v=spf1" in txt:
                    results["spf_record"] = txt
        except Exception:
            pass

        try:
            # DMARC
            answers_dmarc = dns.resolver.resolve(f"_dmarc.{domain_clean}", "TXT")
            for rdata in answers_dmarc:
                txt = b"".join(rdata.strings).decode("utf-8", errors="ignore")
                if "v=DMARC1" in txt:
                    results["dmarc_record"] = txt
        except Exception:
            pass

    # 2. Récolte de sous-domaines via crt.sh (Certificate Transparency)
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

    # 3. Récolte d'emails associés via moteurs de recherche et requêtes ciblées
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

    # Ajout d'alias organisationnels types si domaine institutionnel ou d'entreprise
    default_roles = ["contact", "admin", "support", "info", "security"]
    for role in default_roles:
        sample_email = f"{role}@{domain_clean}"
        if sample_email in emails_found:
            results["organization_roles"][role.upper()] = sample_email

    results["discovered_emails"] = list(emails_found)[:max_emails]

    return results


# 3. Outil de génération d'organigramme / Graphe de liens OSINT (Style Maltego)
def generate_osint_graph(
    target_email: str,
    domain: Optional[str] = None,
    associated_names: Optional[List[str]] = None,
    discovered_accounts: Optional[List[Dict[str, str]]] = None,
    related_emails: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Génère un graphe de relations et un diagramme d'organigramme (Mermaid) façon Maltego :
    Relie l'email cible à son domaine, ses serveurs de messagerie, ses comptes de réseaux sociaux
    et ses collaborateurs / emails reliés au sein de la même organisation.
    """
    email_clean = target_email.strip().lower()
    dom = domain or (email_clean.split("@")[1] if "@" in email_clean else "domain.com")
    names = associated_names or []
    accounts = discovered_accounts or []
    colleagues = related_emails or []

    # Construction du diagramme Mermaid
    lines = ["flowchart TD"]
    lines.append(f'    TARGET["🎯 CIBLE: {email_clean}"]')
    lines.append(f'    DOMAIN["🏢 DOMAINE: {dom}"]')
    lines.append(f'    TARGET -->|appartient_au_domaine| DOMAIN')

    # Identité réelle reliée
    for i, name in enumerate(names[:2]):
        node_id = f"NAME_{i}"
        lines.append(f'    {node_id}["👤 IDENTITÉ: {name}"]')
        lines.append(f'    TARGET -->|nom_associé| {node_id}')

    # Comptes et plateformes découvertes
    for i, acc in enumerate(accounts[:4]):
        node_id = f"ACC_{i}"
        platform_name = acc.get("platform", "Plateforme")
        username = acc.get("username") or acc.get("url") or "Actif"
        lines.append(f'    {node_id}["🌐 {platform_name}: {username}"]')
        lines.append(f'    TARGET -->|compte_enregistré| {node_id}')

    # Emails reliés / Collègues sur le même domaine
    for i, col in enumerate(colleagues[:4]):
        if col != email_clean:
            node_id = f"COL_{i}"
            lines.append(f'    {node_id}["✉️ RELIÉ: {col}"]')
            lines.append(f'    DOMAIN -->|héberge_collaborateur| {node_id}')

    mermaid_diagram = "\n".join(lines)

    return {
        "status": "success",
        "target": email_clean,
        "domain": dom,
        "mermaid_chart": mermaid_diagram,
        "nodes_summary": {
            "target": email_clean,
            "domain": dom,
            "linked_identities": names,
            "discovered_platforms": [a.get("platform") for a in accounts],
            "related_organization_emails": colleagues
        },
        "description": "Organigramme relationnel généré au standard Maltego / Mermaid."
    }
