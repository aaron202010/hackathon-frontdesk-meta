"""FastAPI entry: POST /chat, POST /card (day 4), GET /trace/{chat_id}, GET / (the chat page)."""
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app import agent, clinic

app = FastAPI(title="Front Desk on Meta models")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class ChatIn(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=2000)


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.post("/chat")
def chat(body: ChatIn):
    return agent.handle(body.chat_id, body.text)


@app.post("/card")
def card():
    return {"status": "not built yet, day 4"}


@app.get("/trace/{chat_id}")
def trace(chat_id: str):
    if len(chat_id) > 64:
        raise HTTPException(400, "chat_id too long")
    rows = clinic.connect().execute("SELECT role, content, screen, ms, ts FROM turns WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()
    return {"chat_id": chat_id, "paused": agent.is_paused(chat_id), "turns": [dict(r) for r in rows]}
