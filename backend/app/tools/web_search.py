import json
import httpx
from typing import Dict, Any, List
from app.config import settings

# Outil de recherche sur le Web et actualités (Tavily Search API avec repli intelligent)
def search_web(query: str, search_depth: str = "basic", max_results: int = 5, include_news: bool = False) -> Dict[str, Any]:
    """
    Recherche des informations ou actualités récentes sur Internet.
    Retourne une liste de résultats avec liens sources, titres et synthèses de contenu.
    """
    # Si la clé Tavily est disponible, on interroge l'API officielle Tavily
    if settings.TAVILY_API_KEY and settings.TAVILY_API_KEY.startswith("tvly-"):
        try:
            url = "https://api.tavily.com/search"
            payload = {
                "api_key": settings.TAVILY_API_KEY,
                "query": query,
                "search_depth": search_depth,
                "max_results": max_results,
                "include_answer": True,
                "topic": "news" if include_news else "general"
            }
            with httpx.Client(timeout=15.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    results = []
                    for item in data.get("results", []):
                        results.append({
                            "title": item.get("title"),
                            "url": item.get("url"),
                            "content": item.get("content"),
                            "published_date": item.get("published_date")
                        })
                    return {
                        "status": "success",
                        "provider": "Tavily",
                        "query": query,
                        "direct_answer": data.get("answer"),
                        "results": results,
                        "sources": [item.get("url") for item in results]
                    }
        except Exception as e:
            # En cas d'erreur réseau sur Tavily, bascule vers le repli
            pass

    # Repli automatique (Zero-Key DuckDuckGo HTML / Instant Answers)
    # Permet à l'enseignant de tester la recherche sans clé API externe
    try:
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            res = client.post(url, data={"q": query}, headers=headers)
            if res.status_code == 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(res.text, "html.parser")
                results = []
                for result in soup.find_all("div", class_="result", limit=max_results):
                    link_elem = result.find("a", class_="result__url") or result.find("a", class_="result__snippet")
                    title_elem = result.find("a", class_="result__a")
                    snippet_elem = result.find("a", class_="result__snippet")
                    
                    if title_elem:
                        href = title_elem.get("href", "")
                        title = title_elem.get_text(strip=True)
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        results.append({
                            "title": title,
                            "url": href,
                            "content": snippet
                        })
                
                if results:
                    return {
                        "status": "success",
                        "provider": "DuckDuckGo (Zero-Key Fallback)",
                        "query": query,
                        "results": results,
                        "sources": [item["url"] for item in results]
                    }
    except Exception as e:
        return {
            "status": "error",
            "provider": "None",
            "message": f"Erreur lors de la recherche Web : {str(e)}"
        }

    return {
        "status": "warning",
        "provider": "Fallback",
        "query": query,
        "results": [
            {
                "title": f"Recherche pour : {query}",
                "url": f"https://www.google.com/search?q={query}",
                "content": f"Aucun résultat direct n'a pu être extrait. Consultez le lien ci-dessus."
            }
        ],
        "sources": [f"https://www.google.com/search?q={query}"]
    }
