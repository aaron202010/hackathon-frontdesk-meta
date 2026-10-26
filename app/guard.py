"""Screens every patient message before the model sees it. Word lists and replies live in data/clinic.json["guardrails"]."""
from app.clinic import CLINIC, services, price_line

G = CLINIC["guardrails"]
INJECTION_WORDS = ["ignore your rules", "ignore the rules", "ignore previous", "ignore all", "system prompt", "your instructions",
                   "jailbreak", "pretend you are"]
TAGLISH_WORDS = {"po", "ba", "ang", "ng", "ako", "kayo", "mo", "ko", "magkano", "pwede", "bukas", "sa", "yung", "ano", "may",
                 "meron", "hindi", "oo", "sige", "salamat", "ninyo", "namin", "para", "kung", "ito", "yan"}


def screen(text):
    """One of: takeover, emergency, clinical, injection, ok."""
    t = (text or "").strip().lower()
    if t.startswith(G["takeover_command"]):
        return "takeover"
    if any(w in t for w in G["emergency_words"]):
        return "emergency"
    if any(w in t for w in G["clinical_words"]):
        return "clinical"
    if any(w in t for w in INJECTION_WORDS) or ("ignore" in t and "discount" in t):
        return "injection"
    return "ok"


def reply_for(kind):
    """The fixed reply for a screened message; the injection reply carries the normal price ranges, no discount."""
    if kind == "injection":
        return G["injection_reply"] + " " + " ".join(price_line(s["id"]) for s in services())
    return G.get(kind + "_reply", "")


def is_taglish(text):
    words = set(w.strip(".,?!") for w in (text or "").lower().split())
    return len(words & TAGLISH_WORDS) >= 1
