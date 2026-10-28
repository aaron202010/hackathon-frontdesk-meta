# Code review by Muse Code (Meta's coding agent)

Run: 2026-10-28 20:20 UTC, Muse Code 1.4.14, `muse exec` headless on a throwaway clone of this repo, sandbox on, network
restricted, web tools off, every shell command gated (`--approval-mode untrusted`); it changed no file (git status clean after).
Model: Muse Spark through the Meta Model API. Role: reviewer only; the builder was a different agent (Claude), following the
"one session builds, one only reviews" practice from Meta's Agents 102 workshop.

The prompt asked for real bugs only, with file:line and a failing input. Its review is below, word for word, then what we did
with each finding.

## The review, verbatim

## app/verify.py + model_turn in app/agent.py

- `app/verify.py:8` / `app/verify.py:12` — high — bare-hour times are never checked because `TIME` requires a colon, so a reply like `See you Saturday at 3pm` passes with zero misses.
- `app/verify.py:9` / `app/verify.py:47` — high — a price without a currency marker is never checked, so `Cleaning is 1200` yields no miss even when no tool returned it.
- `app/verify.py:7` / `app/verify.py:44` — medium — only `YYYY-MM-DD` counts as a date, so `See you on Nov 9` or `this Saturday` passes unbacked.
- `app/verify.py:46-47` — medium — any price equal to any number anywhere in the sources is accepted, so `X-ray 14 pesos` passes because `14` appears in hours `09:00-14:00` in `clinic_facts()`.
- `app/agent.py:155` — medium — the retry loop is `range(MAX_TOOL_ROUNDS + MAX_REPLY_RETRIES)` = 6 shared by tool rounds and reply retries, so 4 tool calls followed by 2 missed replies exhausts the loop and returns the generic error line without pausing, instead of the specified pause-after-2-retries.
- `app/agent.py:158-159` — medium — a `ModelError` returns `model_error_reply` with no `set_paused(True)`, so killing the network / an invalid key in live mode never hands the chat to staff despite the docstring's "plus the staff handoff".

## app/voice.py + POST /voice in app/main.py

- `app/voice.py:17-18` + `app/main.py:101-102` — medium — `FileNotFoundError` (no ffmpeg binary) and `TimeoutExpired` (60 s) from `subprocess.run` are not `ValueError`, so POST /voice with a valid webm returns 500 instead of 400 when ffmpeg is missing or hangs.
- `app/main.py:106-108` — low — an empty transcript returns early without `save_turn`, so a failed voice attempt leaves no trace row while typed turns are all stored.
- Command injection: no finding (argument list, no shell).

## app/staff.py + /staff routes

- `app/main.py:112-117` — high — `GET /trace/{chat_id}` needs no key and returns full turn contents, so `POST /chat` with `Book for Maria, 0917 123 4567 ...` then `GET /trace/<same chat_id>` from another client leaks the name and mobile; chat IDs are client-chosen, not secrets.
- `app/main.py:128-133` — medium — `/staff/data` has no `rate_limit` dependency, so `GET /staff/data?key=<guess>` can be brute-forced with no 429 ever.
- `app/staff.py:96` — low — `takeovers` truncates to `chat_id[:8]`, so two chats sharing an 8-char prefix are indistinguishable to staff.
- Key compare itself (`app/staff.py:15-22`): no finding.

## Rate limit in app/main.py

- `app/main.py:26` — medium — `int(os.environ.get("FRONTDESK_RATE", ...) or 0)` is unhandled, so `FRONTDESK_RATE=abc` makes every `/chat`, `/card`, `/voice` call 500.
- `app/main.py:29` — medium — identity is only `request.client.host`, so behind one reverse proxy every visitor shares one bucket and one user's burst 429s everyone else.
- Missing `Retry-After` on 429: no finding beyond low (omitted for brevity).

## evals/run_evals.py and evals/run_voice_evals.py

- `evals/run_evals.py:92` — medium — `rule_booking` requires the reply to *not* contain `booking held`, but `app/clinic.py:243` makes every real booking summary start `Booking held for ...`, so a correct full-booking reply with mobile + `confirms by text` fails.
- `evals/run_evals.py:87` — medium — `open_set` ignores real bookings and `is_past`, so an agent offering a just-booked or past slot still passes the "not open" check (eval blind to double-booking).
- `evals/run_evals.py:164` — low — the judge parses with greedy `re.search(r"\{.*\}", ..., re.S)`, so a judge answer with two JSON objects or braces in prose spans first-`{` to last-`}` and fails to `json.loads` into a spurious `error`.
- `evals/run_voice_evals.py:22` — low — stub `transcribe` reads words from `hint=n["said"]`, so any garbage audio with the expected filename scores word_match ≈ 1.0 by construction (disclosed plumbing check, not accuracy).
- `evals/run_voice_evals.py:25` — low — `res` hardcodes `"paused": False`, so a voice note tagged `takeover` that correctly pauses still fails `rule_takeover`.

Overall verdict: real high-severity holes in reply verification (bare times, markerless prices) and public chat-history exposure via /trace, plus a self-failing booking rule — fix those before any public demo.


## What we did with each finding

| # | Finding | Verdict | What changed |
|---|---|---|---|
| 1 | bare hours like "3pm" never checked | real, fixed | app/verify.py checks bare hours ("3pm", "10 AM") |
| 2 | a price without a peso sign never checked | real, fixed | any amount from 100 to 100,000 left after dates, times, phones and IDs must come from the sources |
| 3 | month-name dates ("Nov 9") never checked | real, fixed | month and day must match a date in the sources; relative words ("this Saturday") stay unchecked |
| 4 | any number in the sources backed a price ("14 pesos" from 09:00-14:00) | real, fixed | a price is backed only by a peso amount in the sources or the clinic's price list |
| 5 | tool rounds and reply retries shared one loop | real, fixed | counted apart; too many tool rounds also hands the chat to staff |
| 6 | a model error did not pause the chat though the line says staff continues | real, fixed | the chat is paused, so the line is true |
| 7 | a hung ffmpeg gave a 500 | real, fixed | a timeout is a bad file (400); a missing ffmpeg stays a server error on purpose |
| 8 | an empty voice note left no trace row | real, fixed | both turns are saved |
| 9 | GET /trace read any chat with no key | real, high, fixed | /trace needs the staff key |
| 10 | /staff/data has no rate limit, key brute force | not changed | the key is 96 random bits (secrets.token_urlsafe(12)); guessing is not practical |
| 11 | takeover list shows chat_id[:8] | not changed | by spec, collisions shown to staff are rare and harmless |
| 12 | FRONTDESK_RATE=abc fails every call | real, fixed | a bad value falls back to the default |
| 13 | all visitors share one rate bucket behind the proxy | not a bug here | uvicorn runs with --proxy-headers and Traefik connects from 127.0.0.1, so the client address is the visitor's |
| 14 | rule_booking fails every real booking | not a bug | that branch is the slot-offer case; a message with a mobile takes the booking branch, which checks "confirms by text" |
| 15 | the slot rule ignored bookings and past slots | real, fixed (stricter check) | the eval's open set is now clinic.open_slots, which drops booked and past slots |
| 16 | the judge's JSON parse was greedy | real, fixed | it reads the first JSON object |
| 17 | voice stub scores 1.0 by construction | known, disclosed | the stub run is a plumbing check and writes no result |
| 18 | voice evals hardcoded paused = False | real, fixed | reads the real paused state |

After the fixes: 75 tests pass; live evals 20 of 20 by rules and 20 of 20 by the judge (16 chats through the reply check, 0
retries); voice notes 5 of 5.
