from ddgs import DDGS


def search_media(query: str, media_type: str = "image") -> str:
    """
    Fetch media URLs for embedding in the itinerary.
    media_type: 'image' or 'video' (videos prefer YouTube links).
    Returns direct URLs ready to embed in Markdown.
    """
    try:
        if media_type == "video":
            results = DDGS().videos(query, max_results=5)
            if not results:
                return f"No videos found for: {query}"
            lines = [f"Videos for: {query}\n"]
            for i, r in enumerate(results, 1):
                embed_url = r.get("content", r.get("embed_url", ""))
                title = r.get("title", "No title")
                lines.append(f"{i}. {title}")
                lines.append(f"   URL: {embed_url}\n")
            return "\n".join(lines)

        else:
            results = DDGS().images(query, max_results=5)
            if not results:
                return f"No images found for: {query}"
            lines = [f"Images for: {query}\n"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r.get('title', 'No title')}")
                lines.append(f"   URL: {r.get('image', '')}\n")
            return "\n".join(lines)

    except Exception as e:
        return f"Media search failed: {e}"
