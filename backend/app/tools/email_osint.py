import re
import hashlib
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

from app.tools.web_search import search_web


# Sondes publiques multi-domaines (tech + grand public) — style Sherlock/Maigret
PLATFORM_PROBES = {
    "GitHub": {
        "url": "https://api.github.com/users/{u}",
        "type": "github_api",
        "web_url": "https://github.com/{u}",
        "category": "Code",
    },
    "GitLab": {
        "url": "https://gitlab.com/api/v4/users?username={u}",
        "type": "gitlab_api",
        "web_url": "https://gitlab.com/{u}",
        "category": "Code",
    },
    "DockerHub": {
        "url": "https://hub.docker.com/v2/users/{u}",
        "type": "docker_api",
        "web_url": "https://hub.docker.com/u/{u}",
        "category": "DevOps",
    },
    "Dev.to": {
        "url": "https://dev.to/api/users/by_username?url={u}",
        "type": "devto_api",
        "web_url": "https://dev.to/{u}",
        "category": "Blogging",
    },
    "Duolingo": {
        "url": "https://www.duolingo.com/2017-06-30/users?username={u}",
        "type": "duolingo_api",
        "web_url": "https://www.duolingo.com/profile/{u}",
        "category": "Langues",
    },
    "HuggingFace": {
        "url": "https://huggingface.co/{u}",
        "type": "http_status",
        "web_url": "https://huggingface.co/{u}",
        "category": "IA",
    },
    "Reddit": {
        "url": "https://www.reddit.com/user/{u}/about.json",
        "type": "reddit_api",
        "web_url": "https://www.reddit.com/user/{u}",
        "category": "Social",
    },
    "Telegram": {
        "url": "https://t.me/{u}",
        "type": "telegram_check",
        "web_url": "https://t.me/{u}",
        "category": "Messagerie",
    },
    "Keybase": {
        "url": "https://keybase.io/{u}",
        "type": "http_status",
        "web_url": "https://keybase.io/{u}",
        "category": "Identité",
    },
    "About.me": {
        "url": "https://about.me/{u}",
        "type": "http_status",
        "web_url": "https://about.me/{u}",
        "category": "Profil public",
    },
    "Medium": {
        "url": "https://medium.com/@{u}",
        "type": "http_status",
        "web_url": "https://medium.com/@{u}",
        "category": "Écriture",
    },
    "Pinterest": {
        "url": "https://www.pinterest.com/{u}/",
        "type": "http_status",
        "web_url": "https://www.pinterest.com/{u}/",
        "category": "Social",
    },
    "Twitch": {
        "url": "https://www.twitch.tv/{u}",
        "type": "http_status",
        "web_url": "https://www.twitch.tv/{u}",
        "category": "Streaming",
    },
    "Steam": {
        "url": "https://steamcommunity.com/id/{u}",
        "type": "http_status",
        "web_url": "https://steamcommunity.com/id/{u}",
        "category": "Jeux",
    },
    "SoundCloud": {
        "url": "https://soundcloud.com/{u}",
        "type": "http_status",
        "web_url": "https://soundcloud.com/{u}",
        "category": "Musique",
    },
    "Flickr": {
        "url": "https://www.flickr.com/people/{u}/",
        "type": "http_status",
        "web_url": "https://www.flickr.com/people/{u}/",
        "category": "Photo",
    },
    "HackerNews": {
        "url": "https://hacker-news.firebaseio.com/v0/user/{u}.json",
        "type": "hn_api",
        "web_url": "https://news.ycombinator.com/user?id={u}",
        "category": "Communauté",
    },
}


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _probe_single_handle(handle: str, client: httpx.Client) -> List[Dict[str, Any]]:
    """Sonde un pseudonyme sur les plateformes supportées. Uniquement des confirmations HTTP/API réelles."""
    found_accounts: List[Dict[str, Any]] = []
    handle = handle.strip()
    if not handle or len(handle) < 2:
        return found_accounts

    for platform, probe in PLATFORM_PROBES.items():
        url = probe["url"].format(u=handle)
        web_url = probe["web_url"].format(u=handle)
        ptype = probe["type"]
        try:
            res = client.get(url, headers=DEFAULT_HEADERS)
            confirmed = False
            title = handle
            bio = ""
            details = ""

            if ptype == "github_api" and res.status_code == 200:
                data = res.json()
                if data.get("login"):
                    confirmed = True
                    title = data.get("name") or handle
                    bio = data.get("bio") or ""
                    details = f"{data.get('public_repos', 0)} dépôts publics"
            elif ptype == "gitlab_api" and res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and data:
                    confirmed = True
                    title = data[0].get("name") or handle
            elif ptype == "docker_api" and res.status_code == 200:
                confirmed = True
            elif ptype == "devto_api" and res.status_code == 200:
                data = res.json()
                if data.get("username") or data.get("name"):
                    confirmed = True
                    title = data.get("name") or handle
            elif ptype == "duolingo_api" and res.status_code == 200:
                users = res.json().get("users", [])
                u_data = next(
                    (
                        u for u in users
                        if str(u.get("username", "")).lower() == handle.lower()
                    ),
                    None,
                )
                if u_data:
                    confirmed = True
                    title = u_data.get("name") or handle
                    bio = u_data.get("bio") or ""
                    details = f"Cours actifs: {len(u_data.get('courses', []))}"
            elif ptype == "reddit_api" and res.status_code == 200:
                r_data = res.json().get("data", {})
                if r_data and not r_data.get("is_suspended"):
                    confirmed = True
                    title = r_data.get("name") or handle
            elif ptype == "hn_api" and res.status_code == 200 and res.text not in ("null", ""):
                data = res.json()
                if isinstance(data, dict) and data.get("id"):
                    confirmed = True
                    title = data.get("id") or handle
                    details = f"karma={data.get('karma', 0)}"
            elif ptype == "telegram_check" and res.status_code == 200:
                text = res.text
                if "tgme_page_title" in text and "If you have Telegram" in text:
                    confirmed = True
            elif ptype == "http_status" and res.status_code == 200:
                text_l = res.text.lower()
                not_found_markers = (
                    "page not found", "doesn't exist", "does not exist",
                    "user not found", "404", "sorry, this page",
                    "n'existe pas", "introuvable", "couldn’t find",
                    "couldn't find", "no such user", "profile not found",
                    "this account doesn’t exist", "this account doesn't exist",
                )
                # Soft-404 : pages génériques très courtes ou sans le handle
                soft_404 = (
                    len(res.text) < 400
                    or (handle.lower() not in text_l and platform not in ("Keybase", "HuggingFace"))
                )
                if any(m in text_l for m in not_found_markers) or soft_404:
                    confirmed = False
                else:
                    confirmed = True

            if confirmed:
                found_accounts.append({
                    "platform": platform,
                    "handle": handle,
                    "url": web_url,
                    "title": title,
                    "bio": bio,
                    "details": details,
                    "category": probe["category"],
                    "status": "CONFIRMED",
                })
        except Exception:
            continue

    return found_accounts


