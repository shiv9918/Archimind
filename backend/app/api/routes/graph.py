from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents.knowledge_graph import GraphEdge, GraphNode, NetworkXGraphStore
from app.db.models import Repository
from app.db.session import get_db
from app.services.workspace import RepoWorkspace

router = APIRouter(prefix="/api/repos", tags=["graph"])

_MAX_DEFAULT_NODES = 300


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

    if node_id:
        nodes, edges = store.get_subgraph(node_id, depth=depth)
        if not nodes:
            raise HTTPException(404, f"Node not found: {node_id}")
        truncated = False
    else:
        all_nodes = store.all_nodes()
        all_edges = store.all_edges()
        truncated = len(all_nodes) > _MAX_DEFAULT_NODES
        if truncated:
            degree: dict[str, int] = {}
            for e in all_edges:
                degree[e.source] = degree.get(e.source, 0) + 1
                degree[e.target] = degree.get(e.target, 0) + 1
            all_nodes.sort(key=lambda n: degree.get(n.id, 0), reverse=True)
            nodes = all_nodes[:_MAX_DEFAULT_NODES]
            node_ids = {n.id for n in nodes}
            edges = [e for e in all_edges if e.source in node_ids and e.target in node_ids]
        else:
            nodes, edges = all_nodes, all_edges

    return {
        "nodes": [_node_dict(n) for n in nodes],
        "edges": [_edge_dict(e) for e in edges],
        "truncated": truncated,
    }


@router.get("/{repo_id}/graph/stats")
def get_graph_stats(repo_id: str, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    store = _load_store(repo_id)
    return store.stats()
