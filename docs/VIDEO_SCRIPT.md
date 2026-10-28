# Demo video: script and shot list (recut, 2026-10-28)

Target: under 3 minutes (docs/PLAN.md item 4). One video, about 2:18. Every spoken line is Aaron's own. Built by video/assemble.py
(local only, the raw footage stays out of the repo).

| # | Time | Shot | On screen |
|---|---|---|---|
| 1 | 0:00 to 0:42 | Aaron on camera, background blurred, his words as captions | 0:00 to 0:03 hook card "20 of 20 test chats passed"; 0:03 to 0:08 name card |
| 2 | 0:42 to 0:47 | title card | "11:40 PM. The clinic is closed. A patient sends a message." |
| 3 | 0:46 to 2:11 | live app recording: typed HMO question, card photo, a voice note (the patient's own voice is heard), booking, medical question, staff takeover, then the staff view | numbered step bands 1/6 Ask, 2/6 Card, 3/6 Voice, 4/6 Book, 5/6 Medical, 6/6 Staff; the proof line in the steps panel outlined in blue, including the reply check |
| 4 | 2:11 to 2:18 | end card | Muse Spark, SAM 3.1, Muse Voice, Muse Code; 20 of 20 test chats checked by rules and a second model; fake data; "Try the live demo", the link and a QR code |

Sound (v5, Aaron 2026-10-28 "background sounds or sound effects wala", "use this voice"): Aaron's own voice only under his clip;
the app part has a voiceover in Ava (en-US-AvaNeural, the voice of the 2026-06-11 HeyDenta promo reel), lines in docs/VOICEOVER.md,
one per step; a calm music bed made for this video from the title card to the end, pressed down under the voiceover; soft cues
(send, receive, card scan, booking confirm, a calm tone on the medical refusal) about 10 dB under the voice.

Checks before a cut is sent: every word in the recorded chat and panel is scanned for Tagalog (video/lang_scan.py), the QR code is
decoded, the test patient number is an obviously fake one (0900 000 0001). Waits for model replies are never cut to fake speed; the
panel shows the real timings.
