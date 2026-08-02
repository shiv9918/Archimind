from pathlib import Path

from app.agents.architecture_agent import detect_architecture
from app.agents.scanner_agent import scan_repository

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_detect_architecture_returns_report_with_confidence():
    overview = scan_repository(FIXTURE)
    report = detect_architecture(FIXTURE, overview)

    assert report.primary_pattern
    assert 0.0 <= report.primary_confidence <= 1.0
    assert report.summary
    assert isinstance(report.service_count, int)
