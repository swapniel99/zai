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

## Phase 3: Agent Orchestrator ✅

- [x] `travel_agent.py` — core agentic loop
  - [x] Spawn `mcp_server.py` as stdio subprocess, fetch tool schemas
  - [x] Inject `datetime.now()` + no-reasoning instruction into system prompt at runtime
  - [x] Native tool-calling loop (LLM → tools → LLM) via `llm_gatewayV2`, `asyncio.TaskGroup` parallel dispatch
  - [x] `AgentTrace` (Pydantic) for structured event logging
  - [x] `run()` — blocking, returns `(markdown, updated_history)`
  - [x] `run_stream()` — async generator yielding SSE events: `thinking` / `tool_start` / `tool_end` / `response` / `error` / `done`
  - [x] `_tool_label()` — informative labels from tool name + args (e.g. "Searching Reddit for 'solo travel Japan'")
  - [x] CLI entrypoint with live progress output

## Phase 4: API Layer ✅

- [x] FastAPI app (`main.py`)
  - [x] `POST /chat/stream` — SSE stream of progress events + final Markdown
  - [x] `POST /chat` — JSON fallback (blocking)
  - [x] `GET /health`
  - [x] In-memory sessions keyed by `session_id` (auto-generated if omitted)
  - [x] `load_dotenv()` on startup; `LLM_GATEWAY_V2_URL` configures gateway

## Phase 5: Frontend

- [ ] Browser UI
  - [ ] Connect to `POST /chat/stream` SSE
  - [ ] Show live progress: thinking + tool activity feed
  - [ ] Render final Markdown itinerary (images, video embeds)
  - [ ] Stateless — sends only latest user input + session_id
