"""The one model call. Live: Meta Model API (OpenAI compatible chat completions). Stub: rule answers so the app and tests run
with no network. Every call writes one trace line to logs/trace.jsonl."""
import contextvars, datetime, json, os, re, time
import httpx
from app import clinic
from app.guard import is_taglish, G

BASE = os.environ.get("MODEL_API_BASE", "https://api.meta.ai/v1")
CURRENT_CHAT = contextvars.ContextVar("chat_id", default=None)
TRACE = os.path.join(clinic.ROOT, "logs", "trace.jsonl")
SERVICE_WORDS = {"consult": ["consult", "konsulta", "check up", "checkup"], "cleaning": ["cleaning", "linis", "prophylaxis"],
                 "filling": ["filling", "pasta"], "extraction": ["extraction", "bunot"], "xray": ["x-ray", "xray"],
                 "whitening": ["whitening", "pampaputi"], "braces_adjust": ["adjust"], "rct": ["root canal"]}


class ModelError(Exception):
    pass


def stub_mode():
    return os.environ.get("FRONTDESK_STUB") == "1" or not os.environ.get("MODEL_API_KEY")


def model_id():
    return os.environ.get("FRONTDESK_MODEL", "muse-spark-1.3")


def complete(messages, tools=None, response_format=None):
    """Returns {"content", "tool_calls": [{"id", "name", "arguments"}], "mode", "ms", "usage"}."""
    t0 = time.time()
    mode = "stub" if stub_mode() else "live"
    try:
        out = _stub(messages, tools) if mode == "stub" else _live(messages, tools, response_format)
    finally:
        ms = int((time.time() - t0) * 1000)
    out.update({"mode": mode, "ms": ms})
    _trace(out)
    return out


def _trace(out):
    os.makedirs(os.path.dirname(TRACE), exist_ok=True)
    line = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "chat_id": CURRENT_CHAT.get(), "ms": out["ms"],
            "model": model_id() if out["mode"] == "live" else "stub", "mode": out["mode"],
            "tokens": out.get("usage"), "tool_calls": [c["name"] for c in out["tool_calls"]]}
    with open(TRACE, "a") as f:
        f.write(json.dumps(line) + "\n")


