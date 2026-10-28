"""The built-in reply check (2026-10-28, after Meta's "Agents 102: verifiable agents" workshop): before a reply reaches the
patient, every price, date and time in it must come from this turn's tool results, the chat so far, or the clinic's own facts.
Deterministic, no model call. The agent retries on a miss and hands the chat to staff after the last retry.
Tightened the same day after Muse Code's review: bare hours ("3pm"), prices without a peso sign, month-name dates, and a
price is only backed by a price (a peso amount in the sources or the clinic's price list), not by any number."""
import datetime, re
from app import clinic

DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
TIME = re.compile(r"\b(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?", re.I)
HOUR = re.compile(r"(?<![:\d])\b(\d{1,2})\s*([ap])\.?m\b\.?", re.I)  # not the minutes of "9:30 AM"
MONEY = re.compile(r"(?:₱|\bphp\s?|\bp(?=\d))\s?(\d[\d,]*)|\b(\d[\d,]*)\s*(?:pesos?|php)\b", re.I)
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
MONTH_DAY = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})\b", re.I)
PHONE = re.compile(r"\b0\d{3}[\s-]?\d{3}[\s-]?\d{4}\b")


def _times(text):
    out = set()
    for h, m, ampm in TIME.findall(text or ""):
        h = int(h)
        if ampm and ampm.lower().startswith("p") and h < 12:
            h += 12
        if ampm and ampm.lower().startswith("a") and h == 12:
            h = 0
        out.add(f"{h:02d}:{m}")
    for h, ap in HOUR.findall(text or ""):  # "3pm", "10 AM": a bare hour is a time too
        h = int(h) % 12 + (12 if ap.lower() == "p" else 0)
        out.add(f"{h:02d}:00")
    return out


def _money(text):
    return {int((a or b).replace(",", "")) for a, b in MONEY.findall(text or "") if (a or b).replace(",", "").isdigit()}


def _month_days(text):
    days = {(int(d[5:7]), int(d[8:10])) for d in DATE.findall(text or "")}
    days |= {(MONTHS[m.lower()[:3]], int(d)) for m, d in MONTH_DAY.findall(text or "")}
    return days


def _strip(text):
    """Text with dates, times, phone numbers and IDs removed, so the numbers left over are amounts."""
    t = PHONE.sub(" ", text or "")
    t = DATE.sub(" ", t)
    t = TIME.sub(" ", t)
    t = HOUR.sub(" ", t)
    t = re.sub(r"[A-Za-z]+-\d+|\d+/\d+", " ", t)  # member IDs (MX-000001), card dates (12/2027)
    return t


def _numbers(text):
    return {int(n.replace(",", "")) for n in re.findall(r"\b\d[\d,]*\b", text or "") if n.replace(",", "").isdigit()}


def clinic_prices():
    return {v for s in clinic.services() for v in (s["price_min"], s["price_max"])}


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
    src_days = _month_days(src)
    for m, d in sorted({(MONTHS[m.lower()[:3]], int(d)) for m, d in MONTH_DAY.findall(reply)} - src_days):
        misses.append(f"date {datetime.date(2000, m, d).strftime('%b')} {d}")
    misses += [f"time {t}" for t in sorted(_times(reply) - _times(src))]
    prices = _money(src) | clinic_prices()
    marked = _money(reply)
    misses += [f"price {p:,} pesos" for p in sorted(marked) if p not in prices]
    # an amount without a peso sign still has to come from the sources (a count, a price, an ID left over)
    src_numbers = _numbers(_strip(src)) | prices
    bare = {n for n in _numbers(_strip(MONEY.sub(" ", reply))) if 100 <= n <= 100000}
    misses += [f"number {n:,}" for n in sorted(bare - src_numbers)]
    return misses
