"""SQLite persistence for patient reports and their test results."""

import sqlite3
from pathlib import Path
from typing import Any

from medilens.config import DB_PATH, ensure_db_directory


def _connect() -> sqlite3.Connection:
    ensure_db_directory()
    connection = sqlite3.connect(Path(DB_PATH).expanduser())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    """Create report and result tables if they do not already exist."""
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient TEXT NOT NULL,
                report_date TEXT,
                report_type TEXT,
                lab_name TEXT,
                summary TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                test_name TEXT NOT NULL,
                standard_name TEXT,
                value REAL,
                value_text TEXT,
                unit TEXT,
                ref_low REAL,
                ref_high REAL,
                status TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_reports_patient_date
                ON reports(patient, report_date);
            CREATE INDEX IF NOT EXISTS idx_results_report
                ON results(report_id);
            """
        )


def save_report(
    patient: str,
    report: dict[str, Any],
    tests: list[dict[str, Any]],
    summary: str,
    report_date: str | None = None,
) -> int:
    """Save report metadata and all extracted tests atomically."""
    init_db()
    with _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO reports (patient, report_date, report_type, lab_name, summary)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                patient.strip() or "Me",
                report_date or report.get("report_date"),
                report.get("report_type"),
                report.get("lab_name"),
                summary,
            ),
        )
        report_id = int(cursor.lastrowid)
        connection.executemany(
            """
            INSERT INTO results (
                report_id, test_name, standard_name, value, value_text, unit,
                ref_low, ref_high, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    report_id,
                    test.get("test_name") or "Unknown test",
                    test.get("standard_name"),
                    test.get("value"),
                    test.get("value_text"),
                    test.get("unit"),
                    test.get("ref_low"),
                    test.get("ref_high"),
                    test.get("status"),
                )
                for test in tests
            ],
        )
    return report_id


def list_patients() -> list[str]:
    """Return patient profiles that have at least one saved report."""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT DISTINCT patient FROM reports ORDER BY patient"
        ).fetchall()
    return [str(row["patient"]) for row in rows]


def list_reports(patient: str) -> list[dict[str, Any]]:
    """List a patient's saved report metadata, newest report date first."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT id, patient, report_date, report_type, lab_name, summary, created_at
            FROM reports WHERE patient = ?
            ORDER BY report_date DESC, id DESC
            """,
            (patient,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_trend_rows(patient: str) -> list[dict[str, Any]]:
    """Return saved numeric results with their report date and reference range."""
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT r.id AS report_id, r.report_date, r.report_type,
                   x.test_name, x.standard_name, x.value, x.unit,
                   x.ref_low, x.ref_high, x.status
            FROM reports AS r
            JOIN results AS x ON x.report_id = r.id
            WHERE r.patient = ? AND x.value IS NOT NULL
            ORDER BY r.report_date, r.id, x.id
            """,
            (patient,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_report(report_id: int) -> None:
    """Delete a report; its results are removed through the foreign key."""
    with _connect() as connection:
        cursor = connection.execute("DELETE FROM reports WHERE id = ?", (report_id,))
        if cursor.rowcount == 0:
            raise ValueError(f"No saved report found with ID {report_id}.")
