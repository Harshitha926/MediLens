"""Evaluate report extraction against manually prepared JSON ground truth."""

from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd

from medilens.gemini_client import extract_report

PROJECT_ROOT = Path(__file__).resolve().parent
REPORTS_DIR = PROJECT_ROOT / "eval" / "reports"
RESULTS_PATH = PROJECT_ROOT / "eval" / "results.csv"
SUPPORTED_REPORTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def normalize_name(value: Any) -> str:
    """Normalize test labels to match names with punctuation/case differences."""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def evaluate_report(report_path: Path, truth: dict) -> list[dict]:
    """Extract one report and return test-level and report-level comparisons."""
    extracted = extract_report(
        report_path.read_bytes(), MIME_TYPES[report_path.suffix.lower()]
    )
    predicted = extracted.get("tests", [])
    predicted_by_name = {
        normalize_name(item.get("standard_name") or item.get("test_name")): item
        for item in predicted
    }
    expected_tests = truth.get("tests", [])
    comparisons: list[dict] = []
    matched = value_correct = status_correct = 0

    for expected in expected_tests:
        name = expected.get("standard_name", "")
        actual = predicted_by_name.get(normalize_name(name))
        found = actual is not None
        matched += int(found)
        expected_value = expected.get("value")
        actual_value = actual.get("value") if found else None
        value_ok = (
            found
            and expected_value is not None
            and actual_value is not None
            and math.isclose(
                float(actual_value), float(expected_value), rel_tol=0, abs_tol=0.01
            )
        )
        status_ok = (
            found
            and str(actual.get("status", "")).lower()
            == str(expected.get("status", "")).lower()
        )
        value_correct += int(value_ok)
        status_correct += int(status_ok)
        comparisons.append(
            {
                "report": report_path.name,
                "record_type": "test",
                "standard_name": name,
                "expected_value": expected_value,
                "actual_value": actual_value,
                "expected_status": expected.get("status"),
                "actual_status": actual.get("status") if found else None,
                "matched": int(found),
                "value_correct": int(value_ok),
                "status_correct": int(status_ok),
            }
        )

    total = len(expected_tests)
    comparisons.append(
        {
            "report": report_path.name,
            "record_type": "report_summary",
            "standard_name": None,
            "expected_value": None,
            "actual_value": None,
            "expected_status": None,
            "actual_status": None,
            "matched": matched,
            "value_correct": value_correct,
            "status_correct": status_correct,
            "test_recall": matched / total if total else 0.0,
            "value_accuracy": value_correct / total if total else 0.0,
            "status_accuracy": status_correct / total if total else 0.0,
            "expected_tests": total,
        }
    )
    return comparisons


def main() -> None:
    if not REPORTS_DIR.exists():
        raise FileNotFoundError(
            f"Evaluation directory not found: {REPORTS_DIR}. "
            "Add reports and matching .json ground-truth files first."
        )
    report_paths = sorted(
        path
        for path in REPORTS_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_REPORTS
        and path.with_suffix(".json").is_file()
    )
    if not report_paths:
        raise FileNotFoundError(
            f"No report files with matching .json ground truth found in {REPORTS_DIR}."
        )

    rows: list[dict] = []
    for index, report_path in enumerate(report_paths):
        truth_path = report_path.with_suffix(".json")
        try:
            truth = json.loads(truth_path.read_text(encoding="utf-8"))
            rows.extend(evaluate_report(report_path, truth))
        except Exception as exc:
            rows.append(
                {
                    "report": report_path.name,
                    "record_type": "error",
                    "error": str(exc),
                }
            )
            print(f"Failed to evaluate {report_path.name}: {exc}")
        if index < len(report_paths) - 1:
            time.sleep(2)

    successful = [row for row in rows if row.get("record_type") == "report_summary"]
    if successful:
        total_expected = sum(row["expected_tests"] for row in successful)
        overall = {
            "report": "OVERALL",
            "record_type": "overall_summary",
            "matched": sum(row["matched"] for row in successful),
            "value_correct": sum(row["value_correct"] for row in successful),
            "status_correct": sum(row["status_correct"] for row in successful),
            "expected_tests": total_expected,
            "test_recall": (
                sum(row["matched"] for row in successful) / total_expected
                if total_expected
                else 0.0
            ),
            "value_accuracy": (
                sum(row["value_correct"] for row in successful) / total_expected
                if total_expected
                else 0.0
            ),
            "status_accuracy": (
                sum(row["status_correct"] for row in successful) / total_expected
                if total_expected
                else 0.0
            ),
        }
        rows.append(overall)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(RESULTS_PATH, index=False)
    print(f"Saved extraction comparisons to {RESULTS_PATH}")
    if successful:
        print(
            "Overall: "
            f"recall={overall['test_recall']:.1%}, "
            f"value accuracy={overall['value_accuracy']:.1%}, "
            f"status accuracy={overall['status_accuracy']:.1%}"
        )


if __name__ == "__main__":
    main()
