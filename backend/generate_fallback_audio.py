"""One-time setup script: synthesizes config.FALLBACK_APOLOGY_TEXT into
backend/assets/fallback_apology.wav using an offline TTS engine (pyttsx3),
so the runtime fallback path (fallback_tts.py) never depends on a network
call to any speech provider -- including Rime, the thing it's a fallback for.

Run once during setup: python generate_fallback_audio.py
"""

import pyttsx3

import config
from fallback_tts import ASSETS_DIR, FALLBACK_WAV_PATH


def generate() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    engine = pyttsx3.init()
    engine.save_to_file(config.FALLBACK_APOLOGY_TEXT, str(FALLBACK_WAV_PATH))
    engine.runAndWait()
    print(f"Wrote fallback apology clip to {FALLBACK_WAV_PATH}")


if __name__ == "__main__":
    generate()
