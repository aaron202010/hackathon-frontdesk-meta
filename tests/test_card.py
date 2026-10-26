"""Stub mode tests for the HMO card flow: segment, read, POST /card, and the HMO on the next booking. No network."""
import glob, io, os, tempfile
os.environ["FRONTDESK_STUB"] = "1"
os.environ["FRONTDESK_DB"] = os.path.join(tempfile.mkdtemp(), "frontdesk.db")

import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app import card, clinic, model
from app.main import app, BLURRY_LINE

client = TestClient(app)
CARDS = sorted(glob.glob(os.path.join(card.CARDS_DIR, "*.jpg")))
PATIENTS = {p["id"]: p for p in clinic.CLINIC["patients"]}


@pytest.fixture(autouse=True)
def fresh_files(tmp_path, monkeypatch):
    monkeypatch.setattr(model, "TRACE", str(tmp_path / "trace.jsonl"))
    monkeypatch.setenv("FRONTDESK_DB", str(tmp_path / "frontdesk.db"))


def patient_for(path):
    return PATIENTS[os.path.basename(path).split("_")[0]]


def grey_jpeg():
    out = io.BytesIO()
    Image.new("RGB", (1200, 900), (128, 128, 128)).save(out, "JPEG")
    return out.getvalue()


def post_card(data, chat_id, name="photo.jpg"):
    return client.post("/card", data={"chat_id": chat_id}, files={"file": (name, data, "image/jpeg")})


def test_there_are_six_sample_cards():
    assert len(CARDS) == 6


@pytest.mark.parametrize("path", CARDS, ids=os.path.basename)
def test_segment_finds_the_card(path):
    im = Image.open(path)
    found = card.segment(open(path, "rb").read())
    b = found["box"]
    assert b["w"] * b["h"] >= 0.40 * im.width * im.height
    assert b["x"] >= 0 and b["y"] >= 0 and b["x"] + b["w"] <= im.width and b["y"] + b["h"] <= im.height
    assert Image.open(io.BytesIO(found["crop"])).size == (b["w"], b["h"])


@pytest.mark.parametrize("path", CARDS, ids=os.path.basename)
def test_read_card_matches_the_patient_row(path):
    p = patient_for(path)
    got = card.read_card(card.segment(open(path, "rb").read())["crop"])
    assert got["insurer"] == p["hmo"] and got["member_id"] == p["member_id"] and got["member_name"] == p["name"]
    assert got["valid_thru"] == "12/2027" and got["confidence"] == 0.9


def test_unknown_image_has_low_confidence():
    got = card.read_card(card.segment(grey_jpeg())["crop"])
    assert got["confidence"] < 0.5 and not any(got[f] for f in card.FIELDS)


def test_card_photo_names_the_insurer_and_sets_the_chat_hmo():
    path = next(p for p in CARDS if "demohealth" in p)
    out = post_card(open(path, "rb").read(), "c1", os.path.basename(path)).json()
    assert "DemoHealth" in out["reply"] and out["hmo"]["accepted"] is True and out["card"]["member_id"] == "DH-000002"
    assert "One cleaning a year" in out["reply"]
    assert card.saved_card("c1")["insurer"] == "DemoHealth"


def test_unlisted_card_gets_no_coverage_promise():
    path = next(p for p in CARDS if "notlisted" in p)
    out = post_card(open(path, "rb").read(), "c2").json()
    assert "NotListed HMO" in out["reply"] and "not on our accepted list" in out["reply"]
    assert out["hmo"]["accepted"] is False and "covered" not in out["reply"].lower()


def test_blurry_photo_gets_the_blurry_line():
    out = post_card(grey_jpeg(), "c3").json()
    assert out["reply"] == BLURRY_LINE and out["hmo"] is None
    assert card.saved_card("c3") is None


def test_not_an_image_is_a_400():
    assert post_card(b"not a picture", "c4").status_code == 400


def test_booking_after_a_card_carries_the_hmo():
    path = next(p for p in CARDS if "demohealth" in p)
    post_card(open(path, "rb").read(), "c5")
    out = client.post("/chat", json={"chat_id": "c5", "text": "Yes, book the 10:00 slot, Sample Patient Ben, 0917 000 0002, cleaning."}).json()
    assert out["booking"]["hmo"] == "DemoHealth"
    assert "HMO: DemoHealth, covered for" in out["reply"] and "clinic confirms by text" in out["reply"]


def test_booking_without_a_card_stays_cash():
    out = client.post("/chat", json={"chat_id": "c6", "text": "Yes, book the 10:00 slot, Sample Patient Ben, 0917 000 0002, cleaning."}).json()
    assert out["booking"]["hmo"] is None and "HMO: none, cash." in out["reply"]
