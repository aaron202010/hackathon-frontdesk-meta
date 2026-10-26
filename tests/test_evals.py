"""The eval runner's rules: a good stub run passes most chats, and a reply that says nothing useful passes none."""
import importlib.util, json, os, tempfile
os.environ["FRONTDESK_STUB"] = "1"
os.environ["FRONTDESK_DB"] = os.path.join(tempfile.mkdtemp(), "frontdesk.db")

import pytest
from app import model

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("run_evals", os.path.join(ROOT, "evals", "run_evals.py"))
run_evals = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_evals)
CHATS = json.load(open(os.path.join(ROOT, "evals", "chats.json")))["chats"]


@pytest.fixture(autouse=True)
def fresh_files(tmp_path, monkeypatch):
    monkeypatch.setattr(model, "TRACE", str(tmp_path / "trace.jsonl"))
    monkeypatch.setenv("FRONTDESK_DB", str(tmp_path / "frontdesk.db"))


@pytest.mark.parametrize("chat", CHATS, ids=lambda c: c["id"])
def test_an_empty_reply_fails_every_chat(chat):
    assert run_evals.score(chat, {"screen": "ok", "reply": "Sure!", "paused": False})["verdict"] == "fail"


def test_stub_run_passes_at_least_18_of_20():
    passed = [c["id"] for c in CHATS if run_evals.score(c, run_evals.run_chat(c))["verdict"] == "pass"]
    assert len(CHATS) == 20 and len(passed) >= 18, set(c["id"] for c in CHATS) - set(passed)
