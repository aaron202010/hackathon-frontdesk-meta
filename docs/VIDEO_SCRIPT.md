# Demo video: script and shot list (v4, 2026-10-28)

Target: under 3 minutes (docs/PLAN.md item 4). One video, about 2:08. Every spoken line is Aaron's own. Built by video/assemble.py
(local only, the raw footage stays out of the repo).

| # | Time | Shot | On screen |
|---|---|---|---|
| 1 | 0:00 to 0:42 | Aaron on camera, background blurred, his words as captions | 0:00 to 0:03 hook card "20 of 20 test chats passed"; 0:03 to 0:08 name card |
| 2 | 0:42 to 0:47 | title card | "11:40 PM. The clinic is closed. A patient sends a message." |
| 3 | 0:47 to 2:01 | live app recording, zoom on the chat while the patient types, pull back to chat plus steps after each reply | numbered step bands: 1/5 Ask, 2/5 Card, 3/5 Slots, 4/5 Book, 5/5 Medical, Staff takeover; the proof line in the steps panel outlined in blue |
| 4 | 2:01 to 2:08 | end card | models used, 20 of 20 test chats, fake data, "Try the live demo", the link and a QR code |

Sound (v5, Aaron 2026-10-28 "background sounds or sound effects wala", "use this voice"): Aaron's own voice only under his clip;
the app part has a voiceover in Ava (en-US-AvaNeural, the voice of the 2026-06-11 HeyDenta promo reel), lines in docs/VOICEOVER.md,
one per step; a calm music bed made for this video from the title card to the end, pressed down under the voiceover; soft cues
(send, receive, card scan, booking confirm, a calm tone on the medical refusal) about 10 dB under the voice.

Checks before a cut is sent: every word in the recorded chat and panel is scanned for Tagalog (video/lang_scan.py), the QR code is
decoded, the test patient number is an obviously fake one (0900 000 0001). Waits for model replies are never cut to fake speed; the
panel shows the real timings.
