"""Voice notes in stub mode: the transcript comes from the file name (like the card stub), the audio still has to be real audio."""
import io, os, tempfile, wave
os.environ["FRONTDESK_STUB"] = "1"
os.environ.setdefault("FRONTDESK_DB", os.path.join(tempfile.mkdtemp(), "frontdesk.db"))

from fastapi.testclient import TestClient
from app import clinic
from app.main import app

client = TestClient(app)
G = clinic.CLINIC["guardrails"]


def tone_wav(seconds=1.0, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"\x00\x10" * int(seconds * rate))
    return buf.getvalue()


def send(name, data, chat_id):
    return client.post("/voice", data={"chat_id": chat_id}, files={"file": (name, data, "audio/wav")})


def test_voice_note_runs_the_same_turn_as_typing():
    r = send("how_much_is_a_cleaning.wav", tone_wav(), "voice-1").json()
    assert r["transcript"] == "how much is a cleaning"
    assert r["steps"][0]["label"].startswith("muse-voice-transcribe-1.0 transcribed")
    assert "1,000" in r["reply"] and "dentist confirms" in r["reply"].lower()


def test_medical_voice_note_hits_the_guard():
    r = send("what_medicine_can_i_take.wav", tone_wav(), "voice-2").json()
    assert r["screen"] == "clinical" and r["reply"] == G["clinical_reply"]


def test_not_audio_is_refused_and_silence_gets_the_not_heard_line():
    assert send("x.wav", b"not audio at all", "voice-3").status_code == 400
    r = send("_.wav", tone_wav(), "voice-4").json()
    assert r["transcript"] == "" and "couldn't hear" in r["reply"]
