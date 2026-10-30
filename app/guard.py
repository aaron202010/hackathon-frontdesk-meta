"""Screens every patient message before the model sees it. Word lists and replies live in data/clinic.json["guardrails"]."""
import datetime, re
from app import clinic
from app.clinic import CLINIC, services, price_line

G = CLINIC["guardrails"]
INJECTION_WORDS = ["ignore your rules", "ignore the rules", "ignore previous", "ignore all", "system prompt", "your instructions",
                   "jailbreak", "pretend you are", "system override", "admin mode", "developer mode", "debug mode", "god mode",
                   "disregard your", "disregard all", "forget your rules", "forget your instructions", "forget all previous"]
PRICE_WORDS = ["discount", "price", "percent", "%", "free", "libre", "promo", "cheaper", "presyo"]  # an injection about money keeps the price reply
PRIVACY_WORDS = ["patients", "patient's", "pasyente", "bookings", "mobile number", "phone number"]  # an injection about other patients gets the privacy line
IDENTITY_WORDS = ["real person", "real human", "are you human", "are you a bot", "are you a robot", "talking to a bot", "talking to a human",
                  "totoong tao", "bot ka ba", "robot ka ba"]
BOOKING_ASK = re.compile(r"\b(book|reserve|magpa-?book|magpa-?schedule)\b", re.I)  # "book me", not "booking" (c09 cancels Ana's booking)
TAGLISH_WORDS = {"po", "ba", "ang", "ng", "ako", "kayo", "mo", "ko", "magkano", "pwede", "bukas", "sa", "yung", "ano", "may",
                 "meron", "hindi", "oo", "sige", "salamat", "ninyo", "namin", "para", "kung", "ito", "yan"}


def screen(text):
    """One of: takeover, emergency, clinical, injection, identity, ok."""
    t = (text or "").strip().lower()
    if t.startswith(G["takeover_command"]):
        return "takeover"
    if any(w in t for w in G["emergency_words"]):
        return "emergency"
    if any(w in t for w in G["clinical_words"]):
        return "clinical"
    if any(w in t for w in INJECTION_WORDS) or ("ignore" in t and "discount" in t):
        return "injection"
    if any(w in t for w in IDENTITY_WORDS):
        return "identity"
    return "ok"


def fixed(key, text=""):
    """A fixed line in the patient's language: the Taglish variant (<key>_tl) only when the patient wrote Taglish."""
    return G.get(key + "_tl") if is_taglish(text) and G.get(key + "_tl") else G.get(key, "")


def asks_to_book(text):
    return bool(BOOKING_ASK.search(text or ""))


def asked_date(text):
    """The date of "tomorrow"/"bukas", "today"/"ngayon" or a weekday name in the message, else None (the soonest slots)."""
    t = (text or "").lower()
    today = clinic.now_manila().date()
    if "tomorrow" in t or "bukas" in t:
        return (today + datetime.timedelta(days=1)).isoformat()
    if "today" in t or "ngayon" in t:
        return today.isoformat()
    for w in re.findall(r"[a-z]+", t):
        key = clinic.TAGALOG_DAYS.get(w) or next((k for k, v in clinic.DAY_NAMES.items() if v.lower() == w), None)
        if key:
            return next((d["date"] for d in clinic.SCHEDULE["days"] if d["day"] == key), None)
    return None


def slot_offer(text):
    """Real open slots for the day the patient asked, from the schedule and the bookings, then how to pick one. Never a made-up slot."""
    date, lead = asked_date(text), ""
    slots = clinic.open_slots(date) if date else []
    if date and not slots:
        lead = fixed("slot_offer_later", text) + " "
    slots = slots or clinic.open_slots()
    if not slots:
        return clinic.slot_lines(slots)
    return lead + clinic.slot_lines(slots) + " " + fixed("slot_offer_tail", text)


def reply_for(kind, text=""):
    """The fixed reply for a screened message. An injection about money carries the normal price ranges, no discount; one about
    other patients gets the privacy line; any other gets a short refusal. A medical question that also asks to book still gets real slots."""
    t = (text or "").lower()
    if kind == "injection":
        if any(w in t for w in PRICE_WORDS):
            return G["injection_reply"] + " " + " ".join(price_line(s["id"]) for s in services())
        if any(w in t for w in PRIVACY_WORDS):
            return G["privacy_reply"]
        return fixed("injection_refusal", text)
    if kind == "identity":
        return fixed("identity_reply", text).format(**CLINIC["clinic"])
    if kind == "clinical" and asks_to_book(text):
        return fixed("clinical_booking_reply", text) + " " + slot_offer(text)
    return fixed(kind + "_reply", text)


# words that are also English ("may", "sa" in names) only count with a second Tagalog word (2026-10-28: "May I book"
# got a Taglish reply in the English demo)
AMBIGUOUS_WORDS = {"may", "sa", "ito", "mo", "ko", "ba", "ano", "para", "kung"}


def is_taglish(text):
    words = set(w.strip(".,?!") for w in (text or "").lower().split())
    hits = words & TAGLISH_WORDS
    return bool(hits - AMBIGUOUS_WORDS) or len(hits) >= 2
