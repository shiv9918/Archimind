"""Orchestrator -- runs Scan -> Parse -> Build Graph -> Embed -> Score as one
background job, updating the ScanJob row so the frontend can poll progress.

This runs synchronously inside a FastAPI BackgroundTasks worker (no
Celery/Redis in this phase -- documented upgrade path for scale). A single
imported repo is scanned end-to-end in one process; multiple repos can be
scanned concurrently since each gets its own SQLAlchemy session and workspace.
"""

import traceback
from datetime import datetime, timezone

from app.agents.architecture_agent import detect_architecture
from app.agents.ast_parser import parse_file
from app.agents.embedding_agent import HybridRetriever, documents_from_parsed_files
from app.agents.health_scorer import compute_health_scores, generate_recommendations
from app.agents.knowledge_graph import NetworkXGraphStore, build_graph
from app.agents.scanner_agent import scan_repository
from app.db.models import Repository, ScanJob
from app.db.session import SessionLocal
from app.services.workspace import RepoWorkspace


def _set_stage(db, job: ScanJob, stage: str) -> None:
    job.stage = stage
    db.commit()


def run_pipeline(repo_id: str, scan_job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ScanJob, scan_job_id)
        repo = db.get(Repository, repo_id)
        if job is None or repo is None:
            return

        job.status = "running"
        db.commit()

        workspace = RepoWorkspace(repo_id)
        source_dir = workspace.source_dir

        _set_stage(db, job, "scanning")
        overview = scan_repository(source_dir)

        _set_stage(db, job, "parsing")
        parsed_files = [parse_file(source_dir, rel_path, language) for rel_path, language in overview.parseable_files]

        _set_stage(db, job, "building_graph")
        store = NetworkXGraphStore(workspace.graph_file)
        build_graph(store, parsed_files)
        store.save()
        graph_stats = store.stats()

        _set_stage(db, job, "embedding")
        documents = documents_from_parsed_files(parsed_files)
        retriever = HybridRetriever(workspace.vector_dir, workspace.bm25_file)
        retriever.build(documents)

        _set_stage(db, job, "scoring")
        architecture = detect_architecture(source_dir, overview)
        health = compute_health_scores(source_dir, overview, parsed_files, architecture, graph_stats)
        recommendations = generate_recommendations(health)

        parse_errors = [{"file": pf.path, "error": pf.error} for pf in parsed_files if pf.error]

        result = {
            "overview": overview.to_dict(),
            "graph_stats": graph_stats,
            "architecture": architecture.to_dict(),
            "health": health.to_dict(),
            "recommendations": recommendations,
            "parse_errors": parse_errors[:100],
            "files_parsed": len(parsed_files),
        }

        job.status = "done"
        job.stage = "done"
        job.result = result
        job.finished_at = datetime.now(timezone.utc)
        repo.status = "ready"
        db.commit()

    except Exception as exc:
        db.rollback()
        job = db.get(ScanJob, scan_job_id)
        repo = db.get(Repository, repo_id)
        if job is not None:
            job.status = "failed"
            job.error_message = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-2000:]}"
            job.finished_at = datetime.now(timezone.utc)
        if repo is not None:
            repo.status = "failed"
        db.commit()
    finally:
        db.close()
