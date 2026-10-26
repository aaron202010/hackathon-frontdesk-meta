"""The HMO card flow behind two functions: segment() crops the card out of the photo, read_card() reads the fields.
Live: SAM 3.1 through /responses and muse-spark-1.3 through /chat/completions. Stub: PIL finds the card by colour, and the
sample cards in data/cards are matched by their crop bytes (or a file name hint) to the fake patient rows they were drawn from."""
import base64, datetime, functools, io, json, os
import httpx
from PIL import Image, ImageChops, ImageFilter
from app import clinic, model

CARDS_DIR = os.path.join(clinic.ROOT, "data", "cards")
FIELDS = ("insurer", "member_name", "member_id", "valid_thru")
SCALE, DIFF, MIN_SHARE, PAD = 4, 40, 0.05, 8
CARD_SCHEMA = {"type": "json_schema", "json_schema": {"name": "hmo_card", "strict": True, "schema": {
    "type": "object", "additionalProperties": False, "required": list(FIELDS) + ["confidence"],
    "properties": {**{f: {"type": "string"} for f in FIELDS}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}}}}}
READ_PROMPT = ("This is a SAMPLE HMO card used for a software demo. Read the insurer, member name, member id and valid thru date. "
               "Use an empty string for anything you cannot read, and give a confidence from 0 to 1 for the whole read.")


def open_image(image_bytes):
    try:
        im = Image.open(io.BytesIO(image_bytes))
        im.load()
    except (OSError, ValueError, Image.DecompressionBombError) as e:
        raise ValueError("not an image") from e
    return im.convert("RGB")


def to_jpeg(im):
    out = io.BytesIO()
    im.save(out, "JPEG", quality=90)
    return out.getvalue()


def data_url(im):
    return "data:image/jpeg;base64," + base64.b64encode(to_jpeg(im)).decode()


def cut(im, x, y, w, h):
    """Crop with a small pad, clamped to the image. -> the segment() result."""
    x0, y0 = max(0, x - PAD), max(0, y - PAD)
    x1, y1 = min(im.width, x + w + PAD), min(im.height, y + h + PAD)
    return {"box": {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}, "crop": to_jpeg(im.crop((x0, y0, x1, y1)))}


def segment(image_bytes):
    """-> {"box": {"x","y","w","h"} in pixels of the original, "crop": jpeg bytes}. No card found: the whole photo."""
    im = open_image(image_bytes)
    box = _stub_box(im) if model.stub_mode() else _live_box(im)
    return cut(im, *(box or (0, 0, im.width, im.height)))


