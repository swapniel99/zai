# ZAI — Solo Explorer Agent: Implementation Plan

## Phase 1: Foundations ✅

- [x] Write PRD (`docs/PRD.md`)
- [x] Write system prompt (`docs/draft_prompt.md`)
- [x] Write architecture document (`docs/architecture.md`)

## Phase 2: MCP Tool Server ✅

- [x] Evaluate external MCP servers (duckduckgo-mcp-server, mcp-server-fetch, open-meteo-mcp)
- [x] Decide on single custom FastMCP server over multiple external servers
- [x] `tools/search_web.py` — ddgs web search
- [x] `tools/read_webpage.py` — async httpx + readability, two-tier TLS fallback
- [x] `tools/search_reddit.py` — async Reddit public JSON API + ddgs fallback, travel subreddits
- [x] `tools/search_media.py` — ddgs images + videos
- [x] `tools/calendar_math.py` — hybrid date resolver (parsedatetime → dateparser → calendar)
- [x] `tools/get_climate_data.py` — async Open-Meteo geocoding + forecast + ERA5 archive
- [x] `mcp_server.py` — FastMCP server exposing all 6 tools
- [x] `tests/test_tools.py` — pytest suite (21 tests, primary + fallback paths)
- [x] Write retrospective plan (`docs/mcp_server_plan.md`)

## Phase 3: Agent Orchestrator

- [ ] `travel_agent.py` — core agentic loop
  - [ ] Connect to `mcp_server.py` via streamable-http, fetch tool schemas
  - [ ] Inject current date into system prompt at runtime
  - [ ] Native tool-calling loop (LLM → tools → LLM) until no more tool calls
  - [ ] In-memory session/message history per session
  - [ ] Stream final Markdown response to caller

## Phase 4: API Layer

- [ ] FastAPI app (`main.py`)
  - [ ] `POST /chat` — accepts user message + session_id, returns streamed itinerary
  - [ ] Session management (in-memory, keyed by session_id)
  - [ ] Start MCP server as subprocess on app startup

## Phase 5: Frontend

- [ ] Browser UI
  - [ ] Chat input + message history
  - [ ] Render Markdown itineraries (images, video embeds)
  - [ ] Stateless — sends only latest user input + session_id
