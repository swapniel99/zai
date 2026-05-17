import logging
import os
from fastmcp import FastMCP

from tools.calendar_math import calendar_math
from tools.get_climate_data import get_climate_data
from tools.read_webpage import read_webpage
from tools.search_media import search_media
from tools.search_reddit import search_reddit
from tools.search_web import search_web

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
_log = logging.getLogger("zai.mcp")

mcp = FastMCP("solo-explorer-tools")


@mcp.tool()
def search_web_tool(query: str, max_results: int = 5) -> str:
    """
    Search the web for any query.
    Returns ranked snippets with URLs. Use read_webpage_tool to fetch full content from a URL.
    """
    _log.info("search_web query=%r max=%d", query, max_results)
    result = search_web(query, max_results)
    _log.info("search_web → %d chars", len(result))
    return result


@mcp.tool()
async def read_webpage_tool(url: str) -> str:
    """
    Fetch and extract the full text content of a URL.
    Falls back to a clear error on unrecoverable TLS failures — use search snippets instead.
    """
    _log.info("read_webpage url=%r", url)
    result = await read_webpage(url)
    _log.info("read_webpage → %d chars", len(result))
    return result


@mcp.tool()
async def search_reddit_tool(query: str, max_results: int = 5) -> str:
    """
    Search Reddit for first-hand community discussions and opinions on any topic.
    Returns post titles, scores, and content snippets from relevant subreddits.
    """
    _log.info("search_reddit query=%r max=%d", query, max_results)
    result = await search_reddit(query, max_results)
    _log.info("search_reddit → %d chars", len(result))
    return result


@mcp.tool()
def search_media_tool(query: str, media_type: str = "image", max_results: int = 5) -> str:
    """
    Fetch media URLs for a query.
    media_type: 'image' returns live, non-watermarked photo URLs ready for Markdown embeds.
    media_type: 'video' returns up to 8 results, each with a title and URL (prefers YouTube).
    max_results: max images to return (default 5); ignored for video.
    """
    _log.info("search_media query=%r type=%s max=%d", query, media_type, max_results)
    result = search_media(query, media_type, max_results)
    _log.info("search_media → %d chars", len(result))
    return result


@mcp.tool()
def calendar_math_tool(query: str) -> str:
    """
    Resolve a natural language date expression to a concrete date.
    Always use this tool instead of computing dates yourself — eliminates hallucination.

    Supported patterns:
    - Fuzzy month        : 'early May', 'mid October', 'late April 2027'
    - Ordinal weekday    : 'last Sunday of December', 'first Monday of March 2027'
    - Relative offsets   : '14 days from today', '3 weeks from now', 'next Friday'
    - Absolute dates     : 'March 22', 'October 31 2027', 'tomorrow', 'today'
    """
    _log.info("calendar_math query=%r", query)
    result = calendar_math(query)
    _log.info("calendar_math → %r", result)
    return result


@mcp.tool()
async def get_climate_data_tool(location: str, month: str) -> str:
    """
    Get average temperature range and precipitation for a location and month.
    month: month name or 'Month YYYY' — e.g. 'April', 'April 2027', 'January'.
    Uses live forecast for near-term dates; ERA5 historical archive (3-year avg) for future months.
    """
    _log.info("get_climate_data location=%r month=%r", location, month)
    result = await get_climate_data(location, month)
    _log.info("get_climate_data → %d chars", len(result))
    return result


@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", "8000"))
    _log.info("starting mcp server on port=%d", port)
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
