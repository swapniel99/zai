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

# Start MCP server (must be running before travel_agent or main.py)
uv run python mcp_server.py          # listens on 127.0.0.1:8000

# Start API server (requires LLM gateway + MCP server running)
uv run python main.py

# Interactive CLI (requires LLM gateway + MCP server running)
uv run python travel_agent.py
```

## Environment

Create `.env` at repo root. Required/optional vars:
```
LLM_GATEWAY_V2_URL=http://localhost:8100   # LLM gateway endpoint
LLM_PROVIDER=cerebras                      # or groq, or omit for auto-select
MCP_SERVER_URL=http://127.0.0.1:8000/mcp  # optional override
MCP_PORT=8000                              # optional override
REDDIT_CLIENT_ID=                          # optional; enables full post content
REDDIT_CLIENT_SECRET=                      # optional; enables full post content
```

Agent traces (full LLM turn logs) written to `logs/trace_<timestamp>.json` automatically.

## Architecture

**ZAI (Zen Adventure Intelligence)** — agentic travel planner. All 4 phases complete.

### Current state (complete)
- `mcp_server.py` — `FastMCP` server registering 6 tools. Tool *registration only*; all logic lives in `tools/`.
- `tools/` — 6 custom Python modules, each mapping to one PRD capability (web search, page reading, Reddit, media, date math, climate).
- `tests/test_tools.py` — 21 pytest tests with `asyncio_mode=auto`; tests primary paths, fallback chains, and MCP registration.
- `travel_agent.py` — core agentic loop. Connects to `mcp_server.py` via HTTP (`streamable_http_client`), fetches tool schemas, runs native tool-calling loop (LLM → tools → LLM) via `llm_gatewayV2`. Exposes `run()` (blocking) and `run_stream()` (async generator, SSE events). `MAX_TURNS = 12`.
- `main.py` — FastAPI on port 8080. `POST /chat/stream` (SSE), `POST /chat` (JSON fallback), `GET /health`, `GET /` (serves UI). In-memory sessions keyed by `session_id`.
- `static/index.html` — single-file chat UI. Consumes `/chat/stream` SSE; renders Markdown (marked.js) with inline images and YouTube embeds; shows thinking/tool-progress pills in a scrollable status bar.

### SSE event schema (`POST /chat/stream`)
Events are `data: <json>\n\n` lines. Frontend must handle all types:

| `type`       | Fields                          | When                                      |
|--------------|---------------------------------|-------------------------------------------|
| `session`    | `session_id`                    | First event; carry `session_id` forward   |
| `thinking`   | `label`                         | Before each LLM call ("Planning your trip...", "Crafting your itinerary...") |
| `tool_start` | `tool`, `label`                 | When a tool call begins (parallel-aware)  |
| `tool_end`   | `tool`, `label`                 | When a tool call completes                |
| `response`   | `text`                          | Final Markdown itinerary                  |
| `error`      | `message`                       | Agent-level exception                     |
| `done`       | —                               | Stream complete                           |

Parallel tool calls fire all `tool_start` events before any `tool_end` (via `asyncio.TaskGroup`).

### LLM gateway
- Client lives in `client.py` at repo root (`LLM` class → `POST /v1/chat`)
- Default URL: `http://localhost:8100` — override with `LLM_GATEWAY_V2_URL` in `.env`
- **No streaming required from gateway** — all LLM calls use `llm.chat()` (blocking). SSE progress comes from tool call events, not LLM token streaming.
- `LLM_PROVIDER` env var sets provider (e.g. `"cerebras"`, `"groq"`); `None` = auto-select
- MCP server URL: `MCP_SERVER_URL` (default `http://127.0.0.1:8000/mcp`), port: `MCP_PORT` (default `8000`)

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
- `python-dotenv` — loaded at startup in both `main.py` and `travel_agent.py`
- Open-Meteo APIs — free, no API key required
- Reddit public JSON API — no credentials required (`REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` in `.env` reserved for future OAuth upgrade)

### Design constraints
- LLM must call `calendar_math_tool` for all date expressions — never compute dates itself
- `search_reddit` restricted to travel subreddits (`solotravel`, `travel`, `TravelHacks`, etc.)
- Agent injects `datetime.now()` into system prompt at runtime for temporal grounding
- Final response must be pure Markdown itinerary — system prompt explicitly blocks `<reasoning>` blocks in the final turn
- System prompt lives in `prompt.md`; PRD in `docs/PRD.md`; architecture in `docs/architecture.md`