def investigate_username_osint(username: str) -> Dict[str, Any]:
    """
    Investigation OSINT sur un pseudonyme / handle :
    sondage multi-plateformes + recherche web sans biais cyber.
    """
    handle = (username or "").strip().lstrip("@")
    if not re.match(r"^[A-Za-z0-9_.-]{2,39}$", handle):
        return {
            "status": "error",
            "message": f"Pseudonyme invalide : '{username}'. Attendus : lettres, chiffres, . _ -",
        }

    results: Dict[str, Any] = {
        "status": "success",
        "target_username": handle,
        "registered_platforms": [],
        "web_traces": [],
        "associated_names": [],
        "evidence": [],
        "confidence_score": "LOW",
    }

    with httpx.Client(timeout=4.0, follow_redirects=True) as client:
        matches = _probe_single_handle(handle, client)
        results["registered_platforms"] = matches
        for m in matches:
            results["evidence"].append(f"[{m['platform']}] Compte confirmé : {m['url']}")
            if m.get("title") and m["title"] != handle and m["title"] not in results["associated_names"]:
                results["associated_names"].append(m["title"])

    # Traces web générales (pas limitées à la cyber)
    queries = [
        f'"{handle}"',
        f'@{handle}',
        (
            f'"{handle}" (site:linkedin.com OR site:instagram.com OR site:facebook.com '
            f"OR site:twitter.com OR site:x.com OR site:youtube.com OR site:tiktok.com)"
        ),
    ]
    seen_urls = {p["url"] for p in results["registered_platforms"]}
    for q in queries:
        w_res = search_web(query=q, max_results=5)
        if w_res.get("status") != "success":
            continue
        for r in w_res.get("results", []):
            url = r.get("url") or ""
            title = r.get("title") or ""
            content = r.get("content") or ""
            blob = f"{title} {url} {content}".lower()
            if handle.lower() not in blob:
                continue
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results["web_traces"].append({
                "title": title,
                "url": url,
                "snippet": content,
            })
            results["evidence"].append(f"[Web] {title} — {url}")

    n_confirmed = len(results["registered_platforms"])
    n_web = len(results["web_traces"])
    if n_confirmed >= 3:
        results["confidence_score"] = "HIGH"
    elif n_confirmed >= 1 or n_web >= 2:
        results["confidence_score"] = "MEDIUM"
    else:
        results["confidence_score"] = "LOW"

    if n_confirmed == 0 and n_web == 0:
        results["status"] = "no_results"
        results["message"] = (
            f"Aucune présence confirmée pour '{handle}'. "
            "Ne pas inventer de profils ou de statistiques."
        )

    return results


