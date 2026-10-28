"""The built-in reply check (2026-10-28, after Meta's "Agents 102: verifiable agents" workshop): before a reply reaches the
patient, every price, date and time in it must come from this turn's tool results, the chat so far, or the clinic's own facts.
Deterministic, no model call. The agent retries on a miss and hands the chat to staff after the last retry."""
import re
from app import clinic

DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?", re.I)
MONEY = re.compile(r"(?:₱|\bphp\s?|\bp(?=\d))\s?(\d[\d,]*)|\b(\d[\d,]*)\s*(?:pesos?|php)\b", re.I)


def _times(text):
    out = set()
    for h, m, ampm in TIME.findall(text or ""):
        h = int(h)
        if ampm and ampm.lower().startswith("p") and h < 12:
            h += 12
        if ampm and ampm.lower().startswith("a") and h == 12:
            h = 0
        out.add(f"{h:02d}:{m}")
    return out


def _money(text):
    return {int((a or b).replace(",", "")) for a, b in MONEY.findall(text or "") if (a or b).replace(",", "").isdigit()}


def _numbers(text):
    return {int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", text or "") if n.replace(",", "").isdigit()}


def clinic_facts():
    """The facts the system prompt gives the model: price ranges, hours, phone."""
    c = clinic.CLINIC["clinic"]
    parts = [f"{s['price_min']} {s['price_max']}" for s in clinic.services()]
    parts += [f"{k} {v}" for k, v in c["hours"].items()] + [c["phone"]]
    return " ".join(parts)


def check(reply, sources):
    """-> list of misses, empty when every price, date and time in the reply is backed by the sources text."""
    src = " ".join(sources) + " " + clinic_facts()
    misses = []
    misses += [f"date {d}" for d in sorted(set(DATE.findall(reply)) - set(DATE.findall(src)))]
    misses += [f"time {t}" for t in sorted(_times(reply) - _times(src))]
    known = _numbers(src)
    misses += [f"price {p:,} pesos" for p in sorted(_money(reply)) if p not in known]
    return misses
