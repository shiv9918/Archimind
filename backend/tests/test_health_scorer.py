from pathlib import Path

from app.agents.architecture_agent import detect_architecture
from app.agents.ast_parser import parse_file
from app.agents.health_scorer import compute_health_scores, generate_recommendations
from app.agents.knowledge_graph import NetworkXGraphStore, build_graph
from app.agents.scanner_agent import scan_repository

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_compute_health_scores(tmp_path):
    overview = scan_repository(FIXTURE)
    parsed_files = [parse_file(FIXTURE, rel, lang) for rel, lang in overview.parseable_files]

    store = NetworkXGraphStore(tmp_path / "graph.json")
    build_graph(store, parsed_files)
    graph_stats = store.stats()

    architecture = detect_architecture(FIXTURE, overview)
    health = compute_health_scores(FIXTURE, overview, parsed_files, architecture, graph_stats)

    for value in (
        health.documentation_score,
        health.complexity_score,
        health.test_coverage_estimated,
        health.dependency_health_score,
        health.security_score_basic,
        health.architecture_score,
    ):
        assert 0 <= value <= 100

    # The fixture's app/config_sample.py has a fake hardcoded API key.
    assert health.security_findings
    assert any(f["rule"] == "Generic hardcoded secret/API key" for f in health.security_findings)

    # requirements.txt pins flask but leaves sqlalchemy unpinned.
    assert health.dependency_health_score < 100

    recs = generate_recommendations(health)
    assert len(recs) > 0


def test_health_to_dict_has_all_expected_keys(tmp_path):
    overview = scan_repository(FIXTURE)
    parsed_files = [parse_file(FIXTURE, rel, lang) for rel, lang in overview.parseable_files]
    store = NetworkXGraphStore(tmp_path / "graph.json")
    build_graph(store, parsed_files)
    architecture = detect_architecture(FIXTURE, overview)
    health = compute_health_scores(FIXTURE, overview, parsed_files, architecture, store.stats())

    data = health.to_dict()
    expected_keys = {
        "architecture_score", "documentation_score", "complexity_score", "test_coverage_estimated",
        "dependency_health_score", "security_score_basic", "technical_debt_index", "performance_score",
        "notes", "security_findings",
    }
    assert expected_keys <= data.keys()
    assert data["performance_score"] is None
