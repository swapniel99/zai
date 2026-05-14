from ddgs import DDGS


def search_web(query: str, max_results: int = 5) -> str:
    """Search the web. Returns ranked snippets with URLs."""
    try:
        results = DDGS().text(query, max_results=max_results)
    except Exception as e:
        return f"Search failed: {e}"

    if not results:
        return f"No results found for: {query}"

    lines = [f"Found {len(results)} results for: {query}\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title', 'No title')}")
        lines.append(f"   URL: {r.get('href', '')}")
        lines.append(f"   {r.get('body', '')}\n")
    return "\n".join(lines)
