"""Generation-ID fencing, audio-truncation, turn state machine (architecture §2, §2.1, §2.2).

Deliberately independent of LiveKit/Rime/Deepgram so it can be driven directly
by evidence/stress_test.py with no live mic or VAD -- livekit_agent.py wires
this to real audio; the stress test wires it to simulated timing instead.
"""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Awaitable, Callable, Optional

import config
import sql_rag_chain
import telemetry


class TurnState(Enum):
    IDLE = auto()
    THINKING = auto()   # SQL-RAG / LLM work in flight
    SPEAKING = auto()    # Rime audio playing


@dataclass
class Turn:
    role: str            # "user" | "assistant"
    text: str
    generation_id: int
    interrupted: bool = False


@dataclass
class BargeInResult:
    words_heard: int
    truncated_text: str
    remainder_text: str


class Orchestrator:
    """Owns current_generation_id and the turn state machine for one voice session."""

    def __init__(self, measured_wps: Optional[float] = None, clock: Callable[[], float] = time.monotonic):
        self.current_generation_id: int = 0
        self.state: TurnState = TurnState.IDLE
        self.history: list[Turn] = []
        self.measured_wps: float = measured_wps if measured_wps is not None else config.load_measured_wps()
        self._clock = clock

        # Set by livekit_agent.py so the orchestrator can stop Rime audio on barge-in
        # without owning any audio/transport code itself.
        self.on_stop_audio: Optional[Callable[[], None]] = None

        self._playback_start: Optional[float] = None
        self._playback_words: list[str] = []
        self._playback_generation: Optional[int] = None

    # ---- barge-in (called by livekit_agent.py the instant VAD detects user speech
    # while self.state == SPEAKING; the STT transcript for the new turn isn't ready yet) ----

    def on_speech_started_by_user(self) -> Optional[BargeInResult]:
        if self.state != TurnState.SPEAKING or self._playback_start is None:
            return None

        elapsed = self._clock() - self._playback_start
        words_heard = max(0, min(len(self._playback_words), round(elapsed * self.measured_wps)))
        heard = self._playback_words[:words_heard]
        remainder = self._playback_words[words_heard:]

        if self.on_stop_audio is not None:
            self.on_stop_audio()

        if self.history and self.history[-1].role == "assistant":
            self.history[-1].text = " ".join(heard)
            self.history[-1].interrupted = bool(remainder)

        self.state = TurnState.THINKING
        self._playback_start = None
        return BargeInResult(
            words_heard=words_heard,
            truncated_text=" ".join(heard),
            remainder_text=" ".join(remainder),
        )

    # ---- turn lifecycle ----

    def start_new_turn(self, user_text: str) -> int:
        """Called once STT finalizes a user utterance. Always bumps the
        generation id, so any task still in flight from a prior turn is
        provably stale under the fencing check below -- including tasks
        started while the system was idle, not just mid-speech (a strict
        superset of the "interrupted" case, and the only way the fencing
        check has anything to compare against)."""
        self.current_generation_id += 1
        gen = self.current_generation_id
        self.history.append(Turn(role="user", text=user_text, generation_id=gen))
        self.state = TurnState.THINKING
        telemetry.log_turn(kind="user_utterance", generation_id=gen, text=user_text)
        return gen

    async def run_sql_rag(self, question: str, generation_id: int) -> Optional[sql_rag_chain.SqlRagResult]:
        """Runs SQL-RAG for `question` under `generation_id`. Returns None
        (and logs a fenced_drop) if the result resolves after a newer turn
        has already started -- per architecture §2.1, that result must never
        reach the LLM or TTS."""
        result = await asyncio.to_thread(sql_rag_chain.answer, question)
        if generation_id != self.current_generation_id:
            telemetry.log_fenced_drop(
                stale_gen=generation_id, current_gen=self.current_generation_id, task_kind="sql_rag"
            )
            return None
        return result

    def begin_playback(self, generation_id: int, text: str) -> bool:
        """Call right before handing `text` to the Rime TTS plugin. Returns
        False (and fences/logs) if a newer turn has already started, in which
        case the caller must not speak the text at all."""
        if generation_id != self.current_generation_id:
            telemetry.log_fenced_drop(
                stale_gen=generation_id, current_gen=self.current_generation_id, task_kind="tts_playback"
            )
            return False
        self.state = TurnState.SPEAKING
        self._playback_start = self._clock()
        self._playback_words = text.split()
        self._playback_generation = generation_id
        self.history.append(Turn(role="assistant", text=text, generation_id=generation_id))
        return True

    def finish_playback(self, generation_id: int) -> None:
        """Call when Rime reports playback complete for `generation_id`."""
        if generation_id != self.current_generation_id:
            return
        self.state = TurnState.IDLE
        self._playback_start = None

    def finish_turn_without_speech(self, generation_id: int) -> None:
        """Call when a turn ends with nothing spoken (e.g. fenced/dropped
        before reaching TTS)."""
        if generation_id == self.current_generation_id:
            self.state = TurnState.IDLE
