"""Firestore telemetry (architecture §2.1, §3, §4): fenced_drop events,
active_speech_provider, turn events -- feeds the dashboard and is what proves
the RIME_EVIDENCE.md claim.

Writes are best-effort: a telemetry outage must never break the voice
pipeline, so every failure is caught and logged locally instead of raised.
"""

import datetime
import logging

import config

logger = logging.getLogger("telemetry")

_db = None


def _get_db():
    global _db
    if _db is None:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(
                {
                    "type": "service_account",
                    "project_id": config.FIREBASE_PROJECT_ID,
                    "private_key": config.FIREBASE_PRIVATE_KEY,
                    "client_email": config.FIREBASE_CLIENT_EMAIL,
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            )
            firebase_admin.initialize_app(cred)
        _db = firestore.client()
    return _db


_warned_not_configured = False


def log_event(event: dict) -> None:
    global _warned_not_configured
    payload = {**event, "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()}

    if not config.FIREBASE_PROJECT_ID:
        if not _warned_not_configured:
            logger.warning("FIREBASE_PROJECT_ID not set -- telemetry events will be dropped (this one and all after it)")
            _warned_not_configured = True
        return

    try:
        _get_db().collection("telemetry").add(payload)
    except Exception as exc:
        logger.warning("telemetry write failed: %s (%s)", payload.get("event"), exc)


def log_fenced_drop(stale_gen: int, current_gen: int, task_kind: str) -> None:
    log_event(
        {
            "event": "fenced_drop",
            "stale_gen": stale_gen,
            "current_gen": current_gen,
            "task_kind": task_kind,
        }
    )


def log_speech_provider(provider: str) -> None:
    log_event({"event": "active_speech_provider", "provider": provider})


def log_turn(**fields) -> None:
    log_event({"event": "turn", **fields})
