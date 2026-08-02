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
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

from app.agents.ast_parser.base import ParsedFile


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

        fan_in = sorted(
            ((n, self.graph.in_degree(n)) for n in self.graph.nodes),
            key=lambda x: x[1],
            reverse=True,
        )[:10]
        fan_out = sorted(
            ((n, self.graph.out_degree(n)) for n in self.graph.nodes),
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


def build_graph(store: GraphStore, parsed_files: list[ParsedFile]) -> None:
    name_index: dict[str, list[str]] = {}

    for pf in parsed_files:
        if pf.error:
            continue

        file_id = f"file:{pf.path}"
        store.add_node(GraphNode(id=file_id, type="File", label=pf.path, properties={"language": pf.language}))

        for imp in pf.imports:
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
