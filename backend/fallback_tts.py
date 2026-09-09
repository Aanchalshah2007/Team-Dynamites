"""Fallback speech path when Rime is unreachable (architecture §3).

Plays a pre-cached local apology clip directly onto the room's audio track
via the stable livekit.rtc primitives, deliberately bypassing the TTS plugin
abstraction -- if Rime just failed, routing the apology through the same
plugin risks failing identically. Generate the cached clip once with
generate_fallback_audio.py during setup.

VERIFY the AudioSource/LocalAudioTrack/AudioFrame call shapes below against
the livekit-rtc version actually installed -- see the note atop livekit_agent.py.
"""

import logging
import wave
from pathlib import Path

from livekit import rtc

logger = logging.getLogger("fallback_tts")

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
FALLBACK_WAV_PATH = ASSETS_DIR / "fallback_apology.wav"

_FRAME_MS = 20


async def _publish_wav(room: rtc.Room, wav_path: Path) -> None:
    with wave.open(str(wav_path), "rb") as wf:
        sample_rate = wf.getframerate()
        num_channels = wf.getnchannels()
        pcm_bytes = wf.readframes(wf.getnframes())

    source = rtc.AudioSource(sample_rate, num_channels)
    track = rtc.LocalAudioTrack.create_audio_track("fallback-tts", source)
    await room.local_participant.publish_track(track, rtc.TrackPublishOptions())

    samples_per_frame = int(sample_rate * _FRAME_MS / 1000)
    bytes_per_sample = 2 * num_channels
    chunk_size = samples_per_frame * bytes_per_sample

    for offset in range(0, len(pcm_bytes), chunk_size):
        chunk = pcm_bytes[offset : offset + chunk_size]
        if len(chunk) < chunk_size:
            chunk = chunk + b"\x00" * (chunk_size - len(chunk))
        frame = rtc.AudioFrame(
            data=chunk,
            sample_rate=sample_rate,
            num_channels=num_channels,
            samples_per_channel=samples_per_frame,
        )
        await source.capture_frame(frame)


async def speak_fallback(room: rtc.Room, text: str) -> None:
    """Plays the pre-cached apology clip. `text` is accepted for API
    symmetry with the primary speech path and logged on a cache miss -- the
    clip itself is fixed; see generate_fallback_audio.py to regenerate it if
    the wording changes."""
    if not FALLBACK_WAV_PATH.exists():
        logger.error(
            "Fallback audio missing at %s -- run generate_fallback_audio.py once "
            "during setup. Apology text was: %r",
            FALLBACK_WAV_PATH,
            text,
        )
        return
    try:
        await _publish_wav(room, FALLBACK_WAV_PATH)
    except Exception:
        logger.exception("Fallback audio playback itself failed -- agent will be silent this turn")
