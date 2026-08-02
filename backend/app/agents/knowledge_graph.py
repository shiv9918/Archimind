"""Knowledge Graph Builder.

`GraphStore` is a small abstract interface so the storage backend can be
swapped later (e.g. for Neo4j) without touching any calling code. The only
implementation shipped in this phase is `NetworkXGraphStore`, which keeps the
graph in memory and persists it to a per-repo JSON file on disk.

`build_graph` turns the AST Parsing Agent's output into graph nodes/edges:
File/Class/Function/Module nodes, and imports/defines/inherits/calls edges.
Inheritance and call-target resolution are done by best-effort name
matching (no full type inference) -- documented limitation, same approach
most lightweight static analyzers use without a type checker.
"""

import json
import posixpath
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

from app.agents.ast_parser.base import ParsedFile, ParsedImport


@dataclass
class GraphNode:
    id: str
    type: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    type: str
    properties: dict[str, Any] = field(default_factory=dict)


class GraphStore(ABC):
    @abstractmethod
    def add_node(self, node: GraphNode) -> None: ...

    @abstractmethod
    def add_edge(self, edge: GraphEdge) -> None: ...

    @abstractmethod
    def get_node(self, node_id: str) -> GraphNode | None: ...

    @abstractmethod
    def all_nodes(self) -> list[GraphNode]: ...

    @abstractmethod
    def all_edges(self) -> list[GraphEdge]: ...

    @abstractmethod
    def get_subgraph(self, node_id: str, depth: int = 1) -> tuple[list[GraphNode], list[GraphEdge]]: ...

    @abstractmethod
    def stats(self) -> dict: ...

    @abstractmethod
    def save(self) -> None: ...

    @abstractmethod
    def load(self) -> None: ...


