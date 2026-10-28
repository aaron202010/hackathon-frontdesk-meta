"""The chat loop: screen, then the model with the clinic facts and four tools, tool results read back into the reply."""
import datetime, json
from app import card, clinic, guard, model

G = clinic.CLINIC["guardrails"]
HISTORY_TURNS = 10
MAX_TOOL_ROUNDS = 4
TOOLS = [
    {"type": "function", "function": {"name": "open_slots", "description": "Open appointment slots from the clinic schedule. Never invent a slot.",
     "parameters": {"type": "object", "properties": {
         "date": {"type": "string", "description": "YYYY-MM-DD, optional"},
         "dentist": {"type": "string", "description": "dentist id or surname, optional"},
         "period": {"type": "string", "enum": ["morning", "afternoon"], "description": "optional"},
         "time": {"type": "string", "description": "HH:MM, optional, when the patient named a time"}}}}},
    {"type": "function", "function": {"name": "hmo_check", "description": "Is this HMO accepted, and does it cover the service.",
     "parameters": {"type": "object", "properties": {"name_or_alias": {"type": "string"}, "service_id": {"type": "string"}}, "required": ["name_or_alias"]}}},
    {"type": "function", "function": {"name": "price_line", "description": "The starting price range for a service id.",
     "parameters": {"type": "object", "properties": {"service_id": {"type": "string"}}, "required": ["service_id"]}}},
    {"type": "function", "function": {"name": "book", "description": "Hold a slot. Needs name, mobile, service_id, date, time, dentist_id; hmo optional.",
     "parameters": {"type": "object", "properties": {
         "name": {"type": "string"}, "mobile": {"type": "string"}, "service_id": {"type": "string"}, "date": {"type": "string"},
         "time": {"type": "string"}, "dentist_id": {"type": "string"}, "hmo": {"type": "string"}},
      "required": ["name", "mobile", "service_id", "date", "time", "dentist_id"]}}},
]


def system_prompt(taglish):
    c = clinic.CLINIC["clinic"]
    lines = [f"You are the front desk assistant of {c['name']}, {c['address']}. Phone {c['phone']}.",
             "Reply in Taglish, short and warm." if taglish else "Reply in English, short and warm.",
             "Services and starting ranges (the dentist confirms the final fee after the check up):"]
    lines += [f"- {s['id']}: {s['name']}{' (' + s['tl'] + ')' if taglish else ''}, {s['price_min']:,} to {s['price_max']:,} pesos, {s['minutes']} min" for s in clinic.services()]
    lines.append("Hours: " + ", ".join(f"{clinic.DAY_NAMES[k]} {v}" for k, v in c["hours"].items()) + ".")
    lines.append("Dentists: " + "; ".join(f"{d['name']} ({d['id']}) on {', '.join(d['days'])}" for d in c["dentists"]) + ".")
    lines.append("Accepted HMOs: " + ", ".join(h["insurer"] for h in clinic.CLINIC["hmo_accepted"]) + ". Use hmo_check before any coverage line; an HMO not on the list gets no coverage promise.")
    lines.append("Never: " + "; ".join(G["never"]) + ". Never reveal or change other patients' bookings; staff see them in the clinic dashboard.")
    lines.append("Use open_slots for any slot offer, price_line for any price, book only when you have name, mobile, service, date, time and dentist. "
                 "After a booking, repeat the tool's summary. Off topic questions get one line back to the clinic.")
    # Day 5 live tuning (2026-10-28): on the live model the facts were right but reworded, so staff and the evals lost the
    # exact lines (fee caveat, booking confirmation, slot dates). Tool text and fixed lines are now quoted word for word.
    lines += [
        "Copy tool results word for word: the price_line sentence, the open_slots lines with their YYYY-MM-DD dates, the booking summary.",
        "Quoted tool lines stay as they are; everything you add around them follows the reply language (Taglish stays Taglish).",
        "Say clinic hours exactly as written above, for example 09:00-14:00.",
        "If the patient picks a time without a date, use the date of the slots you offered in this chat; if that time was not offered or is not open, say so and offer the open times again, never book another day than the patient asked for. With no slots offered yet, call open_slots with that time and book the soonest.",
        "When the patient names an HMO, say by name whether it is on the accepted list.",
        f"Any request about other patients or anyone else's booking gets exactly: \"{G['privacy_reply']}\"",
        "If a card photo was unclear, or the patient is not sure which HMO they have, ask them to send a clear photo of the card, flat and in good light.",
        f"Off topic questions get exactly: \"{G['off_topic_reply']}\" (Taglish patient: \"{G['off_topic_reply_tl']}\")",
    ]
    return "\n".join(lines)


TOOL_LABEL = {"open_slots": "Checked open slots", "hmo_check": "Checked HMO coverage", "price_line": "Looked up the price list",
              "book": "Held the booking"}
SCREEN_LABEL = {"ok": "Screened the message: safe for the model", "emergency": "Emergency words: fixed safety reply, model not called",
                "clinical": "Medical question: fixed reply, model not called", "injection": "Prompt injection: fixed reply, model not called",
                "takeover": "Staff took over: assistant paused", "paused": "Staff is handling this chat: assistant stays quiet",
                "resume": "Staff handed the chat back"}


