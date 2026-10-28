"""FastAPI entry: POST /chat, POST /card, POST /voice, GET /trace/{chat_id}, GET / (the chat page)."""
import os, time
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from app import agent, card, clinic, model, voice

app = FastAPI(title="Front Desk on Meta models")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_PHOTO = 10 * 1024 * 1024
BLURRY_LINE = "Please send a clearer photo of the card, flat, in good light, or our staff can check it."
MIN_CONFIDENCE = 0.5
MAX_AUDIO = 10 * 1024 * 1024
NOT_HEARD_LINE = "Sorry, I couldn't hear that. Please send the voice note again or type your message."


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


@app.post("/voice")
def voice_note(file: UploadFile = File(...), chat_id: str = Form(min_length=1, max_length=64)):
    """Voice note in: Meta's speech to text, then the same turn as a typed message (same screen, tools and steps)."""
    data = file.file.read(MAX_AUDIO + 1)
    if len(data) > MAX_AUDIO:
        raise HTTPException(413, "voice note too large")
    if agent.is_paused(chat_id):
        return {"transcript": "", "reply": clinic.CLINIC["guardrails"]["paused_reply"], "screen": "paused", "steps": []}
    t0 = time.time()
    try:
        model.CURRENT_CHAT.set(chat_id)
        text = voice.transcribe(data, hint=file.filename)
    except ValueError:
        raise HTTPException(400, "not audio")
    except model.ModelError:
        return {"transcript": "", "reply": clinic.CLINIC["guardrails"]["model_error_reply"], "screen": "error", "steps": []}
    heard = {"label": f"{voice.ASR_MODEL} transcribed the voice note", "detail": text[:160], "ms": int((time.time() - t0) * 1000)}
    if not text:
        return {"transcript": "", "reply": NOT_HEARD_LINE, "screen": "ok", "steps": [heard]}
    out = agent.handle(chat_id, text[:2000])
    return {"transcript": text, **out, "steps": [heard] + out.get("steps", [])}


@app.get("/trace/{chat_id}")
def trace(chat_id: str):
    if len(chat_id) > 64:
        raise HTTPException(400, "chat_id too long")
    rows = clinic.connect().execute("SELECT role, content, screen, ms, ts FROM turns WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()
    return {"chat_id": chat_id, "paused": agent.is_paused(chat_id), "turns": [dict(r) for r in rows]}