def _live(messages, tools, response_format):
    body = {"model": model_id(), "messages": messages, "temperature": 0.3, "max_tokens": 400}
    if tools:
        body.update(tools=tools, tool_choice="auto")
    if response_format:
        body["response_format"] = response_format
    headers = {"Authorization": "Bearer " + os.environ["MODEL_API_KEY"]}
    try:
        r = httpx.post(BASE + "/chat/completions", json=body, headers=headers, timeout=60)
        r.raise_for_status()
        msg = r.json()["choices"][0]["message"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise ModelError(str(e)[:200]) from e
    calls = [{"id": c.get("id", ""), "name": c["function"]["name"], "arguments": json.loads(c["function"]["arguments"] or "{}")}
             for c in msg.get("tool_calls") or []]
    return {"content": msg.get("content"), "tool_calls": calls, "usage": r.json().get("usage")}


# ---- stub: rule answers, same tool protocol as the live model ----

def _stub(messages, tools):
    user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    if messages[-1]["role"] == "tool":
        return _stub_from_tools(messages, user)
    calls, text = _stub_intent(user.lower(), user, messages)
    if calls:
        return {"content": None, "tool_calls": [{"id": f"stub-{i}", "name": n, "arguments": a} for i, (n, a) in enumerate(calls)], "usage": None}
    return {"content": text, "tool_calls": [], "usage": None}


def _stub_from_tools(messages, user):
    results, names = [], []
    for m in reversed(messages):
        if m["role"] != "tool":
            break
        results.insert(0, m["content"])
        names.insert(0, m.get("name", ""))
    text = " ".join(results)
    if "book" not in names:
        text += " Gusto mo bang mag book? Sabihin mo lang ang pangalan, number at oras." if is_taglish(user) else \
            " Want me to hold a slot? Send your name, mobile number and the time."
    return {"content": text, "tool_calls": [], "usage": None}


def _service_in(t):
    return next((sid for sid, words in SERVICE_WORDS.items() if any(w in t for w in words)), None)


def _date_hint(t):
    m = re.search(r"\d{4}-\d{2}-\d{2}", t)
    if m:
        return m.group(0)
    dates = [d["date"] for d in clinic.SCHEDULE["days"] if d["hours"] != "closed"]
    today = datetime.date.today()
    if "bukas" in t or "tomorrow" in t:
        d = (today + datetime.timedelta(days=1)).isoformat()
        return d if d in dates else dates[0]
    if "today" in t or "ngayon" in t:
        return today.isoformat() if today.isoformat() in dates else dates[0]
    for key in list(clinic.DAY_NAMES) + list(clinic.TAGALOG_DAYS):
        if re.search(rf"\b{key}", t):
            k = clinic.day_key(key)
            return next((d["date"] for d in clinic.SCHEDULE["days"] if d["day"] == k), None)
    return None


def _period(t):
    if any(w in t for w in ("umaga", "morning", " am")):
        return "morning"
    if any(w in t for w in ("hapon", "afternoon", " pm")):
        return "afternoon"
    return None


def _dentist_hint(t):
    return next((d["name"].split()[-1] for d in clinic.CLINIC["clinic"]["dentists"] if d["name"].split()[-1].lower() in t), None)


def _stub_intent(t, raw, messages):
    """-> (tool calls, text). Exactly one of them is filled."""
    if any(w in t for w in ("bookings", "pasyente", "patients", "cancel")):
        return [], G["privacy_reply"]
    if re.search(r"09\d{2}\s?\d{3}\s?\d{4}", t) and re.search(r"\d{1,2}:\d{2}", t):
        return [("book", _booking_args(raw, messages))], None
    if clinic.find_hmo(t) or any(w in t for w in ("hmo", "accepted", "covered")):
        return [("hmo_check", {"name_or_alias": _hmo_name(raw), "service_id": _service_in(t) or "consult"})], None
    if any(w in t for w in ("magkano", "how much", "price", "presyo")):
        sid = _service_in(t)
        return ([("price_line", {"service_id": sid})], None) if sid else ([], clinic.price_line("unknown") + " Gusto mo ng consultation slot?")
    if any(w in t for w in ("open", "hours", "oras", "sarado", "closed")) and not any(w in t for w in ("book", "slot")):
        return [], clinic.hours_line(_date_hint(t) or "")
    if any(w in t for w in ("book", "slot", "schedule", "available", "appointment", "pwede")):
        return [("open_slots", {"date": _date_hint(t), "dentist": _dentist_hint(t), "period": _period(t)})], None
    if any(w in t for w in ("picture", "photo", "card", "blurry")):
        return [], "Please send a clear photo of your HMO card: flat, good light, all four corners in. Or tell me the insurer name. Staff can also help."
    if any(w in t for w in ("hi", "hello", "kumusta", "good morning")) and len(t.split()) <= 4:
        return [], "Hello po! Bright Smile Dental Clinic here. I can help with prices, hours, HMO cards and bookings. Ano po ang kailangan ninyo?"
    return [], G["off_topic_reply"]


def _hmo_name(raw):
    h = clinic.find_hmo(raw.lower())
    if h:
        return h["insurer"]
    m = re.search(r"([A-Za-z]+)\s+HMO", raw)
    return (m.group(1) + " HMO") if m else raw


def _booking_args(raw, messages):
    t = raw.lower()
    mob = re.search(r"(09\d{2})\s?(\d{3})\s?(\d{4})", raw)
    mobile = " ".join(mob.groups())
    tm = re.search(r"\b(\d{1,2}):(\d{2})\b", raw)
    time_ = f"{int(tm.group(1)):02d}:{tm.group(2)}"
    parts = [p.strip() for p in raw.split(",")]
    name = next((parts[i - 1] for i, p in enumerate(parts) if mob.group(0) in p and i > 0), "Patient")
    date = _date_hint(t) or _date_from_history(messages, time_)
    dentist = clinic.dentist_id_for(_dentist_hint(t))
    if not date or not dentist:
        slot = _slot_at(time_, date, dentist)
        if slot:
            date, dentist = slot["date"], slot["dentist"]
    hmo = None if "cash" in t else (clinic.find_hmo(t) or {}).get("insurer") or (_hmo_name(raw) if "hmo" in t else None)
    return {"name": name, "mobile": mobile, "service_id": _service_in(t) or "consult", "date": date, "time": time_,
            "dentist_id": dentist, "hmo": hmo}


def _slot_at(time_, date=None, dentist=None):
    """The schedule slot at that time (store bookings ignored, so a repeated booking message maps to the same slot)."""
    for day in clinic.SCHEDULE["days"]:
        if date and day["date"] != date:
            continue
        for s in day["slots"]:
            if s["time"] == time_ and not s["taken"] and (not dentist or s["dentist"] == dentist):
                return {"date": day["date"], "dentist": s["dentist"]}
    return None


def _date_from_history(messages, time_):
    for m in reversed(messages):
        if m["role"] == "assistant" and m.get("content"):
            hit = re.search(rf"(\d{{4}}-\d{{2}}-\d{{2}})(?: at)? {time_}", m["content"])
            if hit:
                return hit.group(1)
    return None
