"""The per-visitor cap on the calls that spend model credits."""
import os, tempfile
os.environ["FRONTDESK_STUB"] = "1"
os.environ.setdefault("FRONTDESK_DB", os.path.join(tempfile.mkdtemp(), "frontdesk.db"))

from fastapi.testclient import TestClient
from app import main

client = TestClient(main.app)


def test_the_cap_answers_429_with_a_plain_line_and_stub_mode_is_uncapped(monkeypatch):
    main._hits.clear()
    monkeypatch.setenv("FRONTDESK_RATE", "3")
    codes = [client.post("/chat", json={"chat_id": "rate-1", "text": "how much is a cleaning"}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]
    assert client.post("/chat", json={"chat_id": "rate-1", "text": "hi"}).json()["detail"] == main.BUSY_LINE
    monkeypatch.delenv("FRONTDESK_RATE")
    main._hits.clear()
    assert all(client.post("/chat", json={"chat_id": "rate-2", "text": "hi"}).status_code == 200 for _ in range(50))
