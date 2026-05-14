"""
main.py — Solo Explorer Agent API.

POST /chat/stream  { "message": "...", "session_id": "..." }  → SSE
POST /chat         { "message": "...", "session_id": "..." }  → JSON (fallback)
GET  /health
"""

import json
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import travel_agent

_sessions: dict[str, list[dict]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    _sessions.clear()


app = FastAPI(title="Solo Explorer Agent", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    session_id = req.session_id or str(uuid.uuid4())
    history = _sessions.get(session_id, [])

    async def event_generator():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        async for event in travel_agent.run_stream(req.message, history):
            if event.get("type") == "response":
                _sessions[session_id] = event.get("history", history)
                # strip history from SSE payload — too large
                yield f"data: {json.dumps({'type': 'response', 'text': event['text']})}\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="message cannot be empty")

    session_id = req.session_id or str(uuid.uuid4())
    history = _sessions.get(session_id, [])

    response, updated_history = await travel_agent.run(req.message, history)
    _sessions[session_id] = updated_history

    return ChatResponse(response=response, session_id=session_id)


@app.get("/health")
async def health():
    return {"status": "ok"}
