"""FastAPI entry: POST /chat, POST /card, POST /voice, GET /trace/{chat_id}, GET / (the chat page), GET /staff and /staff/data (read only, behind a key)."""
import collections, os, threading, time
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from app import agent, card, clinic, model, staff, voice

app = FastAPI(title="Front Desk on Meta models")
STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
MAX_PHOTO = 10 * 1024 * 1024
BLURRY_LINE = "Please send a clearer photo of the card, flat, in good light, or our staff can check it."
MIN_CONFIDENCE = 0.5
MAX_AUDIO = 10 * 1024 * 1024
NOT_HEARD_LINE = "Sorry, I couldn't hear that. Please send the voice note again or type your message."


# A cap per visitor on the calls that spend model credits (2026-10-28: the demo is public until judging on Nov 9 and the
# gallery vote on Nov 16). FRONTDESK_RATE calls per 10 minutes per client IP; 0 turns it off. Off in stub mode unless set.
RATE_WINDOW = 600
BUSY_LINE = "Lots of messages from you in a short time. Please wait a few minutes, or call the clinic."
_hits, _hits_lock = collections.defaultdict(collections.deque), threading.Lock()


def rate_limit(request: Request):
    default = 0 if model.stub_mode() else 40
    try:
        limit = int(os.environ.get("FRONTDESK_RATE", default) or 0)
    except ValueError:
        limit = default
    if limit <= 0:
        return
    ip, now = (request.client.host if request.client else "unknown"), time.time()
    with _hits_lock:
        q = _hits[ip]
        while q and q[0] < now - RATE_WINDOW:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, detail=BUSY_LINE)
        q.append(now)


class ChatIn(BaseModel):
    chat_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=2000)


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.post("/chat", dependencies=[Depends(rate_limit)])
def chat(body: ChatIn):
    return agent.handle(body.chat_id, body.text)


@app.post("/card", dependencies=[Depends(rate_limit)])
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


@app.post("/voice", dependencies=[Depends(rate_limit)])
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
        agent.save_turn(chat_id, "user", "[sent a voice note, nothing heard]", "voice")
        agent.save_turn(chat_id, "assistant", NOT_HEARD_LINE, "voice")
        return {"transcript": "", "reply": NOT_HEARD_LINE, "screen": "ok", "steps": [heard]}
    out = agent.handle(chat_id, text[:2000])
    return {"transcript": text, **out, "steps": [heard] + out.get("steps", [])}


@app.get("/trace/{chat_id}")
def trace(chat_id: str, key: str = ""):
    no = staff.denied(key)
    if no:
        return no
    if len(chat_id) > 64:
        raise HTTPException(400, "chat_id too long")
    rows = clinic.connect().execute("SELECT role, content, screen, ms, ts FROM turns WHERE chat_id=? ORDER BY id", (chat_id,)).fetchall()
    return {"chat_id": chat_id, "paused": agent.is_paused(chat_id), "turns": [dict(r) for r in rows]}


@app.get("/staff")
def staff_page(key: str = ""):
    no = staff.denied(key)
    if no:
        return no
    return FileResponse(os.path.join(STATIC, "staff.html"), headers=staff.PRIVATE)


@app.get("/staff/data")
def staff_data(key: str = ""):
    no = staff.denied(key)
    if no:
        return no
    return JSONResponse(staff.snapshot(), headers=staff.PRIVATE)