class NetworkXGraphStore(GraphStore):
    def __init__(self, persist_path: Path):
        self.persist_path = persist_path
        self.graph = nx.MultiDiGraph()

    def add_node(self, node: GraphNode) -> None:
        self.graph.add_node(node.id, type=node.type, label=node.label, **node.properties)

    def add_edge(self, edge: GraphEdge) -> None:
        self.graph.add_edge(edge.source, edge.target, type=edge.type, **edge.properties)

    def _node_from_data(self, node_id: str, data: dict) -> GraphNode:
        props = {k: v for k, v in data.items() if k not in ("type", "label")}
        return GraphNode(id=node_id, type=data.get("type", "Unknown"), label=data.get("label", node_id), properties=props)

    def get_node(self, node_id: str) -> GraphNode | None:
        if node_id not in self.graph.nodes:
            return None
        return self._node_from_data(node_id, self.graph.nodes[node_id])

    def all_nodes(self) -> list[GraphNode]:
        return [self._node_from_data(nid, data) for nid, data in self.graph.nodes(data=True)]

    def all_edges(self) -> list[GraphEdge]:
        edges = []
        for source, target, data in self.graph.edges(data=True):
            props = {k: v for k, v in data.items() if k != "type"}
            edges.append(GraphEdge(source=source, target=target, type=data.get("type", "related"), properties=props))
        return edges

    def get_subgraph(self, node_id: str, depth: int = 1) -> tuple[list[GraphNode], list[GraphEdge]]:
        if node_id not in self.graph.nodes:
            return [], []

        visited = {node_id}
        frontier = {node_id}
        for _ in range(depth):
            next_frontier = set()
            for n in frontier:
                next_frontier |= set(self.graph.successors(n))
                next_frontier |= set(self.graph.predecessors(n))
            next_frontier -= visited
            visited |= next_frontier
            frontier = next_frontier

        nodes = [self._node_from_data(nid, self.graph.nodes[nid]) for nid in visited]
        edges = []
        for source, target, data in self.graph.edges(data=True):
            if source in visited and target in visited:
                props = {k: v for k, v in data.items() if k != "type"}
                edges.append(GraphEdge(source=source, target=target, type=data.get("type", "related"), properties=props))
        return nodes, edges

    def stats(self) -> dict:
        node_counts: dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            t = data.get("type", "Unknown")
            node_counts[t] = node_counts.get(t, 0) + 1

        edge_counts: dict[str, int] = {}
        for _, _, data in self.graph.edges(data=True):
            t = data.get("type", "related")
            edge_counts[t] = edge_counts.get(t, 0) + 1

        # Coupling/fan-in should reflect real code relationships (imports/calls/
        # inherits), not structural bookkeeping edges (defines/contains) --
        # otherwise a package that simply contains many files looks "coupled".
        _COUPLING_EDGE_TYPES = {"imports", "calls", "inherits"}
        coupling_graph = nx.MultiDiGraph()
        coupling_graph.add_nodes_from(self.graph.nodes)
        for source, target, data in self.graph.edges(data=True):
            if data.get("type") in _COUPLING_EDGE_TYPES:
                coupling_graph.add_edge(source, target)

        fan_in = sorted(
            ((n, coupling_graph.in_degree(n)) for n in coupling_graph.nodes),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        fan_out = sorted(
            ((n, coupling_graph.out_degree(n)) for n in coupling_graph.nodes),
            key=lambda x: x[1],
            reverse=True,
        )[:10]

        return {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "nodes_by_type": node_counts,
            "edges_by_type": edge_counts,
            "most_depended_on": [{"id": n, "in_degree": d} for n, d in fan_in if d > 0],
            "most_coupled": [{"id": n, "out_degree": d} for n, d in fan_out if d > 0],
        }

    def save(self) -> None:
        data = nx.node_link_data(self.graph)
        self.persist_path.write_text(json.dumps(data), encoding="utf-8")

    def load(self) -> None:
        if not self.persist_path.exists():
            return
        data = json.loads(self.persist_path.read_text(encoding="utf-8"))
        self.graph = nx.node_link_graph(data, multigraph=True, directed=True)


def _resolve_python_import(importer_path: str, imp: ParsedImport, path_index: dict[str, str]) -> str | None:
    """Best-effort resolution of a Python import to a file already in this repo's graph."""
    importer_dir = importer_path.rsplit("/", 1)[0] if "/" in importer_path else ""

    if imp.level > 0:
        parts = importer_dir.split("/") if importer_dir else []
        up = imp.level - 1
        if up > 0:
            if up > len(parts):
                return None
            parts = parts[:-up]
        base_dir = "/".join(parts)
        module_path = imp.module.replace(".", "/") if imp.module else ""
        candidate_base = f"{base_dir}/{module_path}" if module_path else base_dir
    else:
        if not imp.module:
            return None
        candidate_base = imp.module.replace(".", "/")

    candidate_base = candidate_base.strip("/")
    for suffix in (".py", "/__init__.py"):
        candidate = f"{candidate_base}{suffix}"
        if candidate in path_index:
            return path_index[candidate]
    return None


_JS_TS_RESOLVE_SUFFIXES = ("", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx", "/index.js", "/index.jsx")


def _resolve_jsts_import(importer_path: str, module: str, path_index: dict[str, str]) -> str | None:
    """Resolve relative ("./foo", "../foo") JS/TS imports to a file in this repo's graph.

    Bare specifiers (npm packages, tsconfig path aliases like "@/...") are left
    unresolved -- they fall back to a Module node since resolving them would
    require reading package.json/tsconfig.json, which is out of scope here.
    """
    if not (module.startswith("./") or module.startswith("../")):
        return None

    importer_dir = importer_path.rsplit("/", 1)[0] if "/" in importer_path else ""
    candidate_base = posixpath.normpath(posixpath.join(importer_dir, module))

    for suffix in _JS_TS_RESOLVE_SUFFIXES:
        candidate = f"{candidate_base}{suffix}"
        if candidate in path_index:
            return path_index[candidate]
    return None


_MAX_PACKAGES = 30
_MIN_FILES_FOR_PACKAGES = 12


def _compute_package_groups(parsed_files: list[ParsedFile]) -> dict[str, str]:
    """Maps each file path to a "package" (folder-based) group path.

    Starts from each file's exact parent directory, then progressively rolls
    groups up to shallower ancestor directories until the total group count
    fits under the cap -- so a repo with many nested subfolders still gets a
    small, readable set of top-level architecture nodes instead of one node
    per directory.
    """
    paths = [pf.path for pf in parsed_files if not pf.error]
    if len(paths) < _MIN_FILES_FOR_PACKAGES:
        return {}

    def dir_parts(path: str) -> list[str]:
        return path.split("/")[:-1]

    max_depth = max((len(dir_parts(p)) for p in paths), default=0)

    for depth in range(max_depth, 0, -1):
        groups = {p: "/".join(dir_parts(p)[:depth]) or "(root)" for p in paths}
        if len(set(groups.values())) <= _MAX_PACKAGES:
            return groups

    return {p: "/".join(dir_parts(p)[:1]) or "(root)" for p in paths}


def build_graph(store: GraphStore, parsed_files: list[ParsedFile]) -> None:
    name_index: dict[str, list[str]] = {}
    path_index: dict[str, str] = {pf.path: f"file:{pf.path}" for pf in parsed_files if not pf.error}
    file_to_file_imports: list[tuple[str, str]] = []

    for pf in parsed_files:
        if pf.error:
            continue

        file_id = f"file:{pf.path}"
        store.add_node(GraphNode(id=file_id, type="File", label=pf.path, properties={"language": pf.language}))

        for imp in pf.imports:
            resolved_file_id: str | None = None
            if pf.language == "Python":
                resolved_file_id = _resolve_python_import(pf.path, imp, path_index)
            elif pf.language in ("JavaScript", "TypeScript") and imp.module:
                resolved_file_id = _resolve_jsts_import(pf.path, imp.module, path_index)

            if resolved_file_id and resolved_file_id != file_id:
                store.add_edge(GraphEdge(source=file_id, target=resolved_file_id, type="imports"))
                file_to_file_imports.append((file_id, resolved_file_id))
                continue

            if not imp.module:
                continue
            module_id = f"module:{imp.module}"
            store.add_node(GraphNode(id=module_id, type="Module", label=imp.module))
            store.add_edge(GraphEdge(source=file_id, target=module_id, type="imports"))

        for cls in pf.classes:
            class_id = f"class:{pf.path}:{cls.qualified_name}"
            store.add_node(
                GraphNode(
                    id=class_id,
                    type="Class",
                    label=cls.name,
                    properties={"file": pf.path, "line": cls.line, "docstring": cls.docstring or "", "bases": cls.bases},
                )
            )
            store.add_edge(GraphEdge(source=file_id, target=class_id, type="defines"))
            name_index.setdefault(cls.name, []).append(class_id)

            for method in cls.methods:
                method_id = f"func:{pf.path}:{method.qualified_name}"
                store.add_node(
                    GraphNode(
                        id=method_id,
                        type="Function",
                        label=method.name,
                        properties={
                            "file": pf.path,
                            "line": method.line,
                            "is_method": True,
                            "parameters": method.parameters,
                            "docstring": method.docstring or "",
                        },
                    )
                )
                store.add_edge(GraphEdge(source=class_id, target=method_id, type="defines"))
                name_index.setdefault(method.name, []).append(method_id)

        for func in pf.functions:
            func_id = f"func:{pf.path}:{func.qualified_name}"
            store.add_node(
                GraphNode(
                    id=func_id,
                    type="Function",
                    label=func.name,
                    properties={
                        "file": pf.path,
                        "line": func.line,
                        "is_method": False,
                        "parameters": func.parameters,
                        "docstring": func.docstring or "",
                    },
                )
            )
            store.add_edge(GraphEdge(source=file_id, target=func_id, type="defines"))
            name_index.setdefault(func.name, []).append(func_id)

    # Second pass: best-effort resolution of inherits/calls edges by simple name match.
    for pf in parsed_files:
        if pf.error:
            continue

        for cls in pf.classes:
            class_id = f"class:{pf.path}:{cls.qualified_name}"
            for base in cls.bases:
                for target_id in name_index.get(base, []):
                    if target_id.startswith("class:") and target_id != class_id:
                        store.add_edge(GraphEdge(source=class_id, target=target_id, type="inherits"))

            for method in cls.methods:
                method_id = f"func:{pf.path}:{method.qualified_name}"
                for call_name in set(method.calls):
                    for target_id in name_index.get(call_name, []):
                        if target_id.startswith("func:") and target_id != method_id:
                            store.add_edge(GraphEdge(source=method_id, target=target_id, type="calls"))

        for func in pf.functions:
            func_id = f"func:{pf.path}:{func.qualified_name}"
            for call_name in set(func.calls):
                for target_id in name_index.get(call_name, []):
                    if target_id.startswith("func:") and target_id != func_id:
                        store.add_edge(GraphEdge(source=func_id, target=target_id, type="calls"))

    # Third pass: group files into "Package" nodes (folder-based) so the
    # default graph view is a small, readable architecture-level map instead
    # of one node per file. Clicking a Package reveals its files via the
    # existing "contains" edges; clicking a File still reveals its
    # classes/functions as before -- this reuses get_subgraph() as-is.
    groups = _compute_package_groups(parsed_files)
    if groups:
        package_id_by_group: dict[str, str] = {}
        file_count_by_group: dict[str, int] = {}
        for group_path in groups.values():
            file_count_by_group[group_path] = file_count_by_group.get(group_path, 0) + 1

        for group_path in file_count_by_group:
            package_id = f"package:{group_path}"
            package_id_by_group[group_path] = package_id
            label = group_path.rsplit("/", 1)[-1] if group_path != "(root)" else "(root)"
            store.add_node(
                GraphNode(
                    id=package_id,
                    type="Package",
                    label=label,
                    properties={"path": group_path, "file_count": file_count_by_group[group_path]},
                )
            )

        for file_path, group_path in groups.items():
            store.add_edge(GraphEdge(source=package_id_by_group[group_path], target=f"file:{file_path}", type="contains"))

        package_edge_weight: dict[tuple[str, str], int] = {}
        for source_file_id, target_file_id in file_to_file_imports:
            source_path = source_file_id.removeprefix("file:")
            target_path = target_file_id.removeprefix("file:")
            if source_path not in groups or target_path not in groups:
                continue
            source_group, target_group = groups[source_path], groups[target_path]
            if source_group == target_group:
                continue
            pair = (package_id_by_group[source_group], package_id_by_group[target_group])
            package_edge_weight[pair] = package_edge_weight.get(pair, 0) + 1

        for (source_package_id, target_package_id), weight in package_edge_weight.items():
            store.add_edge(
                GraphEdge(source=source_package_id, target=target_package_id, type="imports", properties={"weight": weight})
            )
