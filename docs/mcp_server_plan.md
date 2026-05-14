# MCP Tool Server — Implementation Plan (Retrospective)

## Goal

Build a single `FastMCP` server exposing exactly the tools the Solo Explorer Agent needs. The LLM calls one server; all external APIs and fallback logic are hidden behind it.

---

## Scope

6 tools, no more. Each maps to a distinct PRD capability:

| Tool | PRD Requirement |
|------|----------------|
| `search_web_tool` | Event discovery, visa/advisory lookups, logistics |
| `read_webpage_tool` | Deep-reading official sources, visa portals, festival sites |
| `search_reddit_tool` | First-hand safety tips, local laws, nightlife, event reviews |
| `search_media_tool` | Rich media (images + videos) embedded in itinerary output |
| `calendar_math_tool` | Date verification — eliminates hallucination on time-sensitive queries |
| `get_climate_data_tool` | Climate/weather for location-first queries and date validation |

---

## Alternatives Considered and Rejected

### External MCP servers
Evaluated: `duckduckgo-mcp-server`, `mcp-server-fetch`, `open-meteo-mcp`.

Rejected because:
- `mcp-server-fetch` fails silently on server-side TLS errors (e.g., `TLSV1_ALERT_INTERNAL_ERROR`) and has no fallback; also blocked by `robots.txt` on key travel sites.
- `duckduckgo-mcp-server` is a thin wrapper with no added value over calling `ddgs` directly.
- `open-meteo-mcp` exposes 17 tools; we only need 3 of its underlying API calls. Wrapping it hides the complexity from the LLM.
- Multiple external MCP servers → process management overhead, stdio noise on startup, harder to test.

**Decision:** All tool logic in custom Python modules under `tools/`. No external MCP servers at runtime.

### PRAW (Reddit OAuth)
Rejected in favour of Reddit's public JSON API (`reddit.com/r/{subreddits}/search.json`):
- No credentials required, no app registration.
- `restrict_sr=1` limits results to travel subreddits — better signal than global Reddit search.
- PRAW adds a dependency and credential-management burden for no meaningful benefit at this scale.

### `duckduckgo-search` package
Replaced with `ddgs` — correct package name for the maintained fork. Same API surface (`DDGS().text()`, `.images()`, `.videos()`).

---

## Key Design Decisions

### Single FastMCP server
- LLM schema stays clean: 6 tools, clear descriptions.
- Fallback logic is an implementation detail the LLM never sees.
- Simplifies testing: one import, one `mcp.list_tools()` call.

### Async-first for I/O-bound tools
`read_webpage`, `search_reddit`, `get_climate_data` are `async def` with `httpx.AsyncClient`.
- `get_climate_data` historical path fetches 3 archive years concurrently via `asyncio.gather`.
- `search_reddit` DDGS fallback wrapped in `asyncio.to_thread` (DDGS is sync-only).
- `search_web` and `search_media` stay sync — DDGS has no async API and calls are single-shot.

### Fallback chains

**`read_webpage`** (two-tier):
1. `httpx.AsyncClient` standard TLS + `readability-lxml` extraction
2. `httpx.AsyncClient verify=False` — handles expired/self-signed certs
3. Returns explicit error string for unrecoverable server-side TLS; LLM falls back to `search_web` snippets.

**`search_reddit`** (two-tier):
1. Reddit public JSON API — returns post titles, scores, selftext
2. `ddgs.text("site:reddit.com …")` — anonymous fallback when API is unavailable

**`get_climate_data`** (two-path, not fallback):
- Dates within 16 days → Open-Meteo Forecast API
- Dates beyond 16 days → Open-Meteo Archive API, 3 prior years averaged

### `calendar_math` resolution pipeline
`parsedatetime` → `dateparser` → `calendar.monthcalendar()` (ordinal weekday patterns).
LLM must call this tool for any date expression rather than computing dates itself.

---

## File Structure

```
mcp_server.py               # FastMCP server — tool registration only
tools/
  search_web.py             # ddgs.DDGS().text()
  read_webpage.py           # httpx + readability-lxml, two-tier TLS fallback
  search_reddit.py          # Reddit public JSON API + ddgs fallback
  search_media.py           # ddgs.DDGS().images() / .videos()
  calendar_math.py          # hybrid date resolver
  get_climate_data.py       # Open-Meteo geocoding + forecast + archive
tests/
  test_tools.py             # pytest suite, 21 tests, asyncio_mode=auto
```

---

## Testing Strategy

- **Primary paths**: all 6 tools tested against live APIs.
- **Fallback paths**: `read_webpage` expired-cert (badssl.com), `search_reddit` DDGS fallback (mock `httpx.AsyncClient` with `ConnectError`), `read_webpage` unrecoverable TLS (visitshetland.com).
- **Edge cases**: `calendar_math` unresolvable query, `get_climate_data` bad location (geocode failure).
- **MCP registration**: `mcp.list_tools()` asserts all 6 tools present with non-empty descriptions.
- Dynamic dates computed at test runtime (`datetime.now()`) — no hardcoded "tomorrow" strings.

Run: `uv run pytest`
