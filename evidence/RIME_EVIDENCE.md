# Rime Evidence

## Hard voice claim

Interrupting the agent stops speech immediately, cancels/fences any stale
SQL-RAG work in flight, and never lets the LLM or Rime speak content the
user didn't ask for or didn't hear -- verified by generation-ID fencing in
`backend/orchestrator.py`.

## Acceptance test (defined before the demo)

Introduce a fixed delay into the SQL-RAG tool call. While the agent is
speaking or the query is pending, interrupt and change part of the request
(e.g. "actually, what about the DHT22 instead"). Verify all five:

1. Queued Rime audio stops promptly
2. The updated instruction reaches the orchestrator
3. Stale SQL-RAG results are not spoken as current
4. Background DB work is cancelled or its result reconciled (fenced, not applied)
5. The final spoken response reflects exactly what the user actually heard + requested

## Procedure

Repeatable command: `python evidence/stress_test.py --n 10`

`stress_test.py` drives `backend/orchestrator.py` directly (no live mic or
VAD needed): it starts a normal turn, begins playback, then while a slow
(artificially delayed) background SQL-RAG call for the *original* turn is
still in flight, fires a simulated barge-in followed by a corrected
question. It asserts all five checkpoints above against the orchestrator's
return values and turn history, and logs a `fenced_drop` + per-run summary
event to Firestore telemetry for every run.

A live-mic confirmation pass (asking the same stress case out loud through
the real LiveKit/Deepgram/Rime pipeline) should be run once before the
recorded demo, per the limitation below -- the automated run is deliberately
non-mic so it stays fast and fully reproducible.

## Result

**Orchestrator dry run** (`python evidence/stress_test.py --n 10`, logic only,
no live LiveKit/Rime/Deepgram in the loop):

| metric | value |
|---|---|
| runs | 10 |
| fenced-drop count | 10/10 |
| avg time-to-stop-audio | ~151 ms (fixed by the scripted `BARGE_IN_AFTER_S` timing, not a real-world latency measurement) |
| correct-final-answer rate | 100% |

**Rime component verified live (2026-09-10):** a direct synthesis call to
`https://users.rime.ai/v1/rime-tts` (model `mistv2`, speaker `abbie`, lang
`eng`, 16kHz PCM) returned real audio, and `evidence/measure_wps.py` measured
**2.9491 words/sec** against it (written to `backend/measured_wps.txt`,
replacing the earlier 2.5 default).

**SQL-RAG component verified live (2026-09-10):** with a real Groq
(`openai/gpt-oss-20b`) key, `sql_rag_chain.answer("What is the operating
voltage of the DHT22?")` generated `SELECT operating_voltage FROM sensors
WHERE name='DHT22';`, ran it against the real seeded DB, and produced "The
DHT22 operates at 3.3 to 6 volts." -- correct, grounded, no hallucinated spec.

**Still not recorded: a live run through the actual LiveKit voice pipeline**
(real mic -> Deepgram -> orchestrator -> Rime, all wired together in one
session). Every component (Rime TTS + word-rate calibration, SQL-RAG +
LLM, and the fencing/truncation orchestrator logic) is now independently
verified live; the remaining gap is joining them in one LiveKit room with a
speaking participant, which needs `python backend/livekit_agent.py dev` plus
a client actually in the room -- that's the recorded demo itself. Re-run
`stress_test.py --n 10` after that session to pull real Firestore numbers
(`fenced_drop` count, `stress_test_run` timing, dashboard-observed
`active_speech_provider`) into this section.

## Limitations

- Truncation math assumes a roughly constant word-rate within an utterance
  and doesn't yet account for SSML pauses or punctuation-driven pacing.
- `time-to-stop-audio` in the table above is dominated by the stress test's
  own scripted delay constants, not a measurement of real LiveKit/Rime
  network latency -- the live-mic pass is what validates the real number.
- SQL allow-list covers 2 demo tables only (`sensors`, `actuators`).
- Fallback TTS path (`backend/fallback_tts.py`) has not yet been exercised
  against a real Rime outage -- only unit-level review.
