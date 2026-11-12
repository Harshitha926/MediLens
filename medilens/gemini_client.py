"""Small Google Gemini client wrapper for report extraction and explanations."""

import json
from typing import Any

from google import genai
from google.genai import types

from medilens.config import GEMINI_API_KEY, GEMINI_MODEL
from medilens.prompts import (
    EXTRACTION_PROMPT,
    SYSTEM_SAFETY,
    TRANSCRIBE_PROMPT,
    explanation_prompt,
    question_prompt,
)

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Create the client only when an API call is actually needed."""
    global _client
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "Gemini API key is missing. Add GEMINI_API_KEY to your .env file."
        )
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _generate(
    contents: Any, json_output: bool = False, temperature: float = 0.2
) -> str:
    """Generate content with the shared safety instruction and model settings."""
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_SAFETY,
        temperature=temperature,
        response_mime_type="application/json" if json_output else None,
    )
    response = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=config,
    )
    text = getattr(response, "text", None)
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text.strip()


def _parse_json(text: str) -> dict:
    """Parse JSON even if a model wraps it in incidental leading/trailing text."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Gemini did not return a JSON object.")
    try:
        result = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini returned invalid JSON: {exc.msg}") from exc
    if not isinstance(result, dict):
        raise ValueError("Gemini's JSON response must be an object.")
    return result


def extract_report(file_bytes: bytes, mime_type: str) -> dict:
    """Extract report metadata and test results from a PDF or image."""
    part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
    response = _generate(
        [part, EXTRACTION_PROMPT],
        json_output=True,
        temperature=0,
    )
    return _parse_json(response)


def _report_payload(report: dict, tests: list[dict]) -> dict:
    """Keep model-derived tests and rule-enriched statuses in the same context."""
    return {**report, "tests": tests}


def explain_report(report: dict, tests: list[dict], language: str) -> str:
    """Generate a short explanation for the selected language."""
    payload = _report_payload(report, tests)
    prompt = explanation_prompt(payload, language)
    return _generate(prompt, temperature=0.2)


def answer_question(
    report: dict, tests: list[dict], question: str, language: str
) -> str:
    """Answer one question using only the supplied report context."""
    payload = _report_payload(report, tests)
    prompt = question_prompt(payload, question, language)
    return _generate(prompt, temperature=0.2)


def transcribe_audio(audio_bytes: bytes, mime_type: str) -> str:
    """Transcribe a recorded question without translating it."""
    part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
    transcription = _generate([part, TRANSCRIBE_PROMPT], temperature=0)
    if not transcription:
        raise RuntimeError("No speech could be recognized in the recording.")
    return transcription
