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


def fixed(key, text=""):
    """A fixed line in the patient's language: the Taglish variant (<key>_tl) only when the patient wrote Taglish."""
    return G.get(key + "_tl") if is_taglish(text) and G.get(key + "_tl") else G.get(key, "")


def reply_for(kind, text=""):
    """The fixed reply for a screened message; the injection reply carries the normal price ranges, no discount."""
    if kind == "injection":
        return G["injection_reply"] + " " + " ".join(price_line(s["id"]) for s in services())
    return fixed(kind + "_reply", text)


# words that are also English ("may", "sa" in names) only count with a second Tagalog word (2026-10-28: "May I book"
# got a Taglish reply in the English demo)
AMBIGUOUS_WORDS = {"may", "sa", "ito", "mo", "ko", "ba", "ano", "para", "kung"}


def is_taglish(text):
    words = set(w.strip(".,?!") for w in (text or "").lower().split())
    hits = words & TAGLISH_WORDS
    return bool(hits - AMBIGUOUS_WORDS) or len(hits) >= 2
