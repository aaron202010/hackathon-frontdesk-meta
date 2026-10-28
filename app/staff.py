"""Read-only staff view: the key check and the three queries behind GET /staff/data. Nothing here writes to the database."""
import datetime, hmac, os
from zoneinfo import ZoneInfo
from fastapi.responses import JSONResponse, PlainTextResponse
from app import clinic

MANILA = ZoneInfo("Asia/Manila")
UTC = datetime.timezone.utc
MAX_BOOKINGS = 50
MAX_TAKEOVERS = 20
CUT = 160
PRIVATE = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex", "Referrer-Policy": "no-referrer"}  # the key sits in the URL


def denied(key):
    """None when the request may pass, else the response to send. No FRONTDESK_STAFF_KEY set = the feature is off = a plain 404."""
    expected = os.environ.get("FRONTDESK_STAFF_KEY", "")
    if not expected:
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    if not hmac.compare_digest((key or "").encode(), expected.encode()):
        return PlainTextResponse("Staff key needed.", status_code=401)
    return None


def _utc(ts):
    """turns.ts and bookings.created are naive datetime.now() strings from a server on UTC."""
    return datetime.datetime.fromisoformat(ts).replace(tzinfo=UTC)


def _manila_iso(ts):
    return _utc(ts).astimezone(MANILA).isoformat(timespec="seconds") if ts else None


def _day_window(day):
    """The Manila calendar day as [start, end) in the naive UTC ISO strings the tables hold (they sort as text)."""
    def edge(d):
        return datetime.datetime.combine(d, datetime.time(), MANILA).astimezone(UTC).replace(tzinfo=None).isoformat(timespec="seconds")
    return edge(day), edge(day + datetime.timedelta(days=1))


def _count(con, sql, params):
    return con.execute(sql, params).fetchone()[0]


def today_counts(con, today):
    start, end = _day_window(today)
    screened = "SELECT COUNT(*) FROM turns WHERE role='user' AND screen=? AND ts>=? AND ts<?"
    return {
        "date": today.isoformat(),
        "chats_started": _count(con, "SELECT COUNT(*) FROM (SELECT MIN(ts) AS first FROM turns GROUP BY chat_id) WHERE first>=? AND first<?", (start, end)),
        "bookings_made": _count(con, "SELECT COUNT(*) FROM bookings WHERE created>=? AND created<?", (start, end)),
        "medical_questions": _count(con, screened, ("clinical", start, end)),
        "emergencies": _count(con, screened, ("emergency", start, end)),
        "rule_change_attempts": _count(con, screened, ("injection", start, end)),
        "card_photos": _count(con, screened, ("card", start, end)),
    }


def _mask(mobile):
    digits = "".join(c for c in str(mobile or "") if c.isdigit())
    return "•••• " + digits[-4:] if digits else "••••"


def _weekday(date):
    try:
        return clinic.DAY_NAMES[clinic.DAYS[datetime.date.fromisoformat(date).weekday()]]
    except (ValueError, TypeError):
        return ""


def upcoming_bookings(con, today):
    rows = con.execute("SELECT date, time, name, mobile, service_id, dentist_id, hmo FROM bookings WHERE date>=? ORDER BY date, time LIMIT ?",
                       (today.isoformat(), MAX_BOOKINGS)).fetchall()
    out = []
    for r in rows:
        service, dentist = clinic.service(r["service_id"]), clinic.dentist(r["dentist_id"])
        out.append({"date": r["date"], "weekday": _weekday(r["date"]), "time": r["time"], "name": r["name"], "mobile": _mask(r["mobile"]),
                    "service": service["name"] if service else r["service_id"], "dentist": dentist["name"] if dentist else r["dentist_id"],
                    "hmo": r["hmo"] or "cash"})
    return out


def _cut(text):
    text = text or ""
    return text if len(text) <= CUT else text[:CUT - 1] + "…"


def takeovers(con):
    chats = con.execute("""
        SELECT c.chat_id, MAX(CASE WHEN t.screen='takeover' THEN t.ts END) AS taken_at, COUNT(t.id) AS turns
        FROM chats c LEFT JOIN turns t ON t.chat_id=c.chat_id
        WHERE c.paused=1 GROUP BY c.chat_id ORDER BY taken_at DESC LIMIT ?""", (MAX_TAKEOVERS,)).fetchall()
    out = []
    for c in chats:
        last = con.execute("SELECT role, content, ts FROM turns WHERE chat_id=? ORDER BY id DESC LIMIT 3", (c["chat_id"],)).fetchall()
        out.append({"chat_id": c["chat_id"][:8], "taken_over_at": _manila_iso(c["taken_at"]), "turns": c["turns"],
                    "last_turns": [{"role": t["role"], "content": _cut(t["content"]), "ts": _manila_iso(t["ts"])} for t in reversed(last)]})
    return out


def snapshot():
    con = clinic.connect()
    try:
        today = clinic.now_manila().date()
        return {"today": today_counts(con, today), "bookings": upcoming_bookings(con, today), "takeovers": takeovers(con)}
    finally:
        con.close()
