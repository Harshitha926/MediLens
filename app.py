"""Streamlit interface for MediLens."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from medilens.analysis import enrich_tests, status_counts
from medilens.config import DISCLAIMER, GEMINI_API_KEY, GEMINI_MODEL, LANGUAGES
from medilens.gemini_client import (
    answer_question,
    explain_report,
    extract_report,
    transcribe_audio,
)
from medilens.speech import text_to_speech
from medilens.storage import (
    delete_report,
    get_trend_rows,
    init_db,
    list_reports,
    save_report,
)

st.set_page_config(page_title="MediLens", page_icon="🩺", layout="wide")
init_db()


def _report_date(report: dict) -> date:
    """Return a safe date for Streamlit's date input."""
    try:
        return date.fromisoformat(str(report.get("report_date", "")))
    except ValueError:
        return date.today()


def _status_style(row: pd.Series) -> list[str]:
    status = str(row.get("Status", "unknown")).lower()
    color = {
        "high": "background-color: #FDE2E2; color: #242424",
        "abnormal": "background-color: #FDE2E2; color: #242424",
        "low": "background-color: #FFF1CC; color: #242424",
        "normal": "background-color: #DDF3E4; color: #242424",
    }.get(status, "")
    return [color] * len(row)


def _show_analysis() -> None:
    st.subheader("Analyze a lab report")
    uploaded = st.file_uploader(
        "Upload a PDF or image",
        type=["pdf", "png", "jpg", "jpeg", "webp"],
        key="report_upload",
    )
    with st.expander("Use your camera"):
        camera_image = st.camera_input("Take a picture of the report", key="camera_report")
        if camera_image is not None:
            st.image(camera_image, caption="Captured report", width="stretch")

    source = uploaded if uploaded is not None else camera_image
    if uploaded is not None and uploaded.type.startswith("image/"):
        st.image(uploaded, caption="Uploaded report", width="stretch")

    if st.button("Analyze report", type="primary", disabled=source is None):
        st.session_state.report = None
        st.session_state.tests = []
        st.session_state.explanation = ""
        st.session_state.explanation_lang = ""
        st.session_state.explanation_audio = None
        st.session_state.saved_id = None
        st.session_state.qa = []
        try:
            extracted = extract_report(source.getvalue(), source.type or "image/jpeg")
            if extracted.get("error") == "not_a_medical_report":
                st.error("This file does not appear to be a medical lab report.")
                return

            tests = extracted.get("tests") or []
            if not tests:
                st.error("No lab tests could be read. Try a clearer image or PDF.")
                return

            tests = enrich_tests(tests)
            explanation = explain_report(extracted, tests, st.session_state.language)
            st.session_state.report = extracted
            st.session_state.tests = tests
            st.session_state.explanation = explanation
            st.session_state.explanation_lang = st.session_state.language
            st.session_state.explanation_audio = None
            st.session_state.saved_id = None
            st.session_state.save_report_date = _report_date(extracted)
            st.success("Report analyzed. Review the results with your doctor.")
        except Exception as exc:
            st.error(f"We couldn't analyze this report. Please try again. Details: {exc}")

    report = st.session_state.get("report")
    tests = st.session_state.get("tests", [])
    if not report or not tests:
        return

    counts = status_counts(tests)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Tests found", len(tests))
    metric_cols[1].metric("Normal", counts["normal"])
    metric_cols[2].metric("High", counts["high"])
    metric_cols[3].metric("Low", counts["low"])

    out_of_range = [
        test
        for test in tests
        if test.get("status") in {"high", "low", "abnormal"}
    ]
    if out_of_range:
        st.warning(
            "Results outside the listed reference range: "
            + ", ".join(
                f"{item.get('test_name', 'Test')} ({item.get('status')})"
                for item in out_of_range
            )
        )

    display_columns = [
        "test_name",
        "value_text",
        "unit",
        "ref_range_text",
        "status",
    ]
    frame = pd.DataFrame(tests)
    for column in display_columns:
        if column not in frame:
            frame[column] = ""
    frame = frame[display_columns].rename(
        columns={
            "test_name": "Test",
            "value_text": "Result",
            "unit": "Unit",
            "ref_range_text": "Reference range",
            "status": "Status",
        }
    )
    styled = frame.style.apply(_status_style, axis=1)
    st.dataframe(styled, width="stretch", hide_index=True)

    explanation = st.session_state.get("explanation", "")
    if st.session_state.get("explanation_lang") != st.session_state.language:
        st.info("The sidebar language changed. Regenerate the explanation to update its language.")
        if st.button("Regenerate explanation"):
            try:
                explanation = explain_report(report, tests, st.session_state.language)
                st.session_state.explanation = explanation
                st.session_state.explanation_lang = st.session_state.language
                st.session_state.explanation_audio = None
            except Exception as exc:
                st.error(f"We couldn't regenerate the explanation. Details: {exc}")
    st.markdown("### Explanation")
    st.markdown(explanation)

    if st.button("🔊 Listen to explanation"):
        try:
            st.session_state.explanation_audio = text_to_speech(
                explanation, LANGUAGES[st.session_state.language]
            )
        except Exception as exc:
            st.error(f"Audio could not be created. Check your internet connection. Details: {exc}")
    if st.session_state.get("explanation_audio"):
        st.audio(st.session_state.explanation_audio, format="audio/mp3")

    st.markdown("### Save report")
    report_day = st.date_input(
        "Report date",
        value=_report_date(report),
        key="save_report_date",
    )
    if st.button("Save report", type="secondary"):
        try:
            saved_id = save_report(
                patient=st.session_state.patient.strip() or "Me",
                report=report,
                tests=tests,
                summary=explanation,
                report_date=report_day.isoformat(),
            )
            st.session_state.saved_id = saved_id
            st.success(f"Report saved (ID {saved_id}).")
        except Exception as exc:
            st.error(f"The report could not be saved. Details: {exc}")


