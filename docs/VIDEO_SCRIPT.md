# Demo video: script and shot list (v7, 2026-10-29)

Target: under 3 minutes (docs/PLAN.md item 4). One video, about 2:09. Every spoken line is Aaron's own. Built by video/assemble.py
(local only, the raw footage stays out of the repo).

| # | Time | Shot | On screen |
|---|---|---|---|
| 1 | 0:00 to 0:28 | Aaron on camera, background blurred, his words as captions, opening on the problem ("My friend is a dentist...") | 0:00 to 0:03 hook card "2.6 dentists for every 10,000 Filipinos", "3 in 10 people aged 5 and up have untreated tooth decay, WHO"; 0:03 to 0:08 name card |
| 2 | 0:42 to 0:47 | title card | "11:40 PM. The clinic is closed. A patient sends a message." |
| 3 | 0:46 to 2:11 | live app recording: typed HMO question, card photo, a voice note (the patient's own voice is heard), booking, medical question, staff takeover, then the staff view | numbered step bands 1/6 Ask, 2/6 Card, 3/6 Voice, 4/6 Book, 5/6 Medical, 6/6 Staff; the proof line in the steps panel outlined in blue, including the reply check |
| 3b | 1:57 to 2:02 | proof card | 76 tests, 20 of 20 test chats (rules and a second model), 5 of 5 voice notes, Muse Code review 18 found 13 fixed |
| 4 | 2:02 to 2:09 | end card | Muse Spark, SAM 3.1, Muse Voice, Muse Code; 20 of 20 test chats checked by rules and a second model; fake data; "Try the live demo", the link and a QR code |

Sound (v5, Aaron 2026-10-28 "background sounds or sound effects wala", "use this voice"): Aaron's own voice only under his clip;
the app part has a voiceover in Ava (en-US-AvaNeural, the voice of the 2026-06-11 HeyDenta promo reel), lines in docs/VOICEOVER.md,
one per step; a calm music bed made for this video from the title card to the end, pressed down under the voiceover; soft cues
(send, receive, card scan, booking confirm, a calm tone on the medical refusal) about 10 dB under the voice.

Checks before a cut is sent: every word in the recorded chat and panel is scanned for Tagalog (video/lang_scan.py), the QR code is
decoded, the test patient number is an obviously fake one (0900 000 0001). Waits for model replies are never cut to fake speed; the
panel shows the real timings.
