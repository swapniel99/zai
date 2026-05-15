import asyncio
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


async def _is_image_alive(client: httpx.AsyncClient, url: str) -> bool:
    try:
        r = await client.head(url, timeout=4, follow_redirects=True)
        return r.status_code < 400
    except Exception:
        return False


def _is_youtube_embeddable(url: str) -> bool:
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
            results = DDGS().videos(query, max_results=8)
            if not results:
                return f"No videos found for: {query}"
            lines = [f"Videos for: {query} — pick the most destination-relevant result:\n"]
            for i, r in enumerate(results, 1):
                url = r.get("content", r.get("embed_url", ""))
                title = r.get("title", "No title")
                is_yt = "youtube.com" in url or "youtu.be" in url
                if is_yt and not _is_youtube_embeddable(url):
                    lines.append(f"{i}. Title: {title} | [Watch on YouTube: {title}]({url})")
                else:
                    lines.append(f"{i}. Title: {title} | URL: {url}")
            return "\n".join(lines)

        else:
            results = DDGS().images(query, max_results=15)
            if not results:
                return f"No images found for: {query}"

            candidates = [r for r in results if not _is_watermarked(r.get("image", ""))]

            async def pick_live(candidates, want=5):
                async with httpx.AsyncClient() as client:
                    alive = []
                    batch_size = min(len(candidates), want * 2)
                    checks = await asyncio.gather(
                        *[_is_image_alive(client, r["image"]) for r in candidates[:batch_size]]
                    )
                    alive = [r for r, ok in zip(candidates[:batch_size], checks) if ok]
                    if len(alive) < want and batch_size < len(candidates):
                        rest = candidates[batch_size:]
                        checks2 = await asyncio.gather(
                            *[_is_image_alive(client, r["image"]) for r in rest]
                        )
                        alive += [r for r, ok in zip(rest, checks2) if ok]
                    return alive[:want]

            live = asyncio.run(pick_live(candidates))
            if not live:
                return f"No accessible images found for: {query}"
            lines = [f"Images for: {query}\n"]
            for i, r in enumerate(live, 1):
                lines.append(f"{i}. {r.get('image', '')}")
            return "\n".join(lines)

    except Exception as e:
        return f"Media search failed: {e}"
