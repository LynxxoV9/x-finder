import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
import httpx
from app.config import settings


def _is_usable_tavily_key(key: Optional[str]) -> bool:
    """Refuse les placeholders / clés démo (ex: tvly-demo...) qui provoquent des 401 silencieux."""
    if not key:
        return False
    k = key.strip()
    if not k.startswith("tvly-"):
        return False
    if len(k) < 30:
        return False
    lowered = k.lower()
    for bad in ("demo", "votre", "example", "xxxx", "placeholder", "changez"):
        if bad in lowered:
            return False
    return True


_HIGH_RELIABILITY = (
    "wikipedia.org", "bbc.com", "bbc.co.uk", "reuters.com", "afp.com",
    "jeuneafrique.com", "lemonde.fr", "france24.com", "rfi.fr", "voaafrique.com",
    "gov.", "gouv.", "un.org", "who.int", "fifa.com", "uefa.com",
    "transfermarkt.", "espn.com", "sofascore.com",
)
_LOW_RELIABILITY = (
    "facebook.com", "fb.com", "instagram.com", "tiktok.com", "reddit.com",
    "quora.com", "pinterest.com", "tumblr.com", "blogspot.", "wordpress.com",
    "medium.com", "forum.", "forums.",
)
_CYBER_AUTHORITY_DOMAINS = (
    "cve.org",
    "nist.gov",
    "cisa.gov",
    "cert.europa.eu",
    "ncsc.nl",
    "microsoft.com",
    "php.net",
)


def _is_cyber_authority(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower().rstrip(".")
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in _CYBER_AUTHORITY_DOMAINS
    )


def _source_reliability(url: str) -> str:
    u = (url or "").lower()
    if any(h in u for h in _HIGH_RELIABILITY):
        return "high"
    if any(h in u for h in _LOW_RELIABILITY):
        return "low"
    return "medium"


def _normalize_results(raw: List[Dict[str, Any]], max_results: int) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    seen = set()
    for item in raw:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        content = (item.get("content") or item.get("snippet") or "").strip()
        if not title or not url:
            continue
        if url in seen:
            continue
        seen.add(url)
        reliability = _source_reliability(url)
        security_authority = _is_cyber_authority(url)
        cleaned.append({
            "title": title,
            "url": url,
            "content": content,
            "published_date": item.get("published_date"),
            "reliability": reliability,
            "use_as_hard_fact": reliability == "high",
            "security_authority": security_authority,
            "warning": (
                "Source faible : ne pas affirmer un fait biographique sensible "
                "(enfants, décès, mariage) à partir de ce seul résultat."
                if reliability == "low"
                else (
                    "Pour une affirmation de cybersécurité, vérifier une source officielle "
                    "CVE/NVD/CISA ou un avis officiel du fournisseur."
                    if not security_authority
                    else None
                )
            ),
        })
        if len(cleaned) >= max_results:
            break
    # Prioriser les sources fiables dans l'ordre présenté au LLM
    cleaned.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["reliability"], 1))
    return cleaned


def _search_tavily(query: str, search_depth: str, max_results: int, include_news: bool) -> Optional[Dict[str, Any]]:
    if not _is_usable_tavily_key(settings.TAVILY_API_KEY):
        return None
    try:
        payload = {
            "api_key": settings.TAVILY_API_KEY,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": True,
            "topic": "news" if include_news else "general",
        }
        with httpx.Client(timeout=8.0) as client:
            res = client.post("https://api.tavily.com/search", json=payload)
            if res.status_code != 200:
                return None
            data = res.json()
            results = _normalize_results(
                [
                    {
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "content": item.get("content"),
                        "published_date": item.get("published_date"),
                    }
                    for item in data.get("results", [])
                ],
                max_results,
            )
            if not results:
                return None
            return {
                "status": "success",
                "provider": "Tavily",
                "query": query,
                "direct_answer": data.get("answer"),
                "results": results,
                "sources": [item["url"] for item in results],
            }
    except Exception:
        return None


