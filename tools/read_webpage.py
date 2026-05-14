import ssl
import httpx
from readability import Document

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
MAX_CHARS = 8000


def _extract(html: str) -> str:
    doc = Document(html)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(doc.summary(), "lxml")
    return soup.get_text(separator="\n", strip=True)[:MAX_CHARS]


async def read_webpage(url: str) -> str:
    # Primary: standard TLS
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            r = await client.get(url)
            r.raise_for_status()
            return _extract(r.text)
    except (ssl.SSLError, httpx.ConnectError, httpx.RemoteProtocolError):
        pass
    except httpx.HTTPStatusError as e:
        return f"HTTP {e.response.status_code} fetching {url}"

    # Fallback: skip TLS cert verification (expired/self-signed certs)
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15, verify=False) as client:
            r = await client.get(url)
            r.raise_for_status()
            return _extract(r.text)
    except (ssl.SSLError, httpx.ConnectError, httpx.RemoteProtocolError) as e:
        return f"Site has unrecoverable TLS configuration error, cannot fetch {url}. Use search snippets instead."
    except Exception as e:
        return f"Failed to fetch {url}: {e}"