def investigate_email_osint(email: str) -> Dict[str, Any]:
    """
    Investigation OSINT multi-pivots sur une adresse email :
    Gravatar, commits GitHub, sondage de handles dérivés, traces web générales.
    """
    email_clean = (email or "").strip().lower()
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email_clean):
        return {"status": "error", "message": f"Adresse email invalide : {email}"}

    email_prefix, domain = email_clean.split("@", 1)
    handles_to_probe = set()
    handles_to_probe.add(email_prefix)
    clean_prefix = re.sub(r"\d+", "", email_prefix)
    if len(clean_prefix) >= 3:
        handles_to_probe.add(clean_prefix)
    # Variantes courantes
    for sep in (".", "_", "-"):
        if sep in email_prefix:
            parts = [p for p in email_prefix.split(sep) if len(p) >= 3]
            handles_to_probe.update(parts)
            handles_to_probe.add("".join(parts))

    results: Dict[str, Any] = {
        "status": "success",
        "target_email": email_clean,
        "domain": domain,
        "derived_handles": [],
        "primary_identity": None,
        "associated_names": [],
        "profile_bio": None,
        "evidence": [],
        "registered_platforms": [],
        "discovered_repositories": [],
        "associated_interests": [],
        "web_traces": [],
        "confidence_score": "LOW",
    }

    # 1. Gravatar
    md5_hash = hashlib.md5(email_clean.encode("utf-8")).hexdigest()
    try:
        with httpx.Client(timeout=8.0) as client:
            res = client.get(
                f"https://en.gravatar.com/{md5_hash}.json",
                headers=DEFAULT_HEADERS,
            )
            if res.status_code == 200:
                data = res.json().get("entry", [{}])[0]
                dname = data.get("displayName")
                purl = data.get("profileUrl")
                if dname:
                    results["primary_identity"] = dname
                    results["associated_names"].append(dname)
                    results["evidence"].append(f"[Gravatar] Nom public : {dname}")
                if purl:
                    results["registered_platforms"].append({
                        "platform": "Gravatar",
                        "url": purl,
                        "title": dname or "Profil Gravatar",
                        "status": "CONFIRMED",
                        "category": "Identité",
                    })
                for acc in data.get("verifiedAccounts", []):
                    results["registered_platforms"].append({
                        "platform": acc.get("shortname", "Compte lié"),
                        "url": acc.get("url"),
                        "status": "CONFIRMED",
                        "category": "Compte vérifié",
                    })
                preferred = data.get("preferredUsername")
                if preferred:
                    handles_to_probe.add(preferred)
    except Exception:
        pass

    # 2. GitHub commits / users
    try:
        headers = {**DEFAULT_HEADERS, "Accept": "application/vnd.github+json"}
        with httpx.Client(timeout=20.0, headers=headers) as client:
            c_res = client.get(f"https://api.github.com/search/commits?q=author-email:{email_clean}")
            if c_res.status_code == 200:
                c_data = c_res.json()
                total_commits = c_data.get("total_count", 0)
                if total_commits > 0:
                    results["evidence"].append(
                        f"[GitHub Commits] {total_commits} commit(s) public(s)"
                    )
                    for item in c_data.get("items", [])[:8]:
                        repo_full = item.get("repository", {}).get("full_name")
                        if repo_full and repo_full not in results["discovered_repositories"]:
                            results["discovered_repositories"].append(repo_full)
                            handles_to_probe.add(repo_full.split("/")[0])
                        author_name = item.get("commit", {}).get("author", {}).get("name")
                        if author_name:
                            if author_name not in results["associated_names"]:
                                results["associated_names"].append(author_name)
                            if not results["primary_identity"]:
                                results["primary_identity"] = author_name

            u_res = client.get(f"https://api.github.com/search/users?q={email_clean}+in:email")
            if u_res.status_code == 200:
                for u in u_res.json().get("items", []):
                    if u.get("login"):
                        handles_to_probe.add(u["login"])
    except Exception:
        pass

    # 3. Enrichissement profils GitHub découverts (sans biais de handle hardcodé)
    with httpx.Client(timeout=8.0, follow_redirects=True) as client:
        for h in list(handles_to_probe)[:8]:
            if not re.match(r"^[A-Za-z0-9_-]{2,39}$", h):
                continue
            try:
                gh_u_res = client.get(f"https://api.github.com/users/{h}", headers=DEFAULT_HEADERS)
                if gh_u_res.status_code != 200:
                    continue
                gh_prof = gh_u_res.json()
                real_name = gh_prof.get("name")
                bio = gh_prof.get("bio") or ""
                gh_url = f"https://github.com/{h}"
                if not any(p.get("url") == gh_url for p in results["registered_platforms"]):
                    results["registered_platforms"].append({
                        "platform": "GitHub",
                        "handle": h,
                        "url": gh_url,
                        "title": real_name or h,
                        "bio": bio,
                        "details": f"{gh_prof.get('public_repos', 0)} dépôts publics",
                        "category": "Code",
                        "status": "CONFIRMED",
                    })
                if real_name and real_name not in results["associated_names"]:
                    results["associated_names"].append(real_name)
                if real_name and not results["primary_identity"]:
                    results["primary_identity"] = real_name
                if bio and not results["profile_bio"]:
                    results["profile_bio"] = bio
                if bio:
                    results["evidence"].append(f"[GitHub Bio] @{h}: {bio}")
                    for w in (
                        "SOC", "DFIR", "AI", "CYBERSECURITY", "BLUE TEAM", "PYTHON",
                        "MARKETING", "DESIGN", "FINANCE", "JOURNALISM", "TEACHER",
                    ):
                        if w in bio.upper() and w not in results["associated_interests"]:
                            results["associated_interests"].append(w)
            except Exception:
                continue

    results["derived_handles"] = sorted(handles_to_probe)

    # 4. Sondage multi-plateformes parallèle
    def _probe_worker(h: str) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=4.0, follow_redirects=True) as c:
            return _probe_single_handle(h, c)

    probe_targets = [h for h in handles_to_probe if re.match(r"^[A-Za-z0-9_.-]{2,39}$", h)][:5]
    with ThreadPoolExecutor(max_workers=min(5, max(len(probe_targets), 1))) as executor:
        futures = {executor.submit(_probe_worker, h): h for h in probe_targets}
        for future in as_completed(futures):
            try:
                for m in future.result():
                    if not any(p.get("url") == m["url"] for p in results["registered_platforms"]):
                        results["registered_platforms"].append(m)
                        results["evidence"].append(f"[{m['platform']}] Compte actif : {m['url']}")
            except Exception:
                continue

    # 5. Traces web générales (au-delà de TryHackMe / Root-Me)
    identity_bits = [email_prefix]
    if results.get("primary_identity"):
        identity_bits.append(results["primary_identity"])
    identity_q = " OR ".join(f'"{b}"' for b in identity_bits if b)

    queries = [
        f'"{email_clean}"',
        f"{identity_q}",
        (
            f"({identity_q}) (site:linkedin.com OR site:facebook.com OR site:instagram.com "
            f"OR site:twitter.com OR site:x.com OR site:medium.com OR site:about.me)"
        ),
    ]
    seen_urls = {p.get("url") for p in results["registered_platforms"]}
    for q in queries:
        w_res = search_web(query=q, max_results=5)
        if w_res.get("status") != "success":
            continue
        for r in w_res.get("results", []):
            url = r.get("url") or ""
            title = r.get("title") or ""
            content = r.get("content") or ""
            if url in seen_urls:
                continue
            seen_urls.add(url)
            results["web_traces"].append({
                "title": title,
                "url": url,
                "snippet": content,
            })
            results["evidence"].append(f"[Web] {title} — {url}")

            # Détections opportunistes de plateformes connues
            url_l = url.lower()
            platform_hints = {
                "tryhackme.com": ("TryHackMe", "Cybersécurité"),
                "root-me.org": ("Root-Me", "Cybersécurité"),
                "openclassrooms.com": ("OpenClassrooms", "Formation"),
                "linkedin.com": ("LinkedIn", "Professionnel"),
                "facebook.com": ("Facebook", "Social"),
                "instagram.com": ("Instagram", "Social"),
            }
            for host, (plat, cat) in platform_hints.items():
                if host in url_l and not any(host in (p.get("url") or "") for p in results["registered_platforms"]):
                    results["registered_platforms"].append({
                        "platform": plat,
                        "url": url,
                        "title": title,
                        "category": cat,
                        "status": "LIKELY",
                    })

    if results["primary_identity"] and len(results["registered_platforms"]) >= 2:
        results["confidence_score"] = "HIGH"
    elif results["registered_platforms"] or results["web_traces"]:
        results["confidence_score"] = "MEDIUM"
    elif results["evidence"]:
        results["confidence_score"] = "LOW"
    else:
        results["status"] = "no_results"
        results["message"] = (
            f"Aucune trace publique vérifiable pour {email_clean}. "
            "Ne pas inventer d'identité ni de comptes."
        )

    return results


