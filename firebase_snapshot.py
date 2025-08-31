
# firebase_backend.py — snapshot-only runtime (no Firestore I/O)
import json
import os
import random
from typing import List, Dict

# Path to the snapshot; default is next to this file
_SNAPSHOT_PATH = os.getenv(
    "SNAPSHOT_PATH",
    os.path.join(os.path.dirname(__file__), "questions_snapshot.json")
)

# Loaded once and reused
_SNAPSHOT_DATA: List[Dict] = []
_LOADED = False


def _ensure_loaded():
    global _LOADED, _SNAPSHOT_DATA
    if _LOADED:
        return
    try:
        with open(_SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            _SNAPSHOT_DATA = json.load(f)
    except FileNotFoundError:
        # No snapshot shipped; keep empty so the app still runs
        _SNAPSHOT_DATA = []
    _LOADED = True


def initialize_firebase(credential_path: str):
    """No-op in snapshot mode (kept for compatibility)."""
    return


def are_questions_identical(q1: dict, q2: dict) -> bool:
    """Unused in snapshot mode but kept for import compatibility."""
    return (
            q1.get("question") == q2.get("question")
            and q1.get("answer") == q2.get("answer")
            and set(q1.get("options", [])) == set(q2.get("options", []))
    )


def is_duplicate_question(new_question: dict) -> bool:
    """No DB reads in snapshot mode."""
    return False


def save_quiz_question(topic: str, question_data: dict) -> str:
    """Disabled in snapshot mode (no writes)."""
    return ""


def get_random_quiz_questions(limit=10) -> list:
    _ensure_loaded()
    n = min(limit, len(_SNAPSHOT_DATA))
    return random.sample(_SNAPSHOT_DATA, n)


def get_quiz_question_count() -> int:
    _ensure_loaded()
    return len(_SNAPSHOT_DATA)
