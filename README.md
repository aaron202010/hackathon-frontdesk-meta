# Front Desk on Meta models (hackathon build, HeyDenta module)

A Messenger-style front desk for Philippine dental clinics: a patient writes in Taglish, the bot answers from a fake clinic's
schedule and services, reads a photo of an HMO card (SAM 3.1 crops the card, a Muse model reads the fields), checks it against
the clinic's accepted list, and books. Hard lines: no diagnosis, no treatment advice, emergencies get the clinic phone, staff can
take over any chat.

Built for the Meta Global AI Developer Hackathon (startup track, "Build for Your World"), Oct 26 to Nov 4, 2026 ET.
New code written inside the window. Fake clinic, fake patients, fake HMO cards marked SAMPLE. No HeyDenta code, keys, prompts
or patient data in this repo.

Status: day 3, chat loop scaffold. See docs/SPEC.md, docs/PLAN.md and docs/CHECKS.md.

## Run it

```
make test   # pytest in stub mode, no key, no network
make dev    # http://localhost:8000, the Messenger-style chat page
```

Stub note: with no `MODEL_API_KEY` in the shell, or with `FRONTDESK_STUB=1`, the model behind `app/model.py:complete()` is a
deterministic rule stub (prices, hours, slots, HMO checks, bookings from the fake data), so the app and the tests run with no
network. Set `MODEL_API_KEY` (and optionally `FRONTDESK_MODEL`, default `muse-spark-1.3`) to call the Meta Model API. Every
model call, stub or live, writes one line to `logs/trace.jsonl`. Bookings and chat turns live in `data/frontdesk.db` (SQLite,
ignored by git).
