"""FastAPI entry: POST /chat, POST /card, GET /trace/{chat_id}, GET / (the chat page)."""
import os, time
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app import agent, card, clinic, model

app = FastAPI(title="Front Desk on Meta models")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_PHOTO = 10 * 1024 * 1024
BLURRY_LINE = "Please send a clearer photo of the card, flat, in good light, or our staff can check it."
MIN_CONFIDENCE = 0.5


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
def card_photo(file: UploadFile = File(...), chat_id: str = Form(min_length=1, max_length=64)):
    """Photo in: segment, read, check the insurer against the accepted list, keep the card on the chat for the next booking."""
    data = file.file.read(MAX_PHOTO + 1)
    if len(data) > MAX_PHOTO:
        raise HTTPException(413, "photo too large")
    if agent.is_paused(chat_id):
        return {"reply": clinic.CLINIC["guardrails"]["paused_reply"], "card": None, "hmo": None}
    steps = []
    try:
        model.CURRENT_CHAT.set(chat_id)
        t0 = time.time()
        found = card.segment(data)
        agent.step(steps, "SAM 3.1 found the card in the photo" if found.get("box") else "Card not found, using the whole photo", "", int((time.time() - t0) * 1000))
        t0 = time.time()
        fields = card.read_card(found["crop"], hint=file.filename)
        agent.step(steps, f"{model.model_id()} read the card fields", f"insurer {fields.get('insurer')}, confidence {fields.get('confidence')}", int((time.time() - t0) * 1000))
    except ValueError:
        raise HTTPException(400, "not an image")
    except model.ModelError:
        return {"reply": clinic.CLINIC["guardrails"]["model_error_reply"], "card": None, "hmo": None}
    hmo, box = None, found.get("box")
    if fields["confidence"] < MIN_CONFIDENCE:
        agent.step(steps, "Card too unclear to trust: asked for a clearer photo")
        reply = BLURRY_LINE
    else:
        hmo = clinic.hmo_check(fields["insurer"], None)
        agent.step(steps, "Checked HMO coverage", hmo.get("line", ""))
        card.save_card(chat_id, fields)
        reply = card.card_reply(fields, hmo)
    agent.save_turn(chat_id, "user", "[sent a photo of an HMO card]", "card")
    agent.save_turn(chat_id, "assistant", reply, "card")
    return {"reply": reply, "card": fields, "hmo": hmo, "box": box, "steps": steps}


@app.get("/trace/{chat_id}")
def trace(chat_id: str):
    if len(chat_id) > 64:
        raise HTTPException(400, "chat_id too long")
    rows = clinic.connect().execute("SELECT role, content, screen, ms, ts FROM turns WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()
    return {"chat_id": chat_id, "paused": agent.is_paused(chat_id), "turns": [dict(r) for r in rows]}
