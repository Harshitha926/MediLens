"""All model prompts used by MediLens."""

import json

SYSTEM_SAFETY = """
You explain medical laboratory reports for educational purposes only. Never
diagnose a disease, recommend medicines or doses, or replace a clinician.
Always encourage the user to discuss results with a doctor. Clearly flag
seriously abnormal values and advise prompt professional follow-up without
claiming a diagnosis. Use only the data provided; do not invent facts,
reference ranges, symptoms, or patient history. Explain in simple, friendly
words. If information is missing or unclear, say so plainly.
""".strip()

EXTRACTION_PROMPT = """
Read the provided file and return ONLY a valid JSON object, without code
fences or commentary. It must have these fields:
{
  "patient_name": string or null,
  "report_date": "YYYY-MM-DD" or null,
  "lab_name": string or null,
  "report_type": string or null,
  "tests": [
    {
      "test_name": "name exactly as printed",
      "standard_name": "common English test name, consistent across labs",
      "value": number or null,
      "value_text": "result as printed",
      "unit": string or null,
      "ref_low": number or null,
      "ref_high": number or null,
      "ref_range_text": "reference range as printed" or null,
      "status": "normal, high, low, abnormal, or unknown",
      "category": string or null
    }
  ]
}
Never invent values or ranges. If a result is qualitative (for example
"Negative"), use null for value and preserve the result in value_text. For a
reference limit "< 200", set ref_high to 200; for "> 40", set ref_low to 40.
If the file is not a medical lab report, return exactly:
{"error": "not_a_medical_report"}
""".strip()

TRANSCRIBE_PROMPT = (
    "Transcribe the audio exactly as spoken. It may be English or an Indian "
    "language. Return only the transcription, with no translation or explanation."
)


def explanation_prompt(report_json: dict, language: str) -> str:
    """Build a concise, structured explanation prompt."""
    return f"""
Explain this lab report in {language}, using friendly and simple words. Keep
the complete answer under 350 words, in Markdown, and use exactly these
section headings:
## Summary
## Results that need attention
## Normal results
## What to do next
Explain uncertainties honestly. Use only the report data below. Do not
diagnose or recommend medicine or doses. Encourage the patient to discuss the
results with a doctor.

Report data:
{json.dumps(report_json, ensure_ascii=False, default=str)}
""".strip()


def question_prompt(report_json: dict, question: str, language: str) -> str:
    """Build a report-grounded question prompt."""
    return f"""
Answer the user's question in {language} in fewer than 150 words. Use only
the lab report data below. Do not diagnose, recommend medicine or doses, or
guess missing information. If the report does not contain the answer, say so.
Encourage discussion with a doctor.

Question: {question}

Report data:
{json.dumps(report_json, ensure_ascii=False, default=str)}
""".strip()