def harvest_domain_intel(domain: str, max_emails: int = 15) -> Dict[str, Any]:
    """Récolte OSINT sur un domaine : DNS, crt.sh, emails associés."""
    domain_clean = (
        (domain or "").strip().lower()
        .replace("http://", "")
        .replace("https://", "")
        .split("/")[0]
    )
    if not domain_clean or "." not in domain_clean:
        return {"status": "error", "message": f"Domaine invalide : {domain}"}

    results: Dict[str, Any] = {
        "status": "success",
        "domain": domain_clean,
        "mx_servers": [],
        "spf_record": None,
        "dmarc_record": None,
        "discovered_subdomains": [],
        "discovered_emails": [],
    }

    if DNS_AVAILABLE:
        try:
            for rdata in dns.resolver.resolve(domain_clean, "MX"):
                results["mx_servers"].append(str(rdata.exchange).rstrip("."))
        except Exception:
            pass
        try:
            for rdata in dns.resolver.resolve(domain_clean, "TXT"):
                txt = b"".join(rdata.strings).decode("utf-8", errors="ignore")
                if "v=spf1" in txt:
                    results["spf_record"] = txt
        except Exception:
            pass
        try:
            for rdata in dns.resolver.resolve(f"_dmarc.{domain_clean}", "TXT"):
                txt = b"".join(rdata.strings).decode("utf-8", errors="ignore")
                if "v=DMARC1" in txt:
                    results["dmarc_record"] = txt
        except Exception:
            pass

    try:
        with httpx.Client(timeout=12.0) as client:
            res = client.get(f"https://crt.sh/?q=%25.{domain_clean}&output=json")
            if res.status_code == 200:
                subdomains = set()
                for entry in res.json():
                    for sub in entry.get("name_value", "").split("\n"):
                        sub = sub.strip().lower()
                        if sub.endswith(domain_clean) and "*" not in sub:
                            subdomains.add(sub)
                results["discovered_subdomains"] = sorted(subdomains)[:15]
    except Exception:
        pass

    emails_found = set()
    for sq in (f'"@{domain_clean}"', f"site:{domain_clean} email OR contact OR info OR support"):
        w_res = search_web(query=sq, max_results=5)
        if w_res.get("status") != "success":
            continue
        for r in w_res.get("results", []):
            text_to_scan = f"{r.get('title', '')} {r.get('content', '')}"
            for em in re.findall(rf"[a-zA-Z0-9_.+-]+@{re.escape(domain_clean)}", text_to_scan):
                emails_found.add(em.lower())

    results["discovered_emails"] = sorted(emails_found)[:max_emails]
    return results


