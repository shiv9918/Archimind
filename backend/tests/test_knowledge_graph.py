from pathlib import Path

from app.agents.ast_parser import parse_file
from app.agents.ast_parser.base import ParsedFile, ParsedImport
from app.agents.knowledge_graph import NetworkXGraphStore, _compute_package_groups, build_graph
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


def test_local_python_import_resolves_to_file_node(tmp_path):
    # app/services.py does `from app.models import AdminUser, User` -- a same-repo
    # import that should resolve to a File->File edge, not a generic Module node.
    store = NetworkXGraphStore(tmp_path / "graph.json")
    build_graph(store, _parsed_files())

    imports_edges = [e for e in store.all_edges() if e.type == "imports"]
    assert any(e.source == "file:app/services.py" and e.target == "file:app/models.py" for e in imports_edges)

    module_edge_targets = {e.target for e in imports_edges if e.target.startswith("module:")}
    assert "module:app.models" not in module_edge_targets


def test_external_imports_stay_module_nodes_not_resolved_to_files(tmp_path):
    # app/utils.py imports stdlib `os`; frontend/src/utils.js imports the npm
    # package `react` -- neither exists as a file in this repo, so both must
    # stay Module nodes rather than being (incorrectly) resolved to a File.
    store = NetworkXGraphStore(tmp_path / "graph.json")
    build_graph(store, _parsed_files())

    module_labels = {n.label for n in store.all_nodes() if n.type == "Module"}
    assert "os" in module_labels
    assert "react" in module_labels

    imports_edges = [e for e in store.all_edges() if e.type == "imports"]
    assert any(e.source == "file:app/utils.py" and e.target == "module:os" for e in imports_edges)
    assert any(e.source == "file:frontend/src/utils.js" and e.target == "module:react" for e in imports_edges)


def _synthetic_package_files() -> list[ParsedFile]:
    files = []
    for pkg, count in (("pkgA", 5), ("pkgB", 5), ("pkgC", 4)):
        for i in range(count):
            files.append(ParsedFile(path=f"{pkg}/file{i}.py", language="Python"))

    # Two separate files in pkgA import files in pkgB -- should aggregate to a
    # single pkgA->pkgB Package edge with weight 2, not two separate edges.
    files[0].imports = [ParsedImport(module="pkgB.file0", level=0)]
    files[1].imports = [ParsedImport(module="pkgB.file1", level=0)]
    return files


def test_compute_package_groups_below_threshold_returns_empty():
    small_repo = [ParsedFile(path=f"app/file{i}.py", language="Python") for i in range(5)]
    assert _compute_package_groups(small_repo) == {}


def test_compute_package_groups_assigns_folder_based_groups():
    groups = _compute_package_groups(_synthetic_package_files())
    assert groups["pkgA/file0.py"] == "pkgA"
    assert groups["pkgB/file0.py"] == "pkgB"
    assert groups["pkgC/file0.py"] == "pkgC"


def test_build_graph_creates_package_nodes_and_aggregated_edges(tmp_path):
    store = NetworkXGraphStore(tmp_path / "graph.json")
    build_graph(store, _synthetic_package_files())

    package_nodes = {n.label: n for n in store.all_nodes() if n.type == "Package"}
    assert set(package_nodes) == {"pkgA", "pkgB", "pkgC"}
    assert package_nodes["pkgA"].properties["file_count"] == 5
    assert package_nodes["pkgC"].properties["file_count"] == 4

    contains_edges = [e for e in store.all_edges() if e.type == "contains"]
    assert len([e for e in contains_edges if e.source == "package:pkgA"]) == 5

    package_import_edges = [
        e for e in store.all_edges() if e.type == "imports" and e.source == "package:pkgA" and e.target == "package:pkgB"
    ]
    assert len(package_import_edges) == 1  # aggregated, not one per file pair
    assert package_import_edges[0].properties["weight"] == 2

    # pkgC has no cross-package imports at all -- no imports edges should reference it.
    assert not any(e.type == "imports" and "pkgC" in (e.source, e.target) for e in store.all_edges())


def test_clicking_package_reveals_its_files(tmp_path):
    store = NetworkXGraphStore(tmp_path / "graph.json")
    build_graph(store, _synthetic_package_files())

    nodes, edges = store.get_subgraph("package:pkgA", depth=1)
    node_ids = {n.id for n in nodes}
    assert "file:pkgA/file0.py" in node_ids
    assert "file:pkgA/file4.py" in node_ids
    assert "package:pkgB" in node_ids  # the aggregated import edge target is also revealed
