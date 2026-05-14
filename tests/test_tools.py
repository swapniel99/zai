"""
Pytest suite for all MCP tools — primary and fallback paths.
Run: uv run pytest
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import httpx
import pytest


# ─── search_web ───────────────────────────────────────────────────────────────

class TestSearchWeb:
    def test_primary_returns_relevant_results(self):
        from tools.search_web import search_web

        r = search_web("Up Helly Aa Shetland 2026 date", max_results=3)
        assert "up helly aa" in r.lower()
        assert "2026" in r
        assert "search failed" not in r.lower()

    def test_non_empty_response(self):
        from tools.search_web import search_web

        r = search_web("solo travel", max_results=1)
        assert "result" in r.lower()


# ─── read_webpage ─────────────────────────────────────────────────────────────

class TestReadWebpage:
    async def test_primary_normal_https(self):
        from tools.read_webpage import read_webpage

        r = await read_webpage("https://uphellyaa.org/up-helly-aa-2026/")
        assert "up helly aa" in r.lower()
        assert "2026" in r
        assert "failed to fetch" not in r.lower()

    async def test_fallback_expired_cert(self):
        from tools.read_webpage import read_webpage

        r = await read_webpage("https://expired.badssl.com/")
        assert "failed to fetch" not in r.lower()
        assert "unrecoverable" not in r.lower()
        assert "expired" in r.lower()

    async def test_unrecoverable_tls_returns_clear_error(self):
        from tools.read_webpage import read_webpage

        r = await read_webpage("https://www.visitshetland.com/up-helly-aa")
        assert "unrecoverable" in r.lower()


# ─── search_reddit ────────────────────────────────────────────────────────────

class TestSearchReddit:
    async def test_primary_reddit_json_api(self):
        from tools.search_reddit import search_reddit

        r = await search_reddit("solo female travel Japan safety", max_results=3)
        assert "r/" in r
        assert "reddit.com" in r
        assert "web fallback" not in r.lower()
        assert "failed" not in r.lower()

    async def test_fallback_ddgs_when_reddit_api_fails(self):
        from tools.search_reddit import search_reddit

        with patch("tools.search_reddit.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.ConnectError("timeout")
            r = await search_reddit("cannabis laws Amsterdam solo travel", max_results=3)

        assert "reddit.com" in r
        assert "no reddit results found" not in r.lower()


# ─── search_media ─────────────────────────────────────────────────────────────

class TestSearchMedia:
    def test_images_returns_urls(self):
        from tools.search_media import search_media

        r = search_media("Shetland Up Helly Aa fire festival", media_type="image")
        assert "http" in r
        assert "failed" not in r.lower()
        assert "no images" not in r.lower()

    def test_videos_returns_urls(self):
        from tools.search_media import search_media

        r = search_media("Kyoto cherry blossom sakura", media_type="video")
        assert "http" in r
        assert "failed" not in r.lower()
        assert "no videos" not in r.lower()


# ─── calendar_math ────────────────────────────────────────────────────────────

class TestCalendarMath:
    @pytest.mark.parametrize("query,expected", [
        ("last Tuesday of January 2027",  "2027-01-26"),
        ("first Monday of March 2027",    "2027-03-01"),
        ("early May 2027",                "2027-05-05"),
        ("late April 2027",               "2027-04-25"),
    ])
    def test_fixed_date_expressions(self, query, expected):
        from tools.calendar_math import calendar_math

        r = calendar_math(query)
        assert expected in r

    def test_relative_14_days(self):
        from tools.calendar_math import calendar_math

        expected = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
        r = calendar_math("14 days from today")
        assert expected in r

    def test_tomorrow(self):
        from tools.calendar_math import calendar_math

        expected = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        r = calendar_math("tomorrow")
        assert expected in r

    def test_unresolvable_returns_error(self):
        from tools.calendar_math import calendar_math

        r = calendar_math("xyzfoobar not a date")
        assert "could not resolve" in r.lower()


# ─── get_climate_data ─────────────────────────────────────────────────────────

class TestGetClimateData:
    async def test_historical_era5_archive(self):
        from tools.get_climate_data import get_climate_data

        r = await get_climate_data("Kyoto, Japan", "April 2027")
        assert "kyoto" in r.lower()
        assert "°c" in r.lower()
        assert "mm" in r
        assert "failed" not in r.lower()
        assert "could not" not in r.lower()

    async def test_forecast_current_month(self):
        from tools.get_climate_data import get_climate_data

        forecast_month = datetime.now().strftime("%B %Y")
        r = await get_climate_data("Tokyo, Japan", forecast_month)
        assert "tokyo" in r.lower()
        assert "°c" in r.lower()
        assert "failed" not in r.lower()
        assert "could not" not in r.lower()

    async def test_bad_location_returns_geocode_error(self):
        from tools.get_climate_data import get_climate_data

        r = await get_climate_data("zzznowherexyz", "April")
        assert "could not geocode" in r.lower()


# ─── mcp_server registration ──────────────────────────────────────────────────

class TestMcpServer:
    async def test_all_tools_registered(self):
        import mcp_server

        tools = await mcp_server.mcp.list_tools()
        registered = {t.name for t in tools}
        expected = {
            "search_web_tool",
            "read_webpage_tool",
            "search_reddit_tool",
            "search_media_tool",
            "calendar_math_tool",
            "get_climate_data_tool",
        }
        assert expected == registered

    async def test_all_tools_have_descriptions(self):
        import mcp_server

        tools = await mcp_server.mcp.list_tools()
        for t in tools:
            assert t.description and len(t.description.strip()) >= 10, \
                f"{t.name} missing description"
