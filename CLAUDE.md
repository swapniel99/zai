# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install deps
uv sync

# Run all tests (live APIs + fallbacks)
uv run pytest

# Run a single test file or test class
uv run pytest tests/test_tools.py::TestCalendarMath
uv run pytest tests/test_tools.py::TestCalendarMath::test_tomorrow

# Start MCP server
uv run python mcp_server.py
```

## Architecture

**Solo Explorer Agent** — agentic travel planner. Phases 1–2 complete; Phase 3+ in progress.

### Current state (complete)
- `mcp_server.py` — `FastMCP` server registering 6 tools. Tool *registration only*; all logic lives in `tools/`.
- `tools/` — 6 custom Python modules, each mapping to one PRD capability (web search, page reading, Reddit, media, date math, climate).
- `tests/test_tools.py` — 21 pytest tests with `asyncio_mode=auto`; tests primary paths, fallback chains, and MCP registration.

### Planned (not yet built)
- `travel_agent.py` — agentic loop: connect to MCP server via streamable-http, inject current date into system prompt, native JSON tool-calling loop (LLM → tools → LLM), in-memory session history.
- `main.py` (FastAPI) — `POST /chat`, session management, spawns MCP server subprocess.
- Browser frontend — stateless chat UI, renders Markdown with embedded images/video.

### Tool fallback chains
- `read_webpage`: httpx standard TLS → httpx `verify=False` → explicit error string (LLM falls back to `search_web`)
- `search_reddit`: Reddit public JSON API → `ddgs` `site:reddit.com` search
- `get_climate_data`: Open-Meteo Forecast API (≤16 days out) vs. Archive API (ERA5, 3-year avg for future months)

### Key dependencies
- `fastmcp` — MCP server framework
- `ddgs` — DuckDuckGo search (replaces `duckduckgo-search`); sync-only, no async API
- `httpx` — async HTTP for `read_webpage`, `search_reddit`, `get_climate_data`
- `readability-lxml` + `beautifulsoup4` — webpage text extraction
- `parsedatetime` + `dateparser` — date resolution pipeline in `calendar_math`
- Open-Meteo APIs — free, no API key required
- Reddit public JSON API — no credentials required (env vars `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` enable full post content at higher rate limits)

### Design constraints
- LLM must call `calendar_math_tool` for all date expressions — never compute dates itself
- `search_reddit` restricted to travel subreddits (`solotravel`, `travel`, `TravelHacks`, etc.)
- Agent injects `datetime.now()` into system prompt at runtime for temporal grounding
- System prompt lives in `docs/draft_prompt.md`; PRD in `docs/PRD.md`; architecture in `docs/architecture.md`
