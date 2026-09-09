# Demo script (4-5 min)

Mapped to the judging rubric (architecture §0): problem/necessity of voice
25%, hard voice engineering 25%, Rime integration 20%, evidence/reproducibility
20%, demo clarity 10%.

## 0:00-0:30 -- Who and why
State the user: a technician in a mechatronics lab, hands full with hardware,
can't look at a screen or type. Voice is the only channel that works here.

## 0:30-1:30 -- Normal end-to-end flow
Ask a spec question out loud (e.g. "What's the measurement range of the
HC-SR04?"). Show the full loop: mic -> Deepgram STT -> SQL-RAG over
`sensors`/`actuators` -> Rime-spoken answer.

## 1:30-3:00 -- The deliberate stress case
Interrupt the agent mid-answer and change the request (e.g. "actually, what
about the DHT22 instead"). On the dashboard, show in real time:
- the stale SQL-RAG result being fenced/dropped (`fenced_drop` event)
- the corrected answer being spoken instead, reflecting only what was asked

## 3:00-3:30 -- Active speech provider
Point at the dashboard's `active_speech_provider` indicator -- Rime by
default, or the disclosed fallback if it was triggered during the demo.

## 3:30-4:30 -- Evidence
Show the measured result from `evidence/RIME_EVIDENCE.md` / a live run of
`python evidence/stress_test.py --n 10`: fenced-drop count, time-to-stop-audio,
correct-final-answer rate.

## 4:30-5:00 -- Limitations and what's next
One line on limitations (truncation assumes constant word-rate, 2-table
allow-list) and, if shipped, what P1 (vector RAG over manuals) adds.
