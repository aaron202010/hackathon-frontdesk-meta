"""Voice notes: any browser recording in, Meta's speech to text (muse-voice-transcribe-1.0) out, then the normal chat turn.
API (dev.meta.ai/docs/speech-to-text, read 2026-10-28): POST /v1/asr/transcribe, multipart with a JSON "request" part and a
WAV "audio" part (mono, 16-bit PCM, 16 or 24 kHz, 10 minutes and 32 MB at most); the answer carries "transcript"."""
import json, os, re, subprocess, tempfile
import httpx
from app import model

ASR_MODEL = "muse-voice-transcribe-1.0"
MAX_SECONDS = 120  # a patient's voice note, not a meeting


def to_wav(data):
    """Browser audio (webm, ogg, mp4, wav) -> 24 kHz mono 16-bit WAV bytes. ValueError when ffmpeg can't read it."""
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, "in"), os.path.join(d, "out.wav")
        open(src, "wb").write(data)
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-t", str(MAX_SECONDS), "-ac", "1", "-ar", "24000",
                            "-c:a", "pcm_s16le", "-map_metadata", "-1", dst], capture_output=True, timeout=60)
        if r.returncode != 0 or not os.path.exists(dst) or os.path.getsize(dst) < 1000:
            raise ValueError("not audio")
        return open(dst, "rb").read()


def transcribe(data, hint=None):
    """-> transcript text ("" when nothing was said). Stub mode reads the words from the file name, like the card stub."""
    wav = to_wav(data)
    if model.stub_mode():
        stem = os.path.splitext(os.path.basename(hint or ""))[0]
        return re.sub(r"[_-]+", " ", stem).strip()
    req = {"model": ASR_MODEL, "audioEncoding": "WAV", "languageBias": ["English", "Tagalog"]}
    try:
        r = httpx.post(model.BASE + "/asr/transcribe", headers={"Authorization": "Bearer " + os.environ["MODEL_API_KEY"], "Accept": "application/json"},
                       files={"request": (None, json.dumps(req), "application/json"), "audio": ("note.wav", wav, "audio/wav")}, timeout=60)
        r.raise_for_status()
        return (r.json().get("transcript") or "").strip()
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise model.ModelError(str(e)[:200])
