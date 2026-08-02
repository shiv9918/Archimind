from pathlib import Path

from app.agents.ast_parser import parse_file
from app.agents.knowledge_graph import NetworkXGraphStore, build_graph
from app.agents.scanner_agent import scan_repository

FIXTURE = Path(__file__).parent / "fixtures" / "sample_repo"


def _parsed_files():
    overview = scan_repository(FIXTURE)
    return [parse_file(FIXTURE, rel, lang) for rel, lang in overview.parseable_files]


def test_build_graph_creates_expected_nodes_and_edges(tmp_path):
    store = NetworkXGraphStore(tmp_path / "graph.json")
    build_graph(store, _parsed_files())

    node_types = {n.type for n in store.all_nodes()}
    assert {"File", "Class", "Function"} <= node_types

    edge_types = {e.type for e in store.all_edges()}
    assert {"defines", "inherits", "calls"} <= edge_types

    inherits_edges = [e for e in store.all_edges() if e.type == "inherits"]
    assert any("AdminUser" in e.source and e.target.endswith(":User") for e in inherits_edges)


def test_graph_persists_and_reloads(tmp_path):
    graph_file = tmp_path / "graph.json"
    store = NetworkXGraphStore(graph_file)
    build_graph(store, _parsed_files())
    store.save()

    reloaded = NetworkXGraphStore(graph_file)
    reloaded.load()
    assert len(reloaded.all_nodes()) == len(store.all_nodes())
    assert len(reloaded.all_edges()) == len(store.all_edges())


def test_get_subgraph_expands_neighbors(tmp_path):
    store = NetworkXGraphStore(tmp_path / "graph.json")
    build_graph(store, _parsed_files())

    file_node = next(n for n in store.all_nodes() if n.type == "File" and n.label == "app/models.py")
    nodes, edges = store.get_subgraph(file_node.id, depth=1)
    assert len(nodes) > 1
    assert any(n.type == "Class" for n in nodes)
