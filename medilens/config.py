"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
DB_PATH = os.getenv("DB_PATH", "data/medilens.db").strip()

LANGUAGES = {
    "English": "en",
    "Hindi": "hi",
    "Kannada": "kn",
    "Tamil": "ta",
    "Telugu": "te",
    "Malayalam": "ml",
    "Marathi": "mr",
    "Bengali": "bn",
    "Gujarati": "gu",
}

DISCLAIMER = (
    "MediLens is an educational assistant, not a medical professional. "
    "It does not diagnose or recommend treatment. Always discuss lab results "
    "with a qualified doctor, especially any result flagged as abnormal."
)


def ensure_db_directory() -> None:
    """Create the configured database's parent directory when needed."""
    parent = Path(DB_PATH).expanduser().parent
    if str(parent) not in {"", "."}:
        parent.mkdir(parents=True, exist_ok=True)
