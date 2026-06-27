from app.readiness.models import ReadinessReport, ReadinessSignal
from app.readiness.markdown import report_to_markdown


def test_report_defaults_and_shape():
    report = ReadinessReport(verdict="ready")
    assert report.verdict == "ready"
    assert report.signals == []
    assert report.questions == []


def test_signal_fields():
    sig = ReadinessSignal(kind="vagueness", message="The request is vague.")
    assert sig.kind == "vagueness"
    assert sig.message == "The request is vague."


def test_markdown_includes_verdict_and_questions():
    report = ReadinessReport(
        verdict="clarify",
        signals=[ReadinessSignal(kind="vagueness", message="The request is vague.")],
        questions=["What platform?"],
    )
    md = report_to_markdown(report)
    assert "clarify" in md.lower()
    assert "What platform?" in md