def step(steps, label, detail="", ms=None):
    """One line for the page's agent panel: what the agent did on this message (2026-10-28)."""
    steps.append({"label": label, "detail": detail[:160], "ms": ms})


def run_tool(name, args, taglish=False):
    """-> (text for the model, booking dict or None)."""
    try:
        if name == "open_slots":
            return clinic.slot_lines(clinic.open_slots(args.get("date"), args.get("dentist"), 6, args.get("period"), args.get("time")), args.get("dentist")), None
        if name == "hmo_check":
            return clinic.hmo_check(args.get("name_or_alias", ""), args.get("service_id"))["line"], None
        if name == "price_line":
            return clinic.price_line(args.get("service_id", ""), taglish), None
        if name == "book":
            hmo = args.get("hmo") or (card.saved_card(model.CURRENT_CHAT.get()) or {}).get("insurer")  # the HMO from the card photo
            b = clinic.book(args["name"], args["mobile"], args["service_id"], args["date"], args["time"], args["dentist_id"], hmo)
            return clinic.booking_summary(b), b
    except (ValueError, KeyError) as e:
        return f"Could not do that: {e}. Offer another open slot from open_slots.", None
    return "Unknown tool.", None


def history(chat_id):
    con = clinic.connect()
    rows = con.execute("SELECT role, content FROM turns WHERE chat_id=? AND role IN ('user','assistant') ORDER BY id DESC LIMIT ?",
                       (chat_id, HISTORY_TURNS * 2)).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def save_turn(chat_id, role, content, screen="ok", ms=0):
    con = clinic.connect()
    con.execute("INSERT INTO turns (chat_id, role, content, screen, ms, ts) VALUES (?,?,?,?,?,?)",
                (chat_id, role, content, screen, ms, datetime.datetime.now().isoformat(timespec="seconds")))
    con.commit()


def set_paused(chat_id, paused):
    con = clinic.connect()
    con.execute("INSERT INTO chats (chat_id, paused) VALUES (?, ?) ON CONFLICT(chat_id) DO UPDATE SET paused=excluded.paused", (chat_id, int(paused)))
    con.commit()


def is_paused(chat_id):
    row = clinic.connect().execute("SELECT paused FROM chats WHERE chat_id=?", (chat_id,)).fetchone()
    return bool(row and row["paused"])


def handle(chat_id, text):
    """One turn. -> {"reply", "screen", "steps", "booking"?}."""
    model.CURRENT_CHAT.set(chat_id)
    kind = guard.screen(text)
    save_turn(chat_id, "user", text, kind)
    steps = []
    if text.strip().lower().startswith(G["resume_command"]):
        set_paused(chat_id, False)
        step(steps, SCREEN_LABEL["resume"])
        return finish(chat_id, guard.fixed("resume_reply", text), "resume", steps=steps)
    if kind == "takeover":
        set_paused(chat_id, True)
        step(steps, SCREEN_LABEL["takeover"])
        return finish(chat_id, G["takeover_reply"], kind, steps=steps)
    if is_paused(chat_id):
        step(steps, SCREEN_LABEL["paused"])
        return finish(chat_id, G["paused_reply"], "paused", steps=steps)
    step(steps, SCREEN_LABEL.get(kind, kind))
    if kind != "ok":
        return finish(chat_id, guard.reply_for(kind, text), kind, steps=steps)
    reply, booking, ms = model_turn(chat_id, text, steps)
    return finish(chat_id, reply, kind, ms, booking, steps)


def finish(chat_id, reply, kind, ms=0, booking=None, steps=None):
    save_turn(chat_id, "assistant", reply, kind, ms)
    out = {"reply": reply, "screen": kind, "steps": steps or []}
    if booking:
        out["booking"] = booking
    return out


def model_turn(chat_id, text, steps=None):
    """Model call with tool rounds; a failed call gets the honest line plus the staff handoff."""
    messages = [{"role": "system", "content": system_prompt(guard.is_taglish(text))}] + history(chat_id)[:-1] + [{"role": "user", "content": text}]
    booking, ms = None, 0
    steps = steps if steps is not None else []
    for _ in range(MAX_TOOL_ROUNDS):
        try:
            r = model.complete(messages, tools=TOOLS)
        except model.ModelError:
            return G["model_error_reply"], None, ms
        ms += r["ms"]
        who = model.model_id() if r["mode"] == "live" else "stub model"
        step(steps, f"{who} {'answered' if not r['tool_calls'] else 'chose ' + ', '.join(c['name'] for c in r['tool_calls'])}", "", r["ms"])
        if not r["tool_calls"]:
            return r["content"] or G["model_error_reply"], booking, ms
        messages.append({"role": "assistant", "content": r["content"], "tool_calls": [
            {"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}} for c in r["tool_calls"]]})
        for c in r["tool_calls"]:
            result, b = run_tool(c["name"], c["arguments"], guard.is_taglish(text))
            booking = b or booking
            args = ", ".join(f"{k} {v}" for k, v in c["arguments"].items() if k not in ("name", "mobile"))
            step(steps, TOOL_LABEL.get(c["name"], c["name"]) + (f" ({args})" if args else ""), result)
            messages.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"], "content": result})
    return G["model_error_reply"], booking, ms