def _show_questions() -> None:
    st.subheader("Ask about this report")
    if not st.session_state.get("report"):
        st.info("Analyze a report first, then ask a question about its results.")
        return

    question = st.text_input("Type your question", key="typed_question")
    audio_question = st.audio_input("Or record your question", key="question_audio")
    if st.button("Get an answer", type="primary"):
        try:
            if question.strip():
                prompt_question = question.strip()
            elif audio_question is not None:
                prompt_question = transcribe_audio(
                    audio_question.getvalue(), audio_question.type or "audio/wav"
                )
                st.caption(f"Recognized question: {prompt_question}")
            else:
                st.warning("Enter or record a question first.")
                return

            answer = answer_question(
                st.session_state.report,
                st.session_state.tests,
                prompt_question,
                st.session_state.language,
            )
            audio_answer = None
            try:
                audio_answer = text_to_speech(
                    answer, LANGUAGES[st.session_state.language]
                )
            except Exception as exc:
                st.warning(f"The answer is ready, but audio could not be created: {exc}")
            st.session_state.qa.append(
                {"question": prompt_question, "answer": answer, "audio": audio_answer}
            )
        except Exception as exc:
            st.error(f"We couldn't answer that question. Please try again. Details: {exc}")

    for item in st.session_state.get("qa", []):
        with st.chat_message("user"):
            st.write(item["question"])
        with st.chat_message("assistant"):
            st.write(item["answer"])
            if item.get("audio"):
                st.audio(item["audio"], format="audio/mp3")


