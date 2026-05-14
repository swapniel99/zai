# Technical Architecture: Solo Explorer Agent

This document outlines the technical blueprint and data flow for the Solo Explorer Agent. The architecture is designed to cleanly separate the user interface, the agent orchestration loop, the tool execution environment, and the LLM routing layer.

---

## 1. System Overview

The system consists of four primary components:

1. **Browser Frontend**: A lightweight web interface where users interact with the travel agent. It handles rendering the rich markdown responses (including images/videos) and managing the user input field.
2. **Agent Orchestrator (Python)**: The core backend service (`travel_agent.py`). It manages the in-memory session state, routes requests to the LLM Gateway, and orchestrates tool execution.
3. **MCP Tool Server (Python)**: A standalone `FastMCP` server (`mcp_server.py`) that executes local Python tools (like web searching and scraping) on behalf of the agent.
4. **LLM Gateway (V2)**: The centralized routing layer that handles API keys, rate limits, caching, and native tool-calling schemas for multiple LLM providers.

### High-Level Data Flow
`User -> Agent -> [LLM Gateway <-> Agent <-> MCP Server]* (Loop) -> Agent -> User`

---

## 2. State Management

For version 1, we will use an **In-Memory Session**.

* **Where is history held?** The chat history (the `messages` array containing system prompts, user queries, assistant responses, and native tool outputs) is maintained in the **Agent Orchestrator (Backend)**.
* **Why this is best practice:** Keeping the context window in the backend ensures the frontend remains stateless and lightweight. It prevents the client from manipulating the system prompt or tool outputs, and reduces the payload size over the network. The browser only sends the latest user input and receives the final itinerary response.
* **Future Iterations:** In later versions, this in-memory list will be swapped for a persistent database (e.g., Redis or PostgreSQL) keyed by a `session_id`.

---

## 3. The Execution Loop

The agent utilizes a structured native tool-calling loop modeled after the `llm_gatewayV2` architecture:

1. **Initialization:** The Agent connects to the local MCP Server via `streamable-http` and fetches the JSON schemas for the available tools.
2. **LLM Request (Planning):** The Agent constructs the system prompt, injecting the current date/time (e.g., `"Today is Thursday, May 14, 2026"`) at runtime so the LLM has an accurate temporal anchor for reasoning before any tool calls. The Agent then sends the user query to the LLM Gateway. The LLM outputs its `<reasoning>` and emits native JSON tool calls.
3. **Tool Execution:** The Agent Orchestrator catches these calls, dispatches them to the MCP Server, and appends the **tool results** back to the `messages` history.
4. **LLM Re-invocation (Loop):** The Agent sends the updated `messages` (now including the tool results) back to the LLM Gateway. (Steps 2-4 repeat as many times as the LLM requests tools).
5. **Finalization:** Once the LLM decides it has enough information, it generates the final Markdown itinerary. The Agent then logs the `AgentTrace` and streams the response to the browser.

*(Note: There is no independent LLM "Verifier" step. The strict 5-step reasoning instructions in the system prompt handle validation natively).*

---

## 4. MCP Tool Specifications

The agent talks to a **single** `FastMCP` server (`mcp_server.py`) exposing exactly 6 tools. All tool logic is implemented as custom Python modules under `tools/` — no external MCP servers are required at runtime.

---

### 1. `search_web(query: str, max_results: int = 5) -> str`
* **Backend:** Custom `tools/search_web.py` — wraps `ddgs.DDGS().text()` (free, no API key, multi-backend metasearch via Bing/Brave/Google/DuckDuckGo).
* **Purpose:** Queries the web for event dates, travel logistics, visa requirements, safety advisories, and general destination research. Returns ranked URL snippets with summaries.

### 2. `read_webpage(url: str) -> str` *(async)*
* **Backend:** Custom `tools/read_webpage.py` — two-tier fallback chain:
  1. `httpx.AsyncClient` + `readability-lxml` + `BeautifulSoup` (standard TLS)
  2. `httpx.AsyncClient verify=False` (expired/self-signed certs)
  Returns a clear error message if the site has an unrecoverable server-side TLS failure (e.g., `TLSV1_ALERT_INTERNAL_ERROR`), prompting the LLM to fall back to `search_web` snippets.
* **Purpose:** Extracts full body text from a URL. Used to deeply investigate official government advisories, visa portals, festival schedules, and travel forums that `search_web` only returns snippets for.

### 3. `search_reddit(query: str, max_results: int = 5) -> str` *(async)*
* **Backend:** Custom `tools/search_reddit.py` — two-tier fallback chain restricted to travel subreddits (`solotravel`, `travel`, `TravelHacks`, `digitalnomad`, `backpacking`, `shoestring`, `longtermtravel`):
  1. Reddit public JSON API (`reddit.com/r/{subreddits}/search.json`) — no credentials required, returns post titles, scores, and selftext
  2. `ddgs.DDGS().text()` with `site:reddit.com` operator (fallback when Reddit API is unavailable)
* **Purpose:** Finds authentic solo-traveler safety tips, local substance laws, nightlife recommendations, and first-hand event reviews.

### 4. `search_media(query: str, media_type: str = "image") -> str`
* **Backend:** Custom `tools/search_media.py` — `ddgs.DDGS().images()` for photos, `ddgs.DDGS().videos()` for clips (YouTube-preferenced URLs).
* **Purpose:** Fetches direct URLs to images or embeddable video links for the destination or event. The LLM embeds these into the final Markdown itinerary for the browser frontend to render.

### 5. `calendar_math(query: str) -> str`
* **Backend:** Custom `tools/calendar_math.py` — hybrid resolution pipeline: `parsedatetime` (relative/offset expressions) → `dateparser` (absolute/multilingual) → `calendar.monthcalendar()` (ordinal patterns like "last Sunday of December"). Uses `datetime.now()` as the temporal anchor.
* **Purpose:** Resolves dates mathematically, eliminating LLM hallucination risk for time-sensitive itineraries (e.g., "the last Tuesday of January 2027", "14 days from today").

### 6. `get_climate_data(location: str, month: str) -> str` *(async)*
* **Backend:** Custom `tools/get_climate_data.py` — calls Open-Meteo APIs directly via `httpx.AsyncClient` (free, no API key):
  - Geocoding API — resolves location name to lat/lon
  - Forecast API (`api.open-meteo.com`) — 16-day forecast for near-term dates
  - Archive API (`archive-api.open-meteo.com`) — ERA5 historical data; fetches 3 prior years concurrently via `asyncio.gather` and averages the results for future month queries
* **Purpose:** Returns temperature range and precipitation for a location and month. Eliminates reliance on LLM training data for climate questions.
