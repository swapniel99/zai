import asyncio

import httpx
from ddgs import DDGS

HEADERS = {"User-Agent": "solo-explorer-agent/1.0"}
TRAVEL_SUBREDDITS = "solotravel+travel+TravelHacks+digitalnomad+backpacking+shoestring+longtermtravel"
REDDIT_SEARCH = f"https://www.reddit.com/r/{TRAVEL_SUBREDDITS}/search.json"


def _fmt_posts(data: dict, query: str) -> str:
    posts = data.get("data", {}).get("children", [])
    if not posts:
        return f"No Reddit results found for: {query}"
    lines = [f"Reddit results for: {query}\n"]
    for i, child in enumerate(posts, 1):
        p = child["data"]
        lines.append(f"{i}. r/{p.get('subreddit')} — {p.get('title')}")
        lines.append(f"   Score: {p.get('score')} | Comments: {p.get('num_comments')}")
        lines.append(f"   URL: https://reddit.com{p.get('permalink')}")
        selftext = p.get("selftext", "").strip()
        if selftext:
            lines.append(f"   {selftext[:400]}")
        lines.append("")
    return "\n".join(lines)


def _search_via_ddgs(query: str, max_results: int) -> str:
    results = DDGS().text(f"site:reddit.com {query}", max_results=max_results)
    if not results:
        return f"No Reddit results found for: {query}"
    lines = [f"Reddit search results (web fallback) for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', '')}")
        lines.append(f"   URL: {r.get('href', '')}")
        lines.append(f"   {r.get('body', '')}\n")
    return "\n".join(lines)


async def search_reddit(query: str, max_results: int = 5, sort: str = "relevance", time_filter: str = "all") -> str:
    """Search Reddit for first-hand traveler experiences, safety tips, local laws, and nightlife advice."""
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=10) as client:
            resp = await client.get(
                REDDIT_SEARCH,
                params={"q": query, "sort": sort, "t": time_filter, "limit": max_results, "restrict_sr": 1},
            )
            resp.raise_for_status()
            return _fmt_posts(resp.json(), query)
    except Exception:
        return await asyncio.to_thread(_search_via_ddgs, query, max_results)
