import os
from fastmcp import FastMCP

from tools.calendar_math import calendar_math
from tools.get_climate_data import get_climate_data
from tools.read_webpage import read_webpage
from tools.search_media import search_media
from tools.search_reddit import search_reddit
from tools.search_web import search_web

mcp = FastMCP("solo-explorer-tools")


@mcp.tool()
def search_web_tool(query: str, max_results: int = 5) -> str:
    """
    Search the web for any query.
    Returns ranked snippets with URLs. Use read_webpage_tool to fetch full content from a URL.
    """
    return search_web(query, max_results)


@mcp.tool()
async def read_webpage_tool(url: str) -> str:
    """
    Fetch and extract the full text content of a URL.
    Falls back to a clear error on unrecoverable TLS failures — use search snippets instead.
    """
    return await read_webpage(url)


@mcp.tool()
async def search_reddit_tool(query: str, max_results: int = 5) -> str:
    """
    Search Reddit for first-hand community discussions and opinions on any topic.
    Returns post titles, scores, and content snippets from relevant subreddits.
    """
    return await search_reddit(query, max_results)


@mcp.tool()
def search_media_tool(query: str, media_type: str = "image", max_results: int = 5) -> str:
    """
    Fetch media URLs for a query.
    media_type: 'image' returns live, non-watermarked photo URLs ready for Markdown embeds.
    media_type: 'video' returns up to 8 results, each with a title and URL (prefers YouTube).
    max_results: max images to return (default 5); ignored for video.
    """
    return search_media(query, media_type, max_results)


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
    return calendar_math(query)


@mcp.tool()
async def get_climate_data_tool(location: str, month: str) -> str:
    """
    Get average temperature range and precipitation for a location and month.
    month: month name or 'Month YYYY' — e.g. 'April', 'April 2027', 'January'.
    Uses live forecast for near-term dates; ERA5 historical archive (3-year avg) for future months.
    """
    return await get_climate_data(location, month)


if __name__ == "__main__":
    port = int(os.getenv("MCP_PORT", "8000"))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
