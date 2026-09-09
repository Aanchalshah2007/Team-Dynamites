"""Calibrates words-per-second against the exact Rime voice/model used in the
demo (architecture §2.2) and writes the constant orchestrator.py uses for
audio-truncation math. Never hardcode an assumed value in config.py instead.

Run: python evidence/measure_wps.py

NOTE: verify this against Rime's current REST contract before relying on it --
the request/response shape here is a best-effort default, and architecture §3
requires the model/speaker/language/endpoint to be pulled from Rime's live
catalog and tested end-to-end at submission time, not assumed.
"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import config  # noqa: E402

CALIBRATION_TEXT = (
    "The DHT22 temperature and humidity sensor operates between negative "
    "forty and eighty degrees Celsius with zero to one hundred percent "
    "relative humidity, connected over a single wire digital interface."
)


def _pcm16_duration_seconds(pcm_bytes: bytes, sample_rate: int) -> float:
    num_samples = len(pcm_bytes) // 2  # 16-bit samples
    return num_samples / sample_rate


def _sample_rate_from_format(audio_format: str, default: int = 16000) -> int:
    tail = audio_format.rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else default


def measure() -> float:
    if not config.RIME_API_KEY or not config.RIME_ENDPOINT:
        raise SystemExit(
            "RIME_API_KEY / RIME_ENDPOINT not set. Fill the architecture §3 "
            "fields in .env before calibrating."
        )

    response = requests.post(
        config.RIME_ENDPOINT,
        headers={
            "Authorization": f"Bearer {config.RIME_API_KEY}",
            "Accept": "audio/*",
            "Content-Type": "application/json",
        },
        json={
            "text": CALIBRATION_TEXT,
            "modelId": config.RIME_MODEL_ID,
            "speaker": config.RIME_SPEAKER,
            "lang": config.RIME_LANGUAGE,
            "audioFormat": config.RIME_AUDIO_FORMAT,
        },
        timeout=30,
    )
    response.raise_for_status()

    sample_rate = _sample_rate_from_format(config.RIME_AUDIO_FORMAT)
    duration_s = _pcm16_duration_seconds(response.content, sample_rate)
    if duration_s <= 0:
        raise SystemExit("Calibration call returned no audio -- check RIME_* config.")

    word_count = len(CALIBRATION_TEXT.split())
    wps = word_count / duration_s

    config.MEASURED_WPS_PATH.write_text(f"{wps:.4f}")
    print(f"Calibration text: {word_count} words, {duration_s:.2f}s audio -> {wps:.4f} words/sec")
    print(f"Written to {config.MEASURED_WPS_PATH}")
    return wps


if __name__ == "__main__":
    measure()
