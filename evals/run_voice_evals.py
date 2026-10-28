"""Voice note evals: each note in evals/voice_notes.json is transcribed by muse-voice-transcribe-1.0, then run through the agent
and scored with the same rules as the typed chats (scored on what was SAID, so a mishearing that changes the answer fails).
Stub mode by default; FRONTDESK_LIVE=1 for the live models. Writes evals/voice-results-<date>.json and a README line."""
import datetime, difflib, json, os, re, sys, uuid
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "evals"))
import run_evals  # noqa: E402  (sets stub or live mode and the eval database)
from app import agent, model, voice  # noqa: E402

MIN_WORDS = 0.8  # share of the spoken words the transcript must hold


def words(s):
    return re.findall(r"[a-z0-9']+", s.lower())


def main():
    notes = json.load(open(os.path.join(ROOT, "evals", "voice_notes.json")))["notes"]
    rows = []
    for n in notes:
        data = open(os.path.join(ROOT, "evals", "voice", n["id"] + ".webm"), "rb").read()
        heard = voice.transcribe(data, hint=n["said"].replace(" ", "_") + ".wav")
        acc = difflib.SequenceMatcher(None, words(n["said"]), words(heard)).ratio()
        chat_id = f"voice-eval-{n['id']}-{uuid.uuid4().hex[:6]}"
        out = agent.handle(chat_id, heard or "(nothing heard)")
        res = {"screen": out["screen"], "reply": out["reply"], "paused": agent.is_paused(chat_id)}
        rule = run_evals.score({"id": n["id"], "user": n["said"], "expect": n["expect"], "tags": n["tags"], "lang": n["lang"]}, res)
        ok = rule["verdict"] == "pass" and acc >= MIN_WORDS
        rows.append({"id": n["id"], "voice": n["voice"], "said": n["said"], "heard": heard, "word_match": round(acc, 2),
                     "screen": out["screen"], "reply": out["reply"], "rule": rule, "verdict": "pass" if ok else "fail"})
        print(f"{n['id']}  {n['lang']}  {'pass' if ok else 'FAIL'}  words {acc:.2f}  heard: {heard[:60]!r}  {rule['reason'][:90]}")
    passed = sum(r["verdict"] == "pass" for r in rows)
    mode = "stub" if model.stub_mode() else "live"
    print(f"voice notes: {passed} of {len(rows)} pass ({mode})")
    if mode == "stub":
        return  # the stub reads the words from the file name: a check of the plumbing, not a result worth recording
    date = datetime.date.today().isoformat()
    json.dump({"date": date, "mode": mode, "asr": voice.ASR_MODEL, "passed": passed, "total": len(rows), "notes": rows},
              open(os.path.join(ROOT, "evals", f"voice-results-{date}.json"), "w"), indent=1)
    path = os.path.join(ROOT, "README.md"); text = open(path).read()
    line = f"Voice notes {date}: {passed} of {len(rows)} pass (transcribed by {voice.ASR_MODEL}, then the same rule checks; {mode} mode)"
    text = re.sub(r"^Voice notes .*$", line, text, count=1, flags=re.M) if re.search(r"^Voice notes .*$", text, re.M) else text.replace("## Eval\n", f"## Eval\n\n{line}\n", 1)
    open(path, "w").write(text)


if __name__ == "__main__":
    main()
