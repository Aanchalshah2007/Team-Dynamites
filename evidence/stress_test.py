"""Scripted, reproducible interruption stress test (architecture §4.2).

Drives backend/orchestrator.py directly -- no live mic or VAD needed -- for
fast, fully reproducible CI-style runs. Injects a fixed artificial delay into
the SQL-RAG call, fires a simulated mid-flight interruption + corrected
request, and checks all 5 acceptance-test checkpoints from RIME_EVIDENCE.md
each run, plus feeds Firestore telemetry (fenced_drop events, per-run
summaries) so the dashboard and RIME_EVIDENCE.md Result numbers come from a
real, repeatable source rather than being hand-typed.

Run: python evidence/stress_test.py --n 10
"""

import argparse
import asyncio
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import orchestrator as orchestrator_module  # noqa: E402
import sql_rag_chain  # noqa: E402
import telemetry  # noqa: E402

FIRST_QUESTION = "What's the operating voltage of the DHT22?"
CORRECTED_QUESTION = "Actually, what about the HC-SR04 instead?"

FIRST_ANSWER_TEXT = "The DHT22 operates between three point three and six volts total draw."
CORRECTED_ANSWER_TEXT = "The HC-SR04 ultrasonic sensor operates at five volts."
STALE_ANSWER_TEXT = "This stale DHT22 answer must never be spoken to the user."

SLOW_SQL_DELAY_S = 0.3   # artificial delay on the background/pending SQL-RAG call
BARGE_IN_AFTER_S = 0.15  # how far into playback the user interrupts
TEST_WPS = 2.5           # fixed for reproducibility -- not the real measured_wps.txt value


def _install_fake_answer(responses: dict[str, tuple[float, str]]) -> None:
    def _fake(question: str) -> sql_rag_chain.SqlRagResult:
        delay, text = responses[question]
        if delay:
            time.sleep(delay)
        return sql_rag_chain.SqlRagResult(question=question, sql="SELECT 1", rows=[(1,)], answer=text)

    sql_rag_chain.answer = _fake


@dataclass
class RunResult:
    audio_stopped_promptly: bool
    corrected_instruction_reached: bool
    stale_result_not_spoken: bool
    stale_work_fenced: bool
    final_answer_correct: bool
    time_to_stop_audio_ms: float


async def run_once() -> RunResult:
    orch = orchestrator_module.Orchestrator(measured_wps=TEST_WPS, clock=time.monotonic)
    stop_calls: list[float] = []
    orch.on_stop_audio = lambda: stop_calls.append(time.monotonic())

    # --- normal turn: SQL-RAG resolves immediately, answer starts playing ---
    _install_fake_answer({FIRST_QUESTION: (0.0, FIRST_ANSWER_TEXT)})
    gen1 = orch.start_new_turn(FIRST_QUESTION)
    result1 = await orch.run_sql_rag(FIRST_QUESTION, gen1)
    assert result1 is not None and result1.answer == FIRST_ANSWER_TEXT
    assert orch.begin_playback(gen1, result1.answer)

    # --- background SQL-RAG work still pending under gen1 when the barge-in happens ---
    _install_fake_answer({FIRST_QUESTION: (SLOW_SQL_DELAY_S, STALE_ANSWER_TEXT)})
    playback_start = time.monotonic()
    stale_task = asyncio.create_task(orch.run_sql_rag(FIRST_QUESTION, gen1))

    await asyncio.sleep(BARGE_IN_AFTER_S)
    barge = orch.on_speech_started_by_user()
    assert barge is not None and barge.remainder_text != "", "expected a nonzero unheard remainder"
    time_to_stop_ms = (stop_calls[0] - playback_start) * 1000 if stop_calls else float("inf")

    # --- checkpoint 2: the corrected instruction reaches the orchestrator as a new turn ---
    _install_fake_answer({CORRECTED_QUESTION: (0.0, CORRECTED_ANSWER_TEXT)})
    gen2 = orch.start_new_turn(CORRECTED_QUESTION)
    result2 = await orch.run_sql_rag(CORRECTED_QUESTION, gen2)

    # --- checkpoints 3+4: stale background work resolves after gen2 started -> must be fenced ---
    stale_result = await stale_task

    final_spoken = bool(result2) and orch.begin_playback(gen2, result2.answer)

    return RunResult(
        audio_stopped_promptly=len(stop_calls) == 1 and time_to_stop_ms < 200,
        corrected_instruction_reached=any(
            t.generation_id == gen2 and t.role == "user" and t.text == CORRECTED_QUESTION for t in orch.history
        ),
        stale_result_not_spoken=stale_result is None,
        stale_work_fenced=stale_result is None,
        final_answer_correct=final_spoken and result2 is not None and result2.answer == CORRECTED_ANSWER_TEXT,
        time_to_stop_audio_ms=time_to_stop_ms,
    )


CHECKPOINT_FIELDS = [
    "audio_stopped_promptly",
    "corrected_instruction_reached",
    "stale_result_not_spoken",
    "stale_work_fenced",
    "final_answer_correct",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=10)
    args = parser.parse_args()

    results: list[RunResult] = []
    for i in range(args.n):
        result = asyncio.run(run_once())
        results.append(result)
        telemetry.log_event({"event": "stress_test_run", "run_index": i, **asdict(result)})

        passed = all(getattr(result, f) for f in CHECKPOINT_FIELDS)
        print(f"run {i + 1}/{args.n}: {'PASS' if passed else 'FAIL'}  stop={result.time_to_stop_audio_ms:.1f}ms")

    n = len(results)
    fenced_drop_count = sum(1 for r in results if r.stale_work_fenced)
    finite_stops = [r.time_to_stop_audio_ms for r in results if r.time_to_stop_audio_ms != float("inf")]
    avg_stop_ms = sum(finite_stops) / len(finite_stops) if finite_stops else float("inf")
    correct_rate = sum(1 for r in results if r.final_answer_correct) / n

    print("\n--- RIME_EVIDENCE.md Result inputs ---")
    print(f"runs: {n}")
    print(f"fenced-drop count: {fenced_drop_count}/{n}")
    print(f"avg time-to-stop-audio: {avg_stop_ms:.1f} ms")
    print(f"correct-final-answer rate: {correct_rate * 100:.0f}%")

    if fenced_drop_count != n or correct_rate != 1.0:
        sys.exit(1)


if __name__ == "__main__":
    main()
