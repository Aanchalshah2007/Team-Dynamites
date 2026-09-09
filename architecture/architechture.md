# Mechatronics Lab Voice Assistant — Build Architecture (for Claude Code)

## 0. Scope discipline (read first)

This submission is judged on ONE hard voice problem, not breadth. Judging weights:
Problem/necessity of voice 25% · Hard voice engineering 25% · Rime integration 20% ·
Evidence/reproducibility 20% · Demo clarity 10%.

**Chosen hard voice problem (do not dilute):** Interruption & recovery, combined with
conversation continuity during tool work (SQL-RAG lookups).

**Build order — P0 must be fully working + evidenced before touching P1/P2:**
- **P0 (core, judged path):** LiveKit voice pipeline, barge-in handling, generation-ID
  fencing, audio-truncation, SQL-RAG over hardware specs, RIME_EVIDENCE.md + stress test.
- **P1 (only if P0 is solid and evidenced):** Vector RAG over manuals for procedural
  questions — same fencing rules apply, no separate acceptance test needed, folds into
  "conversation continuity during tool work."
- **P2 (stretch, cut without guilt):** Multi-step reservation/checkout with two-phase
  commit. This is a transactional-systems feature, not a voice-engineering one — it will
  not move the "hard voice engineering" score and should only be attempted if P0 and P1
  are demo-ready with time to spare.

Do not let P2 show up in the demo instead of a clean P0 demonstration.

---

## 1. Repository layout

```
repo/
├── README.md                      # setup, architecture, services, limitations, failure behavior, exact Rime config
├── RIME_EVIDENCE.md               # claim, acceptance test, procedure, result, limitations
├── .env.example                   # placeholders only — RIME_API_KEY=, DEEPGRAM_API_KEY=, LLM_API_KEY=, FIREBASE_*
├── backend/
│   ├── livekit_agent.py           # LiveKit Agents entrypoint (VAD, turn handling, barge-in)
│   ├── orchestrator.py            # generation-ID fencing, audio-truncation, turn state machine
│   ├── sql_rag_chain.py           # NL -> validated SELECT-only SQL -> DB -> answer text
│   ├── vector_rag_chain.py        # (P1) embeddings + retrieval over manual PDFs
│   ├── seed_demo_db.py            # seeds sensors/actuators tables
│   ├── config.py                  # loads env, exposes ALLOWED_TABLES, RIME config constants
│   └── requirements.txt
├── evidence/
│   ├── RIME_EVIDENCE.md           # (duplicate/link ok — organizers want it discoverable)
│   ├── measure_wps.py             # calibrates words-per-second for truncation math
│   └── stress_test.py             # scripted, reproducible interruption stress test (no mic needed)
├── dashboard/
│   ├── package.json
│   └── src/...                    # Next.js live telemetry view backed by Firestore
└── docs/
    └── demo_script.md             # 4-5 min recording script mapped to rubric
```

---

## 2. Core pipeline (P0)

```
Mic (hands-busy user)
  → LiveKit Agents: WebRTC transport, Silero VAD, barge-in detection
  → Deepgram STT
  → orchestrator.py
       - every user turn gets a monotonic generation_id
       - any SQL-RAG result that resolves under a stale generation_id is dropped,
         never passed to the LLM or TTS
       - on barge-in: elapsed_playback_seconds × measured_words_per_second =
         words actually heard; conversation history is sliced to exactly that
         point and tagged [interrupted]; nothing past that point is treated
         as something the user heard
       - the orchestrator keeps accepting new user turns while Rime is
         speaking and while sql_rag_chain.py is still running — that's the
         part the generation-ID fencing exists to make safe
  → LLM: turn reasoning, SQL generation, answer formatting (never reasons
    over unplayed/dropped content)
  → Rime TTS (LiveKit's official Rime plugin) → playback
  → Telemetry → Firebase Firestore → Next.js dashboard
```

### 2.1 Generation-ID fencing — implementation contract
- `orchestrator.py` holds `current_generation_id` (int, monotonic, incremented on
  every new user utterance that starts while the system is speaking or working).
- Every async task (SQL query, LLM call) is launched with the generation_id it was
  created under.
- On completion, the task checks `if task.generation_id != orchestrator.current_generation_id: discard()`.
- Discarded results are logged to Firestore as `{event: "fenced_drop", stale_gen, current_gen, ts}`
  — this is what proves the claim in RIME_EVIDENCE.md.

### 2.2 Audio-truncation contract
- `measure_wps.py` (in `evidence/`) runs a calibration pass against the exact Rime
  voice/model used in the demo and writes a measured words-per-second constant —
  do not hardcode an assumed value.
- On barge-in: `words_heard = elapsed_playback_seconds * measured_wps`; slice the
  assistant's last utterance to that word count; tag the truncated remainder
  `[interrupted]` in conversation history so the LLM never treats unheard text as
  something the user has context on.
- Known limitation to disclose (per README rules): this assumes roughly constant
  word-rate within an utterance and doesn't yet account for SSML pauses or
  punctuation-driven pacing.

### 2.3 SQL-RAG (`sql_rag_chain.py`)
- NL query → LLM generates SQL restricted to `ALLOWED_TABLES = ["sensors", "actuators"]`.
- Validate: SELECT-only, no DDL/DML, no tables outside allow-list → else raise
  `UnsafeSQLError`.
- On `UnsafeSQLError` or DB error: the agent **says so aloud** — never stays silent,
  never guesses at a hardware spec (per Failure Behavior rule).
