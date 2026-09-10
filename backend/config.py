"""Loads env, exposes ALLOWED_TABLES, RIME config constants (architecture §1)."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- LiveKit ---
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

# --- Deepgram STT ---
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")

# --- LLM (turn reasoning, SQL generation, answer formatting) ---
# Groq's OpenAI-compatible chat completions API (LLM_API_KEY is a Groq key,
# prefix "gsk_"). See llm_client.py.
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")

# --- Rime TTS: exact combination used in the recorded demo (architecture §3) ---
# Confirmed working end-to-end 2026-09-10 with a live synthesis call.
RIME_API_KEY = os.getenv("RIME_API_KEY", "")
RIME_MODEL_ID = os.getenv("RIME_MODEL_ID", "mistv2")
RIME_SPEAKER = os.getenv("RIME_SPEAKER", "abbie")
RIME_LANGUAGE = os.getenv("RIME_LANGUAGE", "eng")
RIME_ENDPOINT = os.getenv("RIME_ENDPOINT", "https://users.rime.ai/v1/rime-tts")
RIME_AUDIO_FORMAT = os.getenv("RIME_AUDIO_FORMAT", "pcm")  # LiveKit plugin TTSEncoding: "pcm" | "mp3"
RIME_SAMPLE_RATE = int(os.getenv("RIME_SAMPLE_RATE", "16000"))

# --- Firebase Firestore (telemetry: fenced_drop events, active_speech_provider) ---
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
FIREBASE_CLIENT_EMAIL = os.getenv("FIREBASE_CLIENT_EMAIL", "")
FIREBASE_PRIVATE_KEY = os.getenv("FIREBASE_PRIVATE_KEY", "").replace("\\n", "\n")

# --- SQL-RAG scope guard (architecture §2.3) ---
# Extending the schema = add the table here. Real scaling constraint, documented
# in README's Known Limitations.
ALLOWED_TABLES = ["sensors", "actuators"]

DB_PATH = Path(__file__).resolve().parent / "demo.db"

# --- Fallback speech behavior (architecture §3) ---
# If Rime is unreachable, the agent speaks a pre-cached local apology instead of
# going silent, and flags active_speech_provider=fallback in telemetry/dashboard.
FALLBACK_TTS_ENABLED = True
FALLBACK_APOLOGY_TEXT = (
    "Sorry, I'm having trouble reaching my voice service right now. "
    "I'll try to help using a backup voice."
)

# --- Audio-truncation (architecture §2.2) ---
# Real value is written by evidence/measure_wps.py against the exact Rime
# voice/model above — never hardcode an assumed number here.
MEASURED_WPS_PATH = Path(__file__).resolve().parent / "measured_wps.txt"


def load_measured_wps(default: float = 2.5) -> float:
    """Reads the calibrated words-per-second constant, or a rough default if
    evidence/measure_wps.py hasn't been run yet."""
    try:
        return float(MEASURED_WPS_PATH.read_text().strip())
    except (FileNotFoundError, ValueError):
        return default
