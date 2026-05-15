# ZAI: Zen Adventure Intelligence 🦜

An agentic AI travel planner that researches, reasons, and builds fully personalized travel itineraries — using live web data, Reddit, climate APIs, and rich media.

## Watch demo on YouTube

[![ZAI Demo](https://i.ytimg.com/vi/2XzlGg0mgog/maxresdefault.jpg)](https://youtu.be/zm0W2Hm5zY4)

---

## What It Does

ZAI is not a chatbot that answers travel questions from memory. It is an autonomous agent that:

- Searches the live web for events, logistics, and destination intel
- Digs into Reddit for first-hand traveler experiences and insider tips
- Fetches real climate data for your travel dates
- Verifies event dates before recommending them
- Assesses safety conditions, local laws, and visa requirements
- Surfaces curated images and a travel video for every itinerary
- Streams its entire reasoning process to the UI in real time

Every itinerary is generated fresh from live data — no templates, no cached responses.

---

## Demo

> **Prompt:** *"I want to travel somewhere in December."*

ZAI classifies the query, resolves the date range, plans parallel searches across web, Reddit, and climate APIs, fires all tool calls simultaneously, synthesizes results, and returns a structured Markdown itinerary — with images, an embedded YouTube video, safety briefings, visa notes, and a day-by-day plan.

---

## Architecture

```
User → FastAPI (main.py)
          │
          ├── SSE stream (tool progress events)
          │
          └── travel_agent.py (agentic loop)
                    │
                    ├── LLM Gateway (client.py)
                    │
                    └── MCP Tool Server (mcp_server.py)
                              │
                              ├── search_web        → DuckDuckGo
                              ├── read_webpage      → httpx + readability
                              ├── search_reddit     → Reddit public API / DDG fallback
                              ├── search_media      → images + YouTube
                              ├── get_climate_data  → Open-Meteo (forecast + ERA5)
                              └── calendar_math     → date resolution pipeline
```

### Key Design Decisions

- **Parallel tool execution** — `asyncio.TaskGroup` fires independent tool calls simultaneously; `tool_start` events stream to the UI before results return
- **Fallback chains** — every tool has a degradation path; the agent never hard-crashes on a failed search
- **Date grounding** — the LLM is explicitly prohibited from computing dates itself; it must call `calendar_math_tool` for all temporal expressions
- **No LLM token streaming** — SSE progress comes from tool events, not token streaming; LLM calls are blocking and cheap
- **MCP registration** — tools are registered on the FastMCP server and fetched by the agent at startup via `streamable_http_client`

---

## Tools

| Tool | What it does |
|------|-------------|
| `search_web` | DuckDuckGo web search |
| `read_webpage` | Extracts clean text from any URL (readability + BS4) |
| `search_reddit` | Searches travel subreddits for first-hand experiences |
| `search_media` | Returns images and YouTube videos for a destination |
| `get_climate_data` | Open-Meteo Forecast API (≤16 days) or ERA5 archive (historical averages) |
| `calendar_math` | Resolves fuzzy date expressions to concrete ranges |

---

## SSE Event Schema

The `/chat/stream` endpoint emits server-sent events. Clients must handle all types:

| `type` | Fields | When |
|--------|--------|------|
| `session` | `session_id` | First event — carry forward for multi-turn |
| `thinking` | `label` | Before each LLM call |
| `tool_start` | `tool`, `label` | When a tool call begins |
| `tool_end` | `tool`, `label` | When a tool call completes |
| `response` | `text` | Final Markdown itinerary |
| `error` | `message` | Agent-level exception |
| `done` | — | Stream complete |

---

## Setup

### Requirements

- Python 3.14+
- [`uv`](https://github.com/astral-sh/uv)
- An LLM gateway running at `http://localhost:8100` (or override via env)

### Install

```bash
git clone https://github.com/your-username/zai
cd zai
uv sync
```

### Environment

Create `.env` at the repo root:

```env
LLM_GATEWAY_V2_URL=http://localhost:8100   # LLM gateway endpoint
LLM_PROVIDER=cerebras                      # or groq, or omit for auto-select
MCP_SERVER_URL=http://127.0.0.1:8000/mcp  # optional override
MCP_PORT=8000                              # optional override
REDDIT_CLIENT_ID=                          # optional — enables full post content
REDDIT_CLIENT_SECRET=                      # optional — enables full post content
```

### Run

Start both servers (two terminals):

```bash
# Terminal 1 — MCP tool server
uv run python mcp_server.py

# Terminal 2 — API + UI server
uv run python main.py
```

Open `http://localhost:8080` in your browser.

### CLI Mode

```bash
uv run python travel_agent.py
```

---

## API

### `POST /chat/stream`

SSE stream. Send a JSON body:

```json
{
  "message": "Plan 10 days in Japan in October — I love hiking and street food.",
  "session_id": "optional-for-multi-turn"
}
```

### `POST /chat`

Non-streaming JSON fallback. Same request body, returns `{ "response": "..." }`.

### `GET /health`

Returns `{ "status": "ok" }`.

---

## Testing

```bash
# Run all 21 tests
uv run pytest

# Run a specific test class
uv run pytest tests/test_tools.py::TestCalendarMath

# Run a single test
uv run pytest tests/test_tools.py::TestCalendarMath::test_tomorrow
```

Tests cover primary paths, fallback chains, and MCP tool registration. All tests run against live APIs — no mocking.

---

## Project Structure

```
zai/
├── main.py              # FastAPI server (port 8080)
├── travel_agent.py      # Core agentic loop (MAX_TURNS = 12)
├── mcp_server.py        # FastMCP tool registration
├── client.py            # LLM gateway client
├── prompt.md            # System prompt
├── tools/
│   ├── search_web.py
│   ├── read_webpage.py
│   ├── search_reddit.py
│   ├── search_media.py
│   ├── get_climate_data.py
│   └── calendar_math.py
├── static/
│   └── index.html       # Single-file chat UI
├── tests/
│   └── test_tools.py
└── docs/
    ├── PRD.md
    └── architecture.md
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | Custom agentic loop + [FastMCP](https://github.com/jlowin/fastmcp) |
| API server | [FastAPI](https://fastapi.tiangolo.com/) |
| LLM | Configurable via gateway (Cerebras / Groq / any OpenAI-compatible) |
| Web search | [ddgs](https://github.com/deedy5/ddgs) (DuckDuckGo) |
| Webpage extraction | [readability-lxml](https://github.com/buriy/python-readability) + [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) |
| Climate data | [Open-Meteo](https://open-meteo.com/) (no API key required) |
| Date parsing | [parsedatetime](https://github.com/bear/parsedatetime) + [dateparser](https://github.com/scrapinghub/dateparser) |
| HTTP client | [httpx](https://www.python-httpx.org/) |
| Package manager | [uv](https://github.com/astral-sh/uv) |

---

## Agent Behavior

ZAI follows a strict reasoning protocol on every turn:

1. **Turn classification** — new request, refinement, or clarification answer
2. **Input analysis** — city, country/region, timeframe, or combination
3. **Planning** — what to search, what to verify
4. **Self-check** — resolve fuzzy dates, verify event dates before recommending
5. **Safety assessment** — advisories, local laws, solo female safety if applicable
6. **Tool execution** — parallel searches across all relevant sources
7. **Synthesis** — structured Markdown itinerary with media, safety, logistics, and day-by-day plan

For country/region queries, ZAI builds a multi-city route (2–4 stops in geographic order) rather than picking one city. For timeframe-only queries, ZAI returns 3 destination options — at least 1 domestic, at least 2 international across different regions — and waits for the user to choose before generating the full itinerary.

---

## Limitations

- Requires an external LLM gateway — no built-in model
- Reddit search is restricted to travel subreddits; general Reddit not supported
- Agent traces are stored locally in `logs/` with no rotation policy
- No persistent memory across sessions (in-memory session store only)
