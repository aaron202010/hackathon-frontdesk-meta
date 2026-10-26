"""Clinic facts, schedule and the fake booking store. Everything comes from data/clinic.json and data/schedule.json."""
import json, os, sqlite3, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLINIC = json.load(open(os.path.join(ROOT, "data", "clinic.json")))
SCHEDULE = json.load(open(os.path.join(ROOT, "data", "schedule.json")))
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES = {"mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday", "fri": "Friday", "sat": "Saturday", "sun": "Sunday"}
TAGALOG_DAYS = {"lunes": "mon", "martes": "tue", "miyerkules": "wed", "huwebes": "thu", "biyernes": "fri", "sabado": "sat", "linggo": "sun"}


def db_path():
    return os.environ.get("FRONTDESK_DB") or os.path.join(ROOT, "data", "frontdesk.db")


def connect():
    con = sqlite3.connect(db_path())
    con.row_factory = sqlite3.Row
    con.executescript("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY, name TEXT, mobile TEXT, service_id TEXT, date TEXT, time TEXT,
            dentist_id TEXT, hmo TEXT, created TEXT, UNIQUE(name, mobile, date, time));
        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY, chat_id TEXT, role TEXT, content TEXT, screen TEXT, ms INTEGER, ts TEXT);
        CREATE TABLE IF NOT EXISTS chats (chat_id TEXT PRIMARY KEY, paused INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS cards (
            chat_id TEXT PRIMARY KEY, insurer TEXT, member_name TEXT, member_id TEXT, valid_thru TEXT, confidence REAL, ts TEXT);
    """)
    return con


def services():
    return CLINIC["services"]


def service(service_id):
    return next((s for s in CLINIC["services"] if s["id"] == service_id), None)


def dentist(dentist_id):
    return next((d for d in CLINIC["clinic"]["dentists"] if d["id"] == dentist_id), None)


def peso(n):
    return f"{n:,} pesos"


def price_line(service_id):
    s = service(service_id)
    if not s:
        return "That service is not on our list, so I can't quote a price. The clinic confirms it; the dentist confirms the fee after a consultation."
    return (f"{s['name']} ({s['tl']}): starting range {peso(s['price_min'])} to {peso(s['price_max'])}. "
            "The dentist confirms the final fee after the check up.")


def day_key(day):
    """'Sunday', 'sun', 'linggo' or '2026-10-27' -> 'sun' / 'tue'."""
    d = str(day).strip().lower()
    if d in TAGALOG_DAYS:
        return TAGALOG_DAYS[d]
    try:
        return DAYS[datetime.date.fromisoformat(d).weekday()]
    except ValueError:
        return d[:3] if d[:3] in DAYS else None


def hours_line(day):
    key = day_key(day)
    if not key:
        return "Hours: Mon to Fri 09:00-18:00, Sat 09:00-14:00, Sunday closed."
    hours = CLINIC["clinic"]["hours"][key]
    if hours == "closed":
        return (f"{DAY_NAMES[key]}: closed. We are open Mon to Fri 09:00-18:00 and Saturday 09:00-14:00. "
                "I can offer a Saturday or weekday slot.")
    who = ", ".join(d["name"] for d in CLINIC["clinic"]["dentists"] if key in d["days"])
    return f"{DAY_NAMES[key]}: open {hours} ({who})."


def dentist_id_for(dentist_hint):
    if not dentist_hint:
        return None
    h = str(dentist_hint).lower()
    for d in CLINIC["clinic"]["dentists"]:
        if h == d["id"] or h in d["name"].lower():
            return d["id"]
    return "none"  # a named dentist who does not work here matches nothing


def booked_keys(con=None):
    con = con or connect()
    return {(r["date"], r["time"], r["dentist_id"]) for r in con.execute("SELECT date, time, dentist_id FROM bookings")}


def open_slots(date=None, dentist=None, limit=6, period=None):
    """Open slots from the schedule minus bookings in the store. period: 'morning' (before 12:00) or 'afternoon'."""
    did = dentist_id_for(dentist)
    taken = booked_keys()
    names = {d["id"]: d["name"] for d in CLINIC["clinic"]["dentists"]}
    out = []
    for day in SCHEDULE["days"]:
        if date and day["date"] != str(date):
            continue
        for s in day["slots"]:
            if s["taken"] or (did and s["dentist"] != did) or (day["date"], s["time"], s["dentist"]) in taken:
                continue
            if period == "morning" and s["time"] >= "12:00" or period == "afternoon" and s["time"] < "12:00":
                continue
            out.append({"date": day["date"], "day": DAY_NAMES[day["day"]], "time": s["time"],
                        "dentist_id": s["dentist"], "dentist": names[s["dentist"]]})
            if len(out) >= limit:
                return out
    return out


def slot_lines(slots, dentist_hint=None):
    if not slots:
        d = dentist(dentist_id_for(dentist_hint))
        days = f" {d['name']} is in on {', '.join(DAY_NAMES[k] for k in d['days'])}." if d else ""
        return "No open slots match that." + days + " I can check another day for you."
    return "Open slots: " + "; ".join(f"{s['day']} {s['date']} {s['time']} with {s['dentist']}" for s in slots) + "."


def find_hmo(name_or_alias):
    n = (name_or_alias or "").strip().lower()
    for h in CLINIC["hmo_accepted"]:
        if n and (n == h["insurer"].lower() or n in h["aliases"] or any(a in n for a in h["aliases"])):
            return h
    return None


def hmo_check(name_or_alias, service_id=None):
    """Accepted or not, covered or not for the service, the note. Never a promise for an unlisted HMO."""
    h = find_hmo(name_or_alias)
    if not h:
        return {"accepted": False, "insurer": name_or_alias, "covered": False, "note": "", "line": CLINIC["hmo_not_accepted_reply"]}
    s = service(service_id) if service_id else None
    covered = bool(s and s["id"] in h["covers"])
    covers = ", ".join(service(c)["name"] for c in h["covers"] if service(c))
    note = f" Note: {h['note']}." if h["note"] else ""
    if s:
        status = f"{h['insurer']} is accepted and covers {s['name']}." if covered else f"{h['insurer']} is accepted but does not cover {s['name']}; that one is cash."
    else:
        status = f"{h['insurer']} is accepted."
    return {"accepted": True, "insurer": h["insurer"], "covered": covered, "note": h["note"],
            "line": f"{status} It covers: {covers}.{note}"}


def slot_is_open(date, time, dentist_id):
    for day in SCHEDULE["days"]:
        if day["date"] == date:
            return any(s["time"] == time and s["dentist"] == dentist_id and not s["taken"] for s in day["slots"])
    return False


def book(name, mobile, service_id, date, time, dentist_id, hmo=None):
    """One booking row; the same name+mobile+date+time returns the existing row instead of a second one."""
    if not service(service_id):
        raise ValueError("unknown service")
    if not dentist(dentist_id):
        raise ValueError("unknown dentist")
    if not slot_is_open(date, time, dentist_id):
        raise ValueError("that slot is not open in the schedule")
    con = connect()
    key = (name.strip(), mobile.strip(), date, time)
    row = con.execute("SELECT * FROM bookings WHERE name=? AND mobile=? AND date=? AND time=?", key).fetchone()
    if row:
        return dict(row) | {"created": False}
    if (date, time, dentist_id) in booked_keys(con):
        raise ValueError("that slot was just booked by someone else")
    con.execute("INSERT INTO bookings (name, mobile, date, time, service_id, dentist_id, hmo, created) VALUES (?,?,?,?,?,?,?,?)",
                key + (service_id, dentist_id, hmo, datetime.datetime.now().isoformat(timespec="seconds")))
    con.commit()
    row = con.execute("SELECT * FROM bookings WHERE name=? AND mobile=? AND date=? AND time=?", key).fetchone()
    return dict(row) | {"created": True}


def hmo_status_line(hmo, service_id):
    if not hmo:
        return "HMO: none, cash."
    r = hmo_check(hmo, service_id)
    if not r["accepted"]:
        return f"HMO: {hmo} is not on our accepted list, so cash for now; the clinic can check with the HMO."
    s = service(service_id)["name"]
    note = f", {r['note'].lower()}" if r["note"] else ""
    return f"HMO: {r['insurer']}, {'covered for ' + s if r['covered'] else 'accepted but not for ' + s}{note}."


def booking_summary(booking):
    s = service(booking["service_id"])
    d = dentist(booking["dentist_id"])
    day = DAY_NAMES[DAYS[datetime.date.fromisoformat(booking["date"]).weekday()]]
    return (f"Booking held for {booking['name']}: {day} {booking['date']} at {booking['time']}, {s['name']}, with {d['name']}. "
            f"{hmo_status_line(booking.get('hmo'), booking['service_id'])} The clinic confirms by text to {booking['mobile']}.")
