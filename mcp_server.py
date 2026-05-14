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
    Search the web for travel information, event dates, visa requirements,
    safety advisories, and general destination research.
    Returns ranked snippets with URLs. Use read_webpage_tool to get full content from a URL.
    """
    return search_web(query, max_results)


@mcp.tool()
async def read_webpage_tool(url: str) -> str:
    """
    Fetch and extract full text content from a URL.
    Use this after search_web_tool to deeply investigate official government advisories,
    visa portals, festival schedules, or travel forums.
    If the site has unrecoverable TLS issues, falls back to a clear error — use search snippets instead.
    """
    return await read_webpage(url)


@mcp.tool()
async def search_reddit_tool(query: str, max_results: int = 5) -> str:
    """
    Search Reddit for authentic first-hand traveler experiences.
    Use for: solo travel safety tips, local substance laws, nightlife recommendations,
    event reviews, and scam warnings. Targets r/solotravel, r/travel, and city subreddits.
    Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET env vars for full post content (60 req/min).
    Without credentials, falls back to web search snippets (10 req/min).
    """
    return await search_reddit(query, max_results)


@mcp.tool()
def search_media_tool(query: str, media_type: str = "image") -> str:
    """
    Fetch media URLs for embedding in the itinerary response.
    media_type: 'image' for photos of a location or event, 'video' for embeddable clips (prefers YouTube).
    Returns direct URLs ready to use in Markdown image/video embeds.
    """
    return search_media(query, media_type)


@mcp.tool()
def calendar_math_tool(query: str) -> str:
    """
    Resolve a natural language date expression to a concrete date. Always use this tool
    instead of guessing dates yourself — it eliminates hallucination for time-sensitive itineraries.

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
    Use for location-first queries (what's the best time to visit?) and climate clarifications.
    month: month name or 'Month YYYY' — e.g. 'April', 'April 2027', 'January'.
    Uses live forecast for near-term dates; ERA5 historical archive (3-year avg) for future months.
    """
    return await get_climate_data(location, month)


if __name__ == "__main__":
    mcp.run()
