from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents.knowledge_graph import GraphEdge, GraphNode, NetworkXGraphStore
from app.db.models import Repository
from app.db.session import get_db
from app.services.workspace import RepoWorkspace

router = APIRouter(prefix="/api/repos", tags=["graph"])

_MAX_DEFAULT_NODES = 150
# The default (no node_id) view is an architecture-level map. When the repo is
# big enough to have Package (folder-based) nodes, those ARE the overview --
# a handful of nodes showing which part of the codebase depends on which.
# Smaller repos (below the Package-grouping threshold) fall back to a
# File+Class overview instead. Function/Module nodes are always left out of
# the initial view -- they only appear once the user clicks a node to expand
# its neighbors, since showing them upfront is what made the graph unreadable.
_PACKAGE_OVERVIEW_TYPES = {"Package"}
_FILE_OVERVIEW_TYPES = {"File", "Class"}


def _node_dict(n: GraphNode) -> dict:
    return {"id": n.id, "type": n.type, "label": n.label, "properties": n.properties}


def _edge_dict(e: GraphEdge) -> dict:
    return {"source": e.source, "target": e.target, "type": e.type}


def _load_store(repo_id: str) -> NetworkXGraphStore:
    workspace = RepoWorkspace(repo_id)
    if not workspace.graph_file.exists():
        raise HTTPException(404, "Knowledge graph not built yet -- scan the repository first")
    store = NetworkXGraphStore(workspace.graph_file)
    store.load()
    return store


@router.get("/{repo_id}/graph")
def get_graph(
    repo_id: str,
    node_id: str | None = Query(default=None),
    depth: int = Query(default=1, ge=1, le=4),
    db: Session = Depends(get_db),
):
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")

    store = _load_store(repo_id)
    view: str | None = None

    if node_id:
        nodes, edges = store.get_subgraph(node_id, depth=depth)
        if not nodes:
            raise HTTPException(404, f"Node not found: {node_id}")
        truncated = False
    else:
        all_nodes = store.all_nodes()
        all_edges = store.all_edges()

        degree: dict[str, int] = {}
        for e in all_edges:
            degree[e.source] = degree.get(e.source, 0) + 1
            degree[e.target] = degree.get(e.target, 0) + 1

        has_packages = any(n.type == "Package" for n in all_nodes)
        overview_types = _PACKAGE_OVERVIEW_TYPES if has_packages else _FILE_OVERVIEW_TYPES
        view = "package" if has_packages else "file"

        overview_nodes = sorted(
            (n for n in all_nodes if n.type in overview_types),
            key=lambda n: degree.get(n.id, 0),
            reverse=True,
        )

        if len(overview_nodes) > _MAX_DEFAULT_NODES:
            nodes = overview_nodes[:_MAX_DEFAULT_NODES]
        else:
            nodes = overview_nodes
            remaining = _MAX_DEFAULT_NODES - len(nodes)
            # Package nodes are deliberately capped low (~30) to stay readable --
            # never pad that out with functions/modules. Only the File+Class
            # fallback (small repos with no packages) gets padded so it isn't sparse.
            if remaining > 0 and not has_packages:
                other_nodes = sorted(
                    (n for n in all_nodes if n.type not in overview_types),
                    key=lambda n: degree.get(n.id, 0),
                    reverse=True,
                )
                nodes = nodes + other_nodes[:remaining]

        # "Truncated" means we cut down the overview itself (too many packages,
        # or too many files/classes in the fallback case) -- not that other
        # node types (functions/modules) are hidden, since that's by design.
        truncated = len(nodes) < len(overview_nodes)
        node_ids = {n.id for n in nodes}
        edges = [e for e in all_edges if e.source in node_ids and e.target in node_ids]

    return {
        "nodes": [_node_dict(n) for n in nodes],
        "edges": [_edge_dict(e) for e in edges],
        "truncated": truncated,
        "view": view,
    }


@router.get("/{repo_id}/graph/stats")
def get_graph_stats(repo_id: str, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    store = _load_store(repo_id)
    return store.stats()
