"""The built-in reply check: prices, dates and times must come from the tools, the chat or the clinic facts; two retries, then staff."""
import os, tempfile
os.environ["FRONTDESK_STUB"] = "1"
os.environ.setdefault("FRONTDESK_DB", os.path.join(tempfile.mkdtemp(), "frontdesk.db"))

from app import agent, clinic, model, verify

G = clinic.CLINIC["guardrails"]
TOOL_LINE = "Open slots: Thursday 2026-10-29 09:30 with Dr. Sample Santos."


def test_backed_values_pass_and_invented_ones_are_named():
    assert verify.check("We have Thursday 2026-10-29 at 9:30 AM. Cleaning starts at 1,000 pesos.", [TOOL_LINE]) == []
    misses = verify.check("Friday 2026-10-30 at 3:00 PM works, and cleaning is P1,750.", [TOOL_LINE])
    assert misses == ["date 2026-10-30", "time 15:00", "price 1,750 pesos"]


def test_a_phone_number_and_the_clinic_hours_are_not_misread():
    assert verify.check("Call us at 0917 000 0000, we're open 09:00-18:00 on Monday.", []) == []


def fake_model(replies):
    it = iter(replies)
    def complete(messages, tools=None, response_format=None):
        return {"content": next(it), "tool_calls": [], "mode": "stub", "ms": 1, "usage": {}}
    return complete


def test_a_miss_goes_back_to_the_model_and_the_fixed_reply_is_sent(monkeypatch):
    monkeypatch.setattr(model, "complete", fake_model(["Cleaning is 1,750 pesos.", "Cleaning starts at 1,000 pesos."]))
    out = agent.handle("verify-1", "how much is cleaning")
    assert out["reply"] == "Cleaning starts at 1,000 pesos."
    labels = [s["label"] for s in out["steps"]]
    assert any(l.startswith("Reply check: not backed") for l in labels) and labels[-1].startswith("Reply check: every price")
    assert not agent.is_paused("verify-1")


def test_three_misses_hand_the_chat_to_staff(monkeypatch):
    monkeypatch.setattr(model, "complete", fake_model(["It is 1,750 pesos."] * 3))
    out = agent.handle("verify-2", "how much is cleaning")
    assert out["reply"] == G["verify_handoff_reply"] and agent.is_paused("verify-2")