- Extending the schema = update `ALLOWED_TABLES` (document this in README's Known
  Limitations, since it's a real scaling constraint).

---

## 3. Rime integration — fields to finalize before submission

Fill this table with a combination you have **actually tested end-to-end**, pulled
from Rime's live model/voice/language catalog at submission time (not a cached list):

| Field | Value |
|---|---|
| Model ID | *(exact, e.g. mistv2)* |
| Speaker | *(exact voice name)* |
| Language | *(e.g. eng)* |
| Endpoint / region | *(exact endpoint)* |
| Audio format | *(e.g. pcm_16000)* |
| Transport | LiveKit Agents (WebRTC) via official Rime LiveKit plugin |

**Rule:** whatever you write here must be the exact combination used in the recorded
demo — organizers will preflight-check it, and a combination that fails preflight and
isn't corrected before the deadline is a disqualifier.

**Fallback behavior (currently a placeholder in your draft — must be filled in, not
left blank):** decide now — e.g. "if Rime is unreachable, the agent surfaces a spoken
(pre-cached) apology via a fallback local TTS and flags `active_speech_provider:
fallback` in the dashboard; Rime remains the default path in the judged flow." Whatever
you choose, it must be (a) real, (b) disclosed in README, (c) visibly logged so the
active provider is observable during the demo.

---

## 4. Evidence package (20% of score — do not shortcut)

### 4.1 `evidence/RIME_EVIDENCE.md` structure
```
## Hard voice claim
[one sentence: interruption stops speech + cancels stale work + never lets the
LLM reason about unplayed content]

## Acceptance test (defined before the demo)
Introduce a fixed delay into the SQL-RAG tool call. While the agent is speaking
or the query is pending, interrupt and change part of the request (e.g. "actually,
what about the DHT22 instead"). Verify all five:
1. Queued Rime audio stops promptly
2. The updated instruction reaches the orchestrator
3. Stale SQL-RAG results are not spoken as current
4. Background DB work is cancelled or its result reconciled (fenced, not applied)
5. The final spoken response reflects exactly what the user actually heard + requested

## Procedure
Repeatable command: `python evidence/stress_test.py --n 10`
[describe what it does — see 4.2]

## Result
[measured: fenced-drop count, time-to-stop-audio (ms), correct-final-answer rate
across n runs — from Firestore telemetry]

## Limitations
- truncation math assumes constant word-rate within an utterance (no SSML/punctuation pacing)
- SQL allow-list covers 2 demo tables only
- [add any P1/vector-RAG limitations if shipped]
```

### 4.2 `evidence/stress_test.py`
- Drives the orchestrator directly (no live mic/VAD needed) for fast, fully
  reproducible CI-style runs — default `--n 10`.
- Injects a fixed artificial delay into the SQL-RAG call, fires a simulated
  mid-flight interruption + corrected request, and asserts all 5 acceptance-test
  checkpoints above via the Firestore telemetry log.
- Recommend one small **live-mic confirmation pass** before the recorded demo, per
  your own noted limitation — disclose in README that the default automated run is
  non-mic and why.

---

## 5. README.md — required sections (all mandatory per submission rules)
1. Setup instructions (exact commands, already drafted in your original doc — keep)
2. Architecture (the diagram in §2, kept current)
3. Third-party services (Rime, LiveKit Agents, Deepgram, Firebase Firestore, SQLite —
   plus Vector RAG store if P1 ships)
4. Known limitations (truncation assumptions, allow-listed tables, anything P1/P2 adds)
5. Failure behavior (SQL-RAG failure → spoken error, never silent/guessed; Rime
   unreachable → the fallback you defined in §3, disclosed)
6. Exact Rime model ID, speaker, language, endpoint, audio format, transport (§3 table)

## 6. Configuration hygiene
- `.env.example` — placeholders only (`RIME_API_KEY=`, `DEEPGRAM_API_KEY=`,
  `LLM_API_KEY=`, `FIREBASE_*=`). Never commit `serviceAccountKey.json` or a filled `.env`.
- All Rime/LLM/Deepgram/Firebase calls happen server-side in `backend/`; nothing
  credentialed ships to client code, screenshots, or recordings.
- Run the organizer-provided Rime configuration + secret preflight check before
  submitting, and fix anything it flags — this is a hard eligibility gate.

## 7. Demo script (`docs/demo_script.md`) — 4-5 min, map to rubric
1. (0:00-0:30) Who the user is + why voice is the only channel (hands-busy lab, can't look at a screen)
2. (0:30-1:30) Normal end-to-end flow: ask a spec question, hear a Rime-spoken answer via SQL-RAG
3. (1:30-3:00) The deliberate stress case: interrupt mid-answer, change the request,
   show (on the dashboard) the stale result being fenced/dropped and the correct
   corrected answer being spoken instead
4. (3:00-3:30) State which speech provider is active on screen (Rime, or disclosed fallback if triggered)
5. (3:30-4:30) Show the measured result from `evidence/RIME_EVIDENCE.md` / stress_test.py output
6. (4:30-5:00) One-line on limitations + what P1 (if shipped) adds

---

## 8. P1 — Vector RAG (only after P0 is demo-ready and evidenced)
- Add `vector_rag_chain.py`: embed manual PDFs once at setup, retrieve top-k chunks
  for procedural/troubleshooting questions, same generation-ID fencing rules apply
  (a stale vector-RAG result is fenced exactly like a stale SQL result).
- No separate acceptance test needed — it's covered by the same "conversation
  continuity during tool work" claim, just add one line to Known Limitations about
  retrieval quality/chunking if you ship it.

## 9. P2 — Reservation/checkout (cut first if time is short)
- If attempted: two-phase commit with generation-ID-tagged locks, instant rollback
  on interruption. Frame this in the demo only as a bonus, after the P0 stress case
  has already been clearly shown — don't let it replace the core demonstration.