def _parse_ddg_html(html: str, max_results: int) -> List[Dict[str, Any]]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict[str, Any]] = []

    # html.duckduckgo.com
    for result in soup.find_all("div", class_="result"):
        title_elem = result.find("a", class_="result__a")
        snippet_elem = result.find("a", class_="result__snippet") or result.find("div", class_="result__snippet")
        if not title_elem:
            continue
        href = title_elem.get("href", "")
        title = title_elem.get_text(strip=True)
        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
        if title and href:
            results.append({"title": title, "url": href, "content": snippet})
        if len(results) >= max_results:
            return results

    # lite.duckduckgo.com
    if not results:
        for row in soup.select("table tr"):
            link = row.find("a", href=True)
            if not link:
                continue
            href = link["href"]
            if not href.startswith("http"):
                continue
            title = link.get_text(strip=True)
            snippet_td = row.find_all("td")
            snippet = snippet_td[-1].get_text(strip=True) if len(snippet_td) > 1 else ""
            if title:
                results.append({"title": title, "url": href, "content": snippet})
            if len(results) >= max_results:
                break

    return results


def _search_duckduckgo(query: str, max_results: int) -> Optional[Dict[str, Any]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }
    endpoints = [
        ("POST", "https://html.duckduckgo.com/html/", {"q": query}),
        ("POST", "https://lite.duckduckgo.com/lite/", {"q": query}),
    ]
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True, headers=headers) as client:
            for method, url, data in endpoints:
                try:
                    res = client.request(method, url, data=data)
                    if res.status_code != 200:
                        continue
                    parsed = _normalize_results(_parse_ddg_html(res.text, max_results), max_results)
                    if parsed:
                        return {
                            "status": "success",
                            "provider": "DuckDuckGo",
                            "query": query,
                            "results": parsed,
                            "sources": [item["url"] for item in parsed],
                        }
                except Exception:
                    continue
    except Exception:
        return None
    return None


def _search_ddg_instant(query: str, max_results: int) -> Optional[Dict[str, Any]]:
    """API Instant Answer DuckDuckGo (JSON) — repli léger sans scraping HTML."""
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            res = client.get(
                "https://api.duckduckgo.com/",
                params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            )
            if res.status_code != 200:
                return None
            data = res.json()
            raw = []
            if data.get("AbstractText") and data.get("AbstractURL"):
                raw.append({
                    "title": data.get("Heading") or query,
                    "url": data.get("AbstractURL"),
                    "content": data.get("AbstractText"),
                })
            for topic in data.get("RelatedTopics", [])[: max_results + 2]:
                if isinstance(topic, dict) and topic.get("FirstURL") and topic.get("Text"):
                    raw.append({
                        "title": topic.get("Text", "")[:120],
                        "url": topic.get("FirstURL"),
                        "content": topic.get("Text", ""),
                    })
                elif isinstance(topic, dict) and "Topics" in topic:
                    for sub in topic.get("Topics", [])[:3]:
                        if sub.get("FirstURL") and sub.get("Text"):
                            raw.append({
                                "title": sub.get("Text", "")[:120],
                                "url": sub.get("FirstURL"),
                                "content": sub.get("Text", ""),
                            })
            results = _normalize_results(raw, max_results)
            if not results:
                return None
            return {
                "status": "success",
                "provider": "DuckDuckGo Instant Answer",
                "query": query,
                "direct_answer": data.get("AbstractText") or None,
                "results": results,
                "sources": [item["url"] for item in results],
            }
    except Exception:
        return None


