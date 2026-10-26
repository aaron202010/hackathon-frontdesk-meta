"""Day 1 test calls on the Meta Model API: one Muse Spark chat in Taglish, one image read of a SAMPLE HMO card, one SAM 3.1
segmentation of the card. Reads MODEL_API_KEY from /root/.creds/meta-model-api.env in process (never printed). Saves each
request (key stripped) and response under evals/day1/. Usage: python3 -I scripts/day1_calls.py [chat|vision|sam|all]
Docs read 2026-10-26: https://dev.meta.ai/docs/overview.md and image-understanding.md (base https://api.meta.ai/v1, Bearer key,
/v1/chat/completions and /v1/responses, images as data URLs in input_image or image_url blocks, SAM 3.1 model id sam-3.1)."""
import base64, json, os, re, sys, time, urllib.request
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(HERE, "evals", "day1"); os.makedirs(OUT, exist_ok=True)
BASE = "https://api.meta.ai/v1"
env = open("/root/.creds/meta-model-api.env").read()
KEY = re.search(r"^MODEL_API_KEY=(.*)$", env, re.M).group(1).strip().strip('"').strip("'")
CARD = os.path.join(HERE, "data", "sample_cards", "sample-card-01.jpg")
def data_url(path):
    return "data:image/jpeg;base64," + base64.b64encode(open(path, "rb").read()).decode()
def post(path, body, name):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read()); status = r.status
    except urllib.error.HTTPError as e:
        resp = {"http_error": e.code, "body": e.read()[:2000].decode(errors="replace")}; status = e.code
    ms = int((time.time() - t0) * 1000)
    saved = {"endpoint": path, "model": body.get("model"), "ms": ms, "status": status, "request": _strip(body), "response": resp}
    json.dump(saved, open(os.path.join(OUT, name + ".json"), "w"), indent=1)
    print(f"{name}: http {status} in {ms} ms -> evals/day1/{name}.json"); return resp
def _strip(body):
    s = json.dumps(body)
    return json.loads(re.sub(r'data:image/[a-z]+;base64,[A-Za-z0-9+/=]+', 'data:image/jpeg;base64,<stripped>', s))
def chat():
    r = post("/chat/completions", {"model": "muse-spark-1.3", "temperature": 0.3, "max_tokens": 300, "messages": [
        {"role": "system", "content": "You are the front desk of Bright Smile Dental Clinic in Makati. Answer in the patient's language (Taglish when they write Taglish), short, friendly. Services: cleaning starts at 1,000 pesos, extraction starts at 1,500, filling price on request. Open Mon to Sat 9 AM to 6 PM. Never give medical advice; emergencies call (02) 8123 4567."},
        {"role": "user", "content": "Hi po, magkano ang cleaning? Pwede ba bukas ng hapon, around 2pm?"}]}, "chat_muse_spark")
    try: print("  reply:", r["choices"][0]["message"]["content"][:300].replace("\n", " "))
    except Exception: print("  reply: see file")
def vision():
    r = post("/responses", {"model": "muse-spark-1.3", "input": [{"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": "This is a SAMPLE HMO card used for a software demo. Read it and answer with one JSON object only: {\"insurer\": ..., \"member_name\": ..., \"member_id\": ..., \"valid_thru\": ..., \"plan\": ...}. Use null for anything unreadable."},
        {"type": "input_image", "image_url": data_url(CARD)}]}]}, "vision_card_read")
    print("  reply:", json.dumps(r)[:400])
def sam():
    # SAM 3.1 on the Model API: model id sam-3.1 through /v1/responses with the image and a text prompt (shape per the overview;
    # the dedicated SAM page was a 404 on 2026-10-26, so the request body is the image-understanding shape until the page is read).
    r = post("/responses", {"model": "sam-3.1", "input": [{"type": "message", "role": "user", "content": [
        {"type": "input_text", "text": "ID card"}, {"type": "input_image", "image_url": data_url(CARD)}]}]}, "sam_card_segment")
    print("  reply:", json.dumps(r)[:400])
which = sys.argv[1] if len(sys.argv) > 1 else "all"
for name, fn in (("chat", chat), ("vision", vision), ("sam", sam)):
    if which in (name, "all"): fn()