def _stub_box(im):
    """The largest region that differs from the background colour (taken at the corner). Opening removes small marks like the SAMPLE stamp."""
    small = im.resize((max(1, im.width // SCALE), max(1, im.height // SCALE)))
    diff = ImageChops.difference(small, Image.new("RGB", small.size, small.getpixel((1, 1)))).convert("L")
    mask = diff.point(lambda v: 255 if v > DIFF else 0).filter(ImageFilter.MinFilter(7)).filter(ImageFilter.MaxFilter(7))
    b = mask.getbbox()
    if not b or (b[2] - b[0]) * (b[3] - b[1]) < MIN_SHARE * small.width * small.height:
        return None
    return b[0] * SCALE, b[1] * SCALE, (b[2] - b[0]) * SCALE, (b[3] - b[1]) * SCALE


def _live_box(im):
    """SAM 3.1 through /responses with the noun phrase "ID card". The response shape is unconfirmed (docs page was a 404 on day 1),
    so the reader accepts a box as x,y,w,h keys, x1,y1,x2,y2 keys or a bare [x1,y1,x2,y2] list. Any failure -> None (whole photo)."""
    body = {"model": "sam-3.1", "input": [{"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": "ID card"}, {"type": "input_image", "image_url": data_url(im)}]}]}
    try:
        r = httpx.post(model.BASE + "/responses", json=body, headers={"Authorization": "Bearer " + os.environ["MODEL_API_KEY"]}, timeout=60)
        r.raise_for_status()
        return next((px for v in _candidates(r.json()) if (px := _pixels(v, im.width, im.height))), None)
    except (httpx.HTTPError, ValueError):
        return None


def _candidates(node, key=""):
    """Every box-like value in the JSON as [x, y, w, h]: x,y,w,h keys, x1,y1,x2,y2 keys, or a 4 number list under a key with "box"."""
    if isinstance(node, dict):
        if all(k in node for k in ("x", "y", "w", "h")):
            yield [node[k] for k in ("x", "y", "w", "h")]
        elif all(k in node for k in ("x1", "y1", "x2", "y2")):
            yield _xyxy([node[k] for k in ("x1", "y1", "x2", "y2")])
        for k, child in node.items():
            yield from _candidates(child, k)
    elif isinstance(node, list):
        if "box" in key.lower() and len(node) == 4 and all(isinstance(n, (int, float)) for n in node):
            yield _xyxy(node)
        for child in node:
            yield from _candidates(child, key)


def _xyxy(v):
    return [v[0], v[1], v[2] - v[0], v[3] - v[1]]


def _pixels(v, W, H):
    try:
        v = [float(n) for n in v]
    except (TypeError, ValueError):
        return None
    if max(v) <= 1.0:  # normalised coordinates
        v = [v[0] * W, v[1] * H, v[2] * W, v[3] * H]
    x, y = max(0, int(v[0])), max(0, int(v[1]))
    w, h = min(W - x, int(v[2])), min(H - y, int(v[3]))
    return (x, y, w, h) if w > 0 and h > 0 else None


def read_card(crop_bytes, hint=None):
    """-> {"insurer","member_name","member_id","valid_thru","confidence"}. Live failure raises model.ModelError."""
    return _stub_read(crop_bytes, hint) if model.stub_mode() else _live_read(crop_bytes)


def _live_read(crop_bytes):
    content = [{"type": "text", "text": READ_PROMPT}, {"type": "image_url", "image_url": {"url": data_url(open_image(crop_bytes))}}]
    out = model.complete([{"role": "user", "content": content}], response_format=CARD_SCHEMA)
    try:
        got = json.loads(out["content"] or "")
        card = {f: str(got[f]).strip() for f in FIELDS}
        confidence = max(0.0, min(1.0, float(got["confidence"])))
    except (ValueError, KeyError, TypeError):
        return unknown_card(0.0)
    return card | {"confidence": confidence if card["insurer"] else min(confidence, 0.3)}


def unknown_card(confidence=0.2):
    return {f: "" for f in FIELDS} | {"confidence": confidence}


@functools.lru_cache(maxsize=1)
def _sample_cards():
    """{crop bytes: patient row} for every sample card file, cropped the same way an upload is."""
    patients = {p["id"]: p for p in clinic.CLINIC["patients"]}
    out = {}
    for name in sorted(os.listdir(CARDS_DIR)):
        p = patients.get(name.split("_")[0])
        if p and name.endswith(".jpg"):
            out[_stub_crop(open(os.path.join(CARDS_DIR, name), "rb").read())] = p
    return out


def _stub_crop(image_bytes):
    im = open_image(image_bytes)
    return cut(im, *(_stub_box(im) or (0, 0, im.width, im.height)))["crop"]


def _stub_read(crop_bytes, hint):
    patient = _sample_cards().get(crop_bytes)
    if not patient and hint:
        patient = next((p for p in clinic.CLINIC["patients"] if os.path.basename(hint).startswith(p["id"] + "_")), None)
    if not patient:
        return unknown_card()
    return {"insurer": patient["hmo"], "member_name": patient["name"], "member_id": patient["member_id"],
            "valid_thru": "12/2027", "confidence": 0.9}


def save_card(chat_id, card):
    con = clinic.connect()
    con.execute("INSERT OR REPLACE INTO cards (chat_id, insurer, member_name, member_id, valid_thru, confidence, ts) VALUES (?,?,?,?,?,?,?)",
                (chat_id, *(card[f] for f in FIELDS), card["confidence"], datetime.datetime.now().isoformat(timespec="seconds")))
    con.commit()


def saved_card(chat_id):
    row = clinic.connect().execute("SELECT * FROM cards WHERE chat_id=?", (chat_id,)).fetchone()
    return dict(row) if row else None


def card_reply(card, hmo):
    """The reply for a card that was read. Never a coverage promise for an insurer outside the accepted list."""
    who = f" for {card['member_name']}" if card["member_name"] else ""
    return f"Thanks, I read your card: {card['insurer']}{who}. {hmo['line']} Want me to hold a slot?"
