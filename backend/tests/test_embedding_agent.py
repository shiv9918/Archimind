from pathlib import Path

from app.agents.ast_parser import parse_file
from app.agents.embedding_agent import HybridRetriever, documents_from_parsed_files
from app.agents.scanner_agent import scan_repository

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def test_hybrid_retrieval_finds_relevant_function(tmp_path):
    overview = scan_repository(FIXTURE)
    parsed_files = [parse_file(FIXTURE, rel, lang) for rel, lang in overview.parseable_files]
    documents = documents_from_parsed_files(parsed_files)
    assert documents

    retriever = HybridRetriever(tmp_path / "vectors", tmp_path / "bm25.pkl")
    retriever.build(documents)

    results = retriever.search("create a new user", top_k=5)
    assert results
    assert any("create_user" in r.id for r in results)


def test_search_before_build_returns_empty(tmp_path):
    retriever = HybridRetriever(tmp_path / "vectors", tmp_path / "bm25.pkl")
    assert retriever.search("anything") == []
