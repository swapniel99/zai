import httpx
from ddgs import DDGS

_WATERMARKED_DOMAINS = {
    "alamy.com", "gettyimages.com", "istockphoto.com", "shutterstock.com",
    "dreamstime.com", "123rf.com", "depositphotos.com", "stock.adobe.com",
    "bigstockphoto.com", "canstockphoto.com",
}

def _is_watermarked(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        return any(host == d or host.endswith("." + d) for d in _WATERMARKED_DOMAINS)
    except Exception:
        return False


def _is_youtube_embeddable(url: str) -> bool:
    """Return True if the YouTube video allows embedding."""
    try:
        r = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=5,
        )
        return r.status_code == 200
    except Exception:
        return False


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
                url = r.get("content", r.get("embed_url", ""))
                title = r.get("title", "No title")
                is_yt = "youtube.com" in url or "youtu.be" in url
                if is_yt and not _is_youtube_embeddable(url):
                    lines.append(f"{i}. [Watch on YouTube: {title}]({url})")
                else:
                    lines.append(f"{i}. {url}")
            return "\n".join(lines)

        else:
            results = DDGS().images(query, max_results=10)
            if not results:
                return f"No images found for: {query}"
            clean = [r for r in results if not _is_watermarked(r.get("image", ""))][:5]
            if not clean:
                return f"No non-watermarked images found for: {query}"
            lines = [f"Images for: {query}\n"]
            for i, r in enumerate(clean, 1):
                lines.append(f"{i}. {r.get('image', '')}")
            return "\n".join(lines)

    except Exception as e:
        return f"Media search failed: {e}"