def _search_wikipedia(query: str, max_results: int) -> Optional[Dict[str, Any]]:
    """Repli Wikipedia (FR puis EN) — OpenSearch + query/search avec snippets."""
    # UA compatible Wikimedia (les UA génériques / "X-Finder" seuls sont souvent 403)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; XFinderBot/1.0; +https://localhost)",
        "Accept": "application/json",
    }
    raw: List[Dict[str, Any]] = []
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True, headers=headers) as client:
            for lang in ("fr", "en"):
                # 1) Recherche plein texte avec snippets
                res = client.get(
                    f"https://{lang}.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "srlimit": max_results,
                        "format": "json",
                        "utf8": 1,
                    },
                )
                if res.status_code == 200:
                    for hit in res.json().get("query", {}).get("search", []):
                        title = hit.get("title") or ""
                        snippet = re.sub(r"<[^>]+>", "", hit.get("snippet") or "")
                        url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
                        raw.append({"title": title, "url": url, "content": snippet or title})

                # 2) OpenSearch en complément
                res2 = client.get(
                    f"https://{lang}.wikipedia.org/w/api.php",
                    params={
                        "action": "opensearch",
                        "search": query,
                        "limit": max_results,
                        "namespace": 0,
                        "format": "json",
                    },
                )
                if res2.status_code == 200:
                    data = res2.json()
                    if isinstance(data, list) and len(data) >= 4:
                        for title, desc, url in zip(data[1], data[2], data[3]):
                            raw.append({"title": title, "url": url, "content": desc or title})

                if len(raw) >= max_results:
                    break

        results = _normalize_results(raw, max_results)
        if not results:
            return None
        return {
            "status": "success",
            "provider": "Wikipedia",
            "query": query,
            "results": results,
            "sources": [item["url"] for item in results],
        }
    except Exception:
        return None


def _search_ddgs(query: str, max_results: int) -> Optional[Dict[str, Any]]:
    """Repli via librairie ddgs / duckduckgo_search si installée."""
    try:
        try:
            from ddgs import DDGS  # type: ignore
        except ImportError:
            from duckduckgo_search import DDGS  # type: ignore
        raw = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                raw.append({
                    "title": item.get("title"),
                    "url": item.get("href") or item.get("link") or item.get("url"),
                    "content": item.get("body") or item.get("snippet") or "",
                })
        results = _normalize_results(raw, max_results)
        if not results:
            return None
        return {
            "status": "success",
            "provider": "DDGS",
            "query": query,
            "results": results,
            "sources": [item["url"] for item in results],
        }
    except Exception:
        return None


def search_web(
    query: str,
    search_depth: str = "basic",
    max_results: int = 5,
    include_news: bool = False,
) -> Dict[str, Any]:
    """
    Recherche web temps réel.
    Priorité : Tavily (clé valide) → DuckDuckGo HTML/Lite.
    Ne fabrique jamais de résultats factices.
    """
    q = (query or "").strip()
    if not q:
        return {"status": "error", "message": "Requête de recherche vide.", "results": [], "sources": []}

    max_results = max(1, min(int(max_results or 5), 10))

    # Ordre : Tavily (si clé réelle) → DDGS → Wikipedia → DDG HTML/Instant
    for provider_fn in (
        lambda: _search_tavily(q, search_depth, max_results, include_news),
        lambda: _search_ddgs(q, max_results),
        lambda: _search_wikipedia(q, max_results),
        lambda: _search_duckduckgo(q, max_results),
        lambda: _search_ddg_instant(q, max_results),
    ):
        try:
            hit = provider_fn()
        except Exception:
            hit = None
        if hit and hit.get("results"):
            return hit

    return {
        "status": "no_results",
        "provider": "none",
        "query": q,
        "message": (
            "Aucun résultat web récupérable (Tavily démo/absent, DuckDuckGo et Wikipedia sans réponse). "
            "Configurez une vraie TAVILY_API_KEY. Ne pas inventer d'informations."
        ),
        "results": [],
        "sources": [],
        "hint_url": "https://duckduckgo.com/?q=" + re.sub(r"\s+", "+", q),
    }
