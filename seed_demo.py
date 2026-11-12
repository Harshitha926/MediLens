"""Insert three invented reports to demonstrate the trends dashboard."""

from medilens.analysis import enrich_tests
from medilens.storage import init_db, list_reports, save_report

PATIENT = "Demo Patient"

DEMO_REPORTS = [
    {
        "report_date": "2026-01-15",
        "tests": [
            ("Fasting Blood Glucose", 112, "mg/dL", 70, 99),
            ("HbA1c", 6.0, "%", 4.0, 5.6),
            ("Hemoglobin", 13.2, "g/dL", 12.0, 16.0),
            ("Total Cholesterol", 220, "mg/dL", None, 200),
            ("TSH", 3.2, "mIU/L", 0.4, 4.0),
        ],
    },
    {
        "report_date": "2026-05-15",
        "tests": [
            ("Fasting Blood Glucose", 105, "mg/dL", 70, 99),
            ("HbA1c", 5.8, "%", 4.0, 5.6),
            ("Hemoglobin", 13.5, "g/dL", 12.0, 16.0),
            ("Total Cholesterol", 205, "mg/dL", None, 200),
            ("TSH", 2.8, "mIU/L", 0.4, 4.0),
        ],
    },
    {
        "report_date": "2026-10-15",
        "tests": [
            ("Fasting Blood Glucose", 96, "mg/dL", 70, 99),
            ("HbA1c", 5.5, "%", 4.0, 5.6),
            ("Hemoglobin", 13.8, "g/dL", 12.0, 16.0),
            ("Total Cholesterol", 188, "mg/dL", None, 200),
            ("TSH", 2.4, "mIU/L", 0.4, 4.0),
        ],
    },
]


def main() -> None:
    init_db()
    existing_dates = {
        report["report_date"] for report in list_reports(PATIENT)
    }
    for demo in DEMO_REPORTS:
        report_date = demo["report_date"]
        if report_date in existing_dates:
            print(f"Skipped existing demo report for {report_date}.")
            continue
        tests = enrich_tests(
            [
                {
                    "test_name": name,
                    "standard_name": name,
                    "value": value,
                    "value_text": str(value),
                    "unit": unit,
                    "ref_low": low,
                    "ref_high": high,
                    "ref_range_text": (
                        f"{low:g} - {high:g}"
                        if low is not None and high is not None
                        else (f"< {high:g}" if high is not None else None)
                    ),
                    "status": "unknown",
                }
                for name, value, unit, low, high in demo["tests"]
            ]
        )
        save_report(
            PATIENT,
            {
                "report_date": report_date,
                "report_type": "Demo blood panel",
                "lab_name": "MediLens Demo Lab",
            },
            tests,
            "Invented values for demonstrating the trends dashboard.",
            report_date=report_date,
        )
        existing_dates.add(report_date)
        print(f"Inserted demo report for {report_date}.")
    print("Choose 'Demo Patient' in the Patient profile field to view trends.")


if __name__ == "__main__":
    main()
