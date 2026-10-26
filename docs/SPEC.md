# Spec: Front Desk on Meta models (hackathon, startup track)
Date: 2026-10-26 (day 1, PHT). From the chat lane plan /root/creative-out/chat-lane/hackathon-plan-meta-2026-10-26.md and Aaron's order in #therapy (02:58 UTC): startup track, new repo, fake data only, test one Muse Spark call, one vision call and one SAM 3.1 call, then the spec and checks table. The three test calls wait on Aaron's API access from the approval email (no Meta key on this box on day 1).

## 1. What it is
A Messenger-style front desk for a Philippine dental clinic, built on Meta models. One chat loop: Taglish question in, answer from the clinic's facts and schedule, HMO card photo read and checked, booking held, staff takeover. Framed as a HeyDenta module for the startup track; the repo is new code written inside the window with fake data only.

## 2. Flows
1. Chat: patient message (Taglish or English) -> Muse Spark answers from clinic facts (services, hours, price ranges) and offers open slots from the fake schedule. Never invents a slot.
2. HMO card: patient sends a card photo -> SAM 3.1 segments and crops the card (text prompt "ID card") -> a Muse vision call reads insurer, member name, member id, validity -> the bot checks the insurer against the clinic's accepted list -> says covered or not covered or "the clinic confirms", then continues to booking.
3. Booking: name, mobile, service, slot -> a booking row in the fake store -> a summary (date, time, service, HMO status) -> "the clinic confirms by text".
4. Guardrails: no diagnosis, no treatment or medicine advice; emergency words route to the clinic phone first; off topic steered back; staff takeover command pauses the bot for that chat.
5. Failure paths: model call fails -> honest line plus staff handoff; blurry card -> ask for a clearer photo; unknown HMO -> "the clinic confirms", never a coverage promise.

## 3. Stack (day 1 draft, confirmed on day 2 once the API is in hand)
- Python 3.12, FastAPI, one process; SQLite fake store; a web chat page that looks like Messenger (fallback if a test Facebook page needs app review, said plainly in the write-up).
- Meta models through the Meta Model API or a partner endpoint (Baseten, Modal or Fireworks credits for select participants). Muse Spark for chat and card reading; SAM 3.1 for the card crop.
- Deploy: a live URL on day 5 (Vercel or Fly), logs and a trace per chat.

## 4. Fake data (day 2)
Clinic "Bright Smile Dental Clinic" facts (address, phone, hours), 8 services with price ranges, a 7 day schedule with open and taken slots, an accepted HMO list of 5 insurers, 6 fake patients, 6 sample HMO cards rendered by us with the word SAMPLE on each.

## 5. Eval (day 6)
20 Taglish chats with expected outcomes, the 10 iFixAi-style inspections mapped for the hackathon bot in the chat lane's map, judge on a different provider than the agent, pass rate in the README; reply time measured per turn.

## 6. Out of scope
Real patients, real clinics, HeyDenta code or prompts, payments, reminders, voice.

## 7. Day plan (PHT) and checks
See docs/CHECKS.md. Day 1 = scaffold, spec, checks, three test calls (blocked on the key). Day 2 fake data. Day 3 chat loop. Day 4 card flow. Day 5 booking, takeover, guardrails, live URL. Day 6 eval. Day 7 demo video. Day 8 write-up. Day 9 submit by 22:00 PHT Nov 4.

## 8. What would prove this wrong
1. Muse Spark weak at Taglish: 10 test chats on the day the key arrives; if under 7 of 10 read right, switch the chat model to an open-weights Llama through the same partner endpoint and say so.
2. SAM 3.1 or a Muse vision model not reachable with the credits: the card flow falls back to the vision model's own crop, or to a plain OCR step, and the write-up says which.
3. Startup track needs an employee letter: Aaron is the sole proprietor (DTI 8234385); if the organizers want more, the indie track is the fallback.