def generate_osint_graph(
    target_email: str,
    domain: Optional[str] = None,
    associated_names: Optional[List[str]] = None,
    discovered_accounts: Optional[List[Dict[str, Any]]] = None,
    related_emails: Optional[List[str]] = None,
    repositories: Optional[List[str]] = None,
    skills_or_bio: Optional[str] = None,
) -> Dict[str, Any]:
    """Génère un diagramme Mermaid relationnel (sans emojis / stickers)."""
    email_clean = (target_email or "").strip().lower()
    if not email_clean:
        return {"status": "error", "message": "target_email requis."}

    dom = domain or (email_clean.split("@")[1] if "@" in email_clean else "domain.com")
    names = associated_names or []
    accounts = discovered_accounts or []
    colleagues = related_emails or []
    repos = repositories or []

    def _safe(label: str) -> str:
        return re.sub(r'["\[\]]', "", label)[:80]

    lines = ["flowchart TD"]
    lines.append(f'    TARGET["CIBLE: {_safe(email_clean)}"]')

    if names:
        primary_name = _safe(names[0])
        lines.append(f'    ID["IDENTITE: {primary_name}"]')
        lines.append("    TARGET -->|identifie_comme| ID")
        if skills_or_bio:
            clean_bio = _safe(skills_or_bio)[:60]
            lines.append(f'    ROLE["PROFIL: {clean_bio}"]')
            lines.append("    ID -->|specialisation| ROLE")

    lines.append(f'    DOMAIN["DOMAINE: {_safe(dom)}"]')
    lines.append("    TARGET -->|messagerie| DOMAIN")

    for i, acc in enumerate(accounts[:8]):
        node_id = f"ACC_{i}"
        plat = _safe(str(acc.get("platform", "Service")))
        handle = _safe(str(acc.get("handle") or acc.get("title") or "Actif"))
        lines.append(f'    {node_id}["{plat}: {handle}"]')
        lines.append(f"    TARGET -->|compte| {node_id}")

    for i, repo in enumerate(repos[:4]):
        repo_node = f"REPO_{i}"
        lines.append(f'    {repo_node}["PROJET: {_safe(str(repo))}"]')
        lines.append(f"    TARGET -->|commits| {repo_node}")

    for i, col in enumerate(colleagues[:3]):
        if col != email_clean:
            col_node = f"COL_{i}"
            lines.append(f'    {col_node}["RELIE: {_safe(str(col))}"]')
            lines.append(f"    DOMAIN -->|meme_org| {col_node}")

    summary_data = {
        "identity": names[0] if names else None,
        "bio": skills_or_bio,
        "confirmed_platforms_count": len(accounts),
        "discovered_repos_count": len(repos),
    }

    return {
        "status": "success",
        "target": email_clean,
        "domain": dom,
        "mermaid_chart": "\n".join(lines),
        "summary": summary_data,
        "nodes_summary": summary_data,
    }
