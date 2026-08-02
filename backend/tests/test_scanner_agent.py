from pathlib import Path

from app.agents.scanner_agent import scan_repository

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_scan_repository_detects_languages_and_frameworks():
    overview = scan_repository(FIXTURE)

    assert overview.languages.get("Python", 0) >= 4
    assert overview.languages.get("JavaScript", 0) >= 1
    assert overview.has_docker is True
    assert "GitHub Actions" in overview.ci_cd
    assert overview.has_readme is True
    assert overview.frameworks & {"React", "Express.js"}
    assert overview.dependency_count > 0
    assert len(overview.parseable_files) >= 5


def test_scan_repository_dependency_manifests_parsed():
    overview = scan_repository(FIXTURE)
    assert "pip" in overview.package_managers
    assert "npm" in overview.package_managers