def _show_trends() -> None:
    st.subheader("Health trends")
    patient = st.session_state.patient.strip() or "Me"
    rows = get_trend_rows(patient)
    if not rows:
        st.info("No saved reports for this patient yet. Save a report or load the demo data.")
        return

    frame = pd.DataFrame(rows)
    frame["report_date"] = pd.to_datetime(frame["report_date"], errors="coerce")
    frame = frame.dropna(subset=["report_date", "value"])
    counts_by_test = frame.groupby("standard_name")["report_id"].nunique()
    available = sorted(counts_by_test[counts_by_test >= 2].index.tolist())
    if available:
        selected = st.selectbox("Test to track", available)
        trend = frame[frame["standard_name"] == selected].sort_values("report_date")
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=trend["report_date"],
                y=trend["value"],
                mode="lines+markers+text",
                text=trend["value"].map(lambda value: f"{value:g}"),
                textposition="top center",
                name=selected,
            )
        )
        first = trend.iloc[0]
        low_values = trend["ref_low"].dropna()
        high_values = trend["ref_high"].dropna()
        low = low_values.iloc[-1] if not low_values.empty else None
        high = high_values.iloc[-1] if not high_values.empty else None
        if low is not None and high is not None:
            fig.add_hrect(
                y0=low,
                y1=high,
                fillcolor="green",
                opacity=0.12,
                line_width=0,
                annotation_text="Reference range",
            )
        elif low is not None or high is not None:
            limit = low if low is not None else high
            fig.add_hline(y=limit, line_dash="dash", line_color="green")
        fig.update_layout(
            title=f"{selected} over time",
            xaxis_title="Report date",
            yaxis_title=str(trend.iloc[-1].get("unit") or "Value"),
            template="plotly_white",
        )
        st.plotly_chart(fig, width="stretch")

        latest = trend.iloc[-1]
        change = float(latest["value"]) - float(first["value"])
        if float(first["value"]) != 0:
            percent_change = change / abs(float(first["value"])) * 100
            change_text = f"{percent_change:+.1f}%"
        else:
            change_text = f"{change:+g} (percentage unavailable from a zero baseline)"
        st.write(
            f"From {first['report_date'].date()} to {latest['report_date'].date()}, "
            f"{selected} changed from {first['value']:g} to {latest['value']:g} "
            f"({change_text}). Latest status: **{latest['status']}**."
        )
    else:
        st.info("A test needs values in at least two saved reports to show a trend.")

    reports = list_reports(patient)
    if reports:
        st.markdown("### Saved reports")
        report_frame = pd.DataFrame(reports)[
            ["id", "report_date", "report_type", "lab_name", "created_at"]
        ]
        st.dataframe(report_frame, width="stretch", hide_index=True)
        with st.expander("Delete a saved report"):
            report_options = {
                f"#{item['id']} — {item['report_date']} — {item['report_type']}": item["id"]
                for item in reports
            }
            selection = st.selectbox("Report", list(report_options))
            if st.button("Delete selected report"):
                try:
                    delete_report(report_options[selection])
                    st.success("Report deleted.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"The report could not be deleted. Details: {exc}")


st.sidebar.title("🩺 MediLens")
st.sidebar.caption("A friendly guide to understanding lab results")
st.sidebar.selectbox("Explanation language", list(LANGUAGES), key="language")
st.sidebar.text_input("Patient profile", value="Me", key="patient")
if not GEMINI_API_KEY:
    st.sidebar.error("Gemini API key is missing. Add GEMINI_API_KEY to your .env file.")
st.sidebar.caption(f"Model: {GEMINI_MODEL}")
st.sidebar.info(DISCLAIMER)

for key, default in {
    "language": "English",
    "patient": "Me",
    "report": None,
    "tests": [],
    "explanation": "",
    "explanation_lang": "",
    "explanation_audio": None,
    "saved_id": None,
    "qa": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.title("MediLens")
st.caption("Understand your laboratory results in simple language.")
analyze_tab, question_tab, trends_tab = st.tabs(
    ["📄 Analyze report", "💬 Ask a question", "📈 Health trends"]
)
with analyze_tab:
    _show_analysis()
with question_tab:
    _show_questions()
with trends_tab:
    _show_trends()
