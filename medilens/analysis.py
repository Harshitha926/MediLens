"""Rule-based parsing and status checks for laboratory results."""

from __future__ import annotations

import math
import re
from typing import Any

_NUMBER = re.compile(r"[-+]?(?:\d[\d,]*\.?\d*|\.\d+)")
_RANGE = re.compile(
    r"^\s*([-+]?(?:\d[\d,]*\.?\d*|\.\d+))\s*(?:-|–|—|to)\s*"
    r"([-+]?(?:\d[\d,]*\.?\d*|\.\d+))\s*$",
    re.IGNORECASE,
)
_LIMIT = re.compile(
    r"^\s*(<=|>=|<|>)\s*([-+]?(?:\d[\d,]*\.?\d*|\.\d+))\s*$"
)


def to_float(value: Any) -> float | None:
    """Convert a number or numeric string to a finite float."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def number_from_text(value: Any) -> float | None:
    """Get the first numeric value from text such as ``12.5 H``."""
    number = to_float(value)
    if number is not None:
        return number
    if not isinstance(value, str):
        return None
    match = _NUMBER.search(value.replace(",", ""))
    return to_float(match.group(0)) if match else None


def parse_range(text: Any) -> tuple[float | None, float | None]:
    """Parse two-sided ranges and single-sided limits."""
    if not isinstance(text, str) or not text.strip():
        return None, None
    match = _RANGE.match(text)
    if match:
        return to_float(match.group(1)), to_float(match.group(2))
    match = _LIMIT.match(text)
    if not match:
        return None, None
    operator, raw_limit = match.groups()
    limit = to_float(raw_limit)
    if operator in {"<", "<="}:
        return None, limit
    return limit, None


def compute_status(
    value: float | None, low: float | None, high: float | None
) -> str | None:
    """Classify a numeric result when at least one reference limit is known."""
    if value is None or (low is None and high is None):
        return None
    if low is not None and value < low:
        return "low"
    if high is not None and value > high:
        return "high"
    return "normal"


def enrich_tests(tests: list[dict]) -> list[dict]:
    """Normalize values/ranges and prefer a computable rule-based status."""
    enriched: list[dict] = []
    for original in tests:
        test = dict(original)
        model_status = str(test.get("status") or "unknown").lower()
        if model_status not in {"normal", "high", "low", "abnormal", "unknown"}:
            model_status = "unknown"

        value = number_from_text(test.get("value"))
        if value is None:
            value = number_from_text(test.get("value_text"))
        test["value"] = value
        if not test.get("value_text"):
            test["value_text"] = "" if value is None else str(value)

        low = to_float(test.get("ref_low"))
        high = to_float(test.get("ref_high"))
        text_low, text_high = parse_range(test.get("ref_range_text"))
        if low is None:
            low = text_low
        if high is None:
            high = text_high
        test["ref_low"] = low
        test["ref_high"] = high

        rule_status = compute_status(value, low, high)
        if rule_status is not None:
            test["status"] = rule_status
            test["status_source"] = "rule"
        else:
            test["status"] = model_status
            test["status_source"] = "model"
        test["model_status"] = model_status
        enriched.append(test)
    return enriched


def status_counts(tests: list[dict]) -> dict[str, int]:
    """Count each status; abnormal is kept separate from high and low."""
    counts = {name: 0 for name in ("normal", "high", "low", "abnormal", "unknown")}
    for test in tests:
        status = str(test.get("status", "unknown")).lower()
        counts[status if status in counts else "unknown"] += 1
    return counts


def range_text(test: dict) -> str:
    """Return a readable reference range, preferring the report's original text."""
    original = test.get("ref_range_text")
    if original:
        return str(original)
    low = to_float(test.get("ref_low"))
    high = to_float(test.get("ref_high"))
    if low is not None and high is not None:
        return f"{low:g} - {high:g}"
    if high is not None:
        return f"< {high:g}"
    if low is not None:
        return f"> {low:g}"
    return "Not provided"
