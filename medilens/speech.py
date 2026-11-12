"""Text cleanup and gTTS audio generation."""

import re
from io import BytesIO

from gtts import gTTS


def clean_for_speech(text: str) -> str:
    """Remove common Markdown formatting before sending text to speech."""
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~`>#]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def text_to_speech(text: str, lang_code: str) -> bytes:
    """Convert text to MP3 bytes using Google Text-to-Speech."""
    cleaned = clean_for_speech(text)
    if not cleaned:
        raise ValueError("There is no text available to read aloud.")
    output = BytesIO()
    gTTS(text=cleaned, lang=lang_code).write_to_fp(output)
    return output.getvalue()
