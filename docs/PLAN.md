# Day plan, updated 2026-10-27 00:35 PHT after the kickoff livestream (Aaron "plan update")

Source: the chat lane's plan of 2026-10-26 (/root/creative-out/chat-lane/hackathon-plan-meta-2026-10-26.md) plus the kickoff transcript (/root/creative-out/research/videos/2026-10-27_web_zY5S8R9xMnPitNXzLR22.txt). Deadline: Nov 4 9:00 PM ET = Nov 5 10:00 AM PHT. We submit by Nov 4 22:00 PHT, 12 hours early.

## What changed after the kickoff
1. Credits come through forms on the event details page (info icon on the Cerebral Valley event page): Meta 150 USD, Modal 100 USD, Fireworks 25 USD, handed out in batches. Fill the Meta form first; the API key comes from dev.meta.ai after that.
2. "Medical advice generators" sit on the organizers' avoid list with chat wrappers, simple RAG apps and image analyzers. The bot never answers a health question; the demo shows it refusing one and handing off, and shows the real work (HMO card read with SAM 3.1, slot offer, booking, staff takeover).
3. Startup track = incorporated startup with an existing team. Aaron is a sole proprietor (DTI 8234385). Ask in Meta office hours on day 2 whether that counts; if not, ask to move to indie before building further.
4. The 3 minute demo video is what the judges watch live on Nov 9. Two days go to it, not one. Voiceover, the bot in action, the problem first.
5. New work only, public GitHub repo, a readme line that says every commit is from the window.
6. Bonus prizes we can aim at without extra build: best agentic use case (5k), best build on Meta open weights (Muse Spark), community vote (project gallery, Nov 16), most viral (one post on X, link in the form).

## Days (PHT)
1. Tue Oct 27 (today): credit forms (Meta, Modal, Fireworks). Key into /root/.creds/meta-model-api.env, "key in". Three test calls: Muse Spark chat in Taglish, a vision call on a sample HMO card, SAM 3.1 crop. Ten Taglish test chats to judge Muse Spark's Taglish. Read the submission form on the event page and copy its fields into docs/SUBMISSION.md.
2. Wed Oct 28: Meta engineering workshop part 1 at 00:00 PHT (noon ET Tuesday). Office hours question: sole proprietorship on the startup track. Fake clinic data: schedule, services, price ranges, accepted HMO list, 6 sample HMO cards marked SAMPLE.
3. Thu Oct 29: workshop part 2 at 00:00 PHT. Chat loop: webhook, Muse Spark replies in Taglish, slot offer from the schedule, booking written to the fake calendar.
4. Fri Oct 30: HMO card flow: SAM 3.1 crop, field read, coverage check against the accepted list. Fireworks workshop (time on the event page).
5. Sat Oct 31: guardrails: no diagnosis, no treatment advice, emergency gets the clinic number, staff takeover; error handling for a failed model call, a blurry card, an unknown HMO; logs and a trace per chat.
6. Sun Nov 1: live URL (not localhost). Eval set of 20 Taglish chats with a pass rate in the README. Reply time measured and shown. US clocks change today: ET becomes UTC minus 5.
7. Mon Nov 2: video day 1: script, screen recording on a phone of one real chat start to booking plus the refusal and handoff, under 3 minutes.
8. Tue Nov 3: video day 2: voiceover, captions, cut, one review pass, upload. Write-up, README, architecture diagram.
9. Wed Nov 4: submit by 22:00 PHT (form, public repo, video, the X post link for the viral prize, the bonus prize boxes). Buffer for breakage.

## Hard lines (unchanged)
New repo, fake data only, no HeyDenta code, keys, prompts or patient data. No clinic users or results claimed in the write-up. Every spoken line in the video is ours. The checks table at /root/.claude/os/checks/CHECKS-hackathon-meta-day1-2026-10-26.md grows one table per day.

## What would prove this plan wrong
1. Muse Spark is weak at Taglish: the 10 test chats on day 1 decide; fallback is English with Taglish greetings only.
2. The sole proprietorship does not qualify for the startup track: the office hours answer on day 2 decides; fallback is the indie track with the same build.
3. Credits arrive late (batches): day 1 test calls wait; the fake data and the chat loop scaffold go first.
