"""
travel_agent.py — Solo Explorer Agent core loop.

Connects to mcp_server.py via stdio, runs a native tool-calling loop
using llm_gatewayV2, and returns a Markdown itinerary string.

SSE event schema (run_stream):
  {"type": "tool_start", "tool": "<name>", "label": "<human label>"}
  {"type": "tool_end",   "tool": "<name>", "label": "<human label>"}
  {"type": "response",   "text": "<markdown>", "history": [...]}
  {"type": "error",      "message": "<msg>"}
  {"type": "done"}
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Literal

_LOG_DIR = Path(__file__).parent / "logs"

from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from client import LLM

_PROMPT_PATH = Path(__file__).parent / "docs" / "draft_prompt.md"
_MCP_SERVER = Path(__file__).parent / "mcp_server.py"
MAX_TURNS = 12
LLM_PROVIDER: str | None = os.getenv("LLM_PROVIDER")  # e.g. "cerebras", "groq", None = auto
MCP_PORT: int = int(os.getenv("MCP_PORT", "8000"))
MCP_SERVER_URL: str = os.getenv("MCP_SERVER_URL", f"http://127.0.0.1:{MCP_PORT}/mcp")

def _tool_label(name: str, args: dict) -> str:
    q = args.get("query", "")
    match name:
        case "search_web_tool":
            return f"Searching the web for '{q}'"
        case "search_reddit_tool":
            return f"Searching Reddit for '{q}'"
        case "search_media_tool":
            kind = args.get("media_type", "image")
            return f"Finding {kind}s for '{q}'"
        case "read_webpage_tool":
            url = args.get("url", "")
            host = url.split("/")[2] if url.count("/") >= 2 else url
            return f"Reading {host}"
        case "calendar_math_tool":
            return f"Resolving date '{q}'"
        case "get_climate_data_tool":
            loc = args.get("location", "")
            month = args.get("month", "")
            return f"Fetching climate for {loc}, {month}"
        case _:
            return name


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ToolDef(BaseModel):
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class TraceEvent(BaseModel):
    kind: Literal["llm_call", "tool_call"]
    turn: int
    provider: str | None = None
    model: str | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read: int | None = None
    cache_create: int | None = None
    tool_name: str | None = None
    tool_args: dict | None = None
    tool_result: str | None = None
    text: str | None = None
    reasoning_text: str | None = None


class AgentTrace(BaseModel):
    goal: str
    events: list[TraceEvent] = Field(default_factory=list)
    started_at: float = Field(default_factory=time.time)

    def add(self, **kw) -> None:
        self.events.append(TraceEvent(**kw))

    def summary(self) -> dict:
        llm_calls = [e for e in self.events if e.kind == "llm_call"]
        tool_calls = [e for e in self.events if e.kind == "tool_call"]
        return {
            "llm_turns": len(llm_calls),
            "tool_calls": len(tool_calls),
            "total_in_tokens": sum(e.input_tokens or 0 for e in llm_calls),
            "total_out_tokens": sum(e.output_tokens or 0 for e in llm_calls),
            "cache_reads": sum(e.cache_read or 0 for e in llm_calls),
            "wall_clock_s": round(time.time() - self.started_at, 2),
        }


# ── Helpers ───────────────────────────────────────────────────────────────────

import re as _re

_STEP_BLOCK_RE = _re.compile(
    r"```[\s\S]*?\[Step 0.*?```|"          # fenced block starting with [Step 0
    r"\[Step \d+:.*?\][\s\S]*?(?=\n\n|\Z)",  # bare [Step N:...] paragraphs
    _re.DOTALL,
)

def _strip_reasoning(text: str) -> str:
    return _STEP_BLOCK_RE.sub("", text).strip()


def _mcp_tool_to_v2(t) -> dict:
    return ToolDef(
        name=t.name,
        description=t.description or "",
        input_schema=t.inputSchema or {"type": "object", "properties": {}},
    ).model_dump()


def _load_system_prompt() -> str:
    base = _PROMPT_PATH.read_text()
    now = datetime.now()
    date_line = (
        f"\n\n---\n**Current date and time:** "
        f"{now.strftime('%A, %B %d, %Y at %H:%M')}. "
        f"Use this as your temporal anchor for all date reasoning. "
        f"\n\n**IMPORTANT:** Your final response (when you have no more tool calls) must contain "
        f"ONLY the Markdown itinerary defined in Section 4. "
        f"No reasoning block, no preamble, no explanation of what you searched."
    )
    return base + date_line


async def _dispatch_tool_calls(
    session: ClientSession,
    tool_calls: list[dict],
    queue: asyncio.Queue | None = None,
) -> list[dict]:
    async def _run_one(tc: dict) -> dict:
        label = _tool_label(tc["name"], tc.get("arguments") or {})
        if queue:
            await queue.put({"type": "tool_start", "tool": tc["name"], "label": label})
        result = await session.call_tool(tc["name"], tc.get("arguments") or {})
        text = result.content[0].text if result.content else ""
        if queue:
            await queue.put({"type": "tool_end", "tool": tc["name"], "label": label})
        return {
            "role": "tool",
            "tool_call_id": tc["id"],
            "tool_name": tc["name"],
            "content": text,
        }

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(_run_one(tc)) for tc in tool_calls]
    return [t.result() for t in tasks]


# ── Agent loop ────────────────────────────────────────────────────────────────

async def _run_native_loop(
    session: ClientSession,
    tools: list[dict],
    messages: list[dict],
    system: str,
    trace: AgentTrace,
    queue: asyncio.Queue | None = None,
) -> str:
    llm = LLM()

    for turn in range(1, MAX_TURNS + 1):
        if queue:
            label = "Crafting your itinerary..." if turn > 1 else "Thinking..."
            await queue.put({"type": "thinking", "label": label})
        reply = llm.chat(
            messages=messages,
            system=system,
            cache_system=True,
            tools=tools,
            tool_choice="auto",
            temperature=0.3,
            max_tokens=8192,
            provider=LLM_PROVIDER,
            reasoning="medium",
        )

        trace.add(
            kind="llm_call",
            turn=turn,
            provider=reply.get("provider"),
            model=reply.get("model"),
            latency_ms=reply.get("latency_ms"),
            input_tokens=reply.get("input_tokens"),
            output_tokens=reply.get("output_tokens"),
            cache_read=reply.get("cache_read_input_tokens"),
            cache_create=reply.get("cache_creation_input_tokens"),
            text=reply.get("text"),
            reasoning_text=reply.get("reasoning_text"),
        )

        if reply.get("reasoning_text") and queue:
            await queue.put({"type": "reasoning", "text": reply["reasoning_text"]})

        tool_calls = reply.get("tool_calls") or []
        if not tool_calls:
            return _strip_reasoning(reply.get("text", ""))

        messages.append({
            "role": "assistant",
            "content": reply.get("text", "") or "",
            "tool_calls": tool_calls,
        })

        results = await _dispatch_tool_calls(session, tool_calls, queue)
        for tc, r in zip(tool_calls, results):
            trace.add(
                kind="tool_call",
                turn=turn,
                tool_name=tc["name"],
                tool_args=tc.get("arguments"),
                tool_result=r["content"],
            )
        messages.extend(results)

    raise RuntimeError(f"agent exceeded MAX_TURNS={MAX_TURNS}")


# ── Core runner (shared by both entrypoints) ──────────────────────────────────

async def _run_core(
    user_message: str,
    history: list[dict],
    queue: asyncio.Queue | None = None,
) -> tuple[str, list[dict]]:
    system = _load_system_prompt()
    messages = history + [{"role": "user", "content": user_message}]

    async with streamable_http_client(MCP_SERVER_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_tools = (await session.list_tools()).tools
            tools = [_mcp_tool_to_v2(t) for t in mcp_tools]
            trace = AgentTrace(goal=user_message)
            response = await _run_native_loop(session, tools, messages, system, trace, queue)

    messages.append({"role": "assistant", "content": response})
    _write_trace(trace)
    return response, messages


def _write_trace(trace: AgentTrace) -> None:
    _LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _LOG_DIR / f"trace_{ts}.json"
    path.write_text(json.dumps(trace.model_dump(), indent=2, default=str))


# ── Public: blocking ──────────────────────────────────────────────────────────

async def run(user_message: str, history: list[dict]) -> tuple[str, list[dict]]:
    """Single-turn agent call. Returns (markdown, updated_history)."""
    return await _run_core(user_message, history)


# ── Public: SSE streaming ─────────────────────────────────────────────────────

async def run_stream(user_message: str, history: list[dict]) -> AsyncIterator[dict]:
    """
    Async generator yielding SSE event dicts.
    Yields tool_start/tool_end during search, then response + done.
    """
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def _agent_task():
        try:
            response, updated_history = await _run_core(user_message, history, queue)
            await queue.put({"type": "response", "text": response, "history": updated_history})
        except Exception as exc:
            # Unwrap ExceptionGroup to surface the real cause
            root = exc
            while hasattr(root, "exceptions") and root.exceptions:
                root = root.exceptions[0]
            await queue.put({"type": "error", "message": f"{type(root).__name__}: {root}"})
        finally:
            await queue.put(None)  # sentinel

    task = asyncio.create_task(_agent_task())

    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event
        yield {"type": "done"}
    finally:
        task.cancel()


# ── CLI for quick testing ─────────────────────────────────────────────────────

async def _cli() -> None:
    print(f"Connecting to MCP server at {MCP_SERVER_URL}")
    print("Solo Explorer Agent — type 'quit' to exit\n")
    history: list[dict] = []
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break
        if not user_input:
            continue
        print()
        async for event in run_stream(user_input, history):
            if event["type"] == "thinking":
                print(f"  💭 {event['label']}")
            elif event["type"] == "reasoning":
                print(f"\n  🧠 Reasoning:\n{event['text']}\n")
            elif event["type"] == "tool_start":
                print(f"  ⚙  {event['label']}...")
            elif event["type"] == "response":
                history = event["history"]
                print(f"\n{event['text']}\n")
            elif event["type"] == "error":
                print(f"  ✗  Error: {event['message']}")


if __name__ == "__main__":
    asyncio.run(_cli())
