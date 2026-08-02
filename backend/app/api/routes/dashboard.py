from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Repository, ScanJob
from app.db.session import get_db

router = APIRouter(prefix="/api/repos", tags=["dashboard"])


@router.get("/{repo_id}/dashboard")
def get_dashboard(repo_id: str, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")

    job = (
        db.query(ScanJob)
        .filter(ScanJob.repository_id == repo_id, ScanJob.status == "done")
        .order_by(ScanJob.created_at.desc())
        .first()
    )

    latest_job = (
        db.query(ScanJob)
        .filter(ScanJob.repository_id == repo_id)
        .order_by(ScanJob.created_at.desc())
        .first()
    )

    if job is None:
        return {
            "repository": {"id": repo.id, "name": repo.name, "status": repo.status},
            "ready": False,
            "latest_job_status": latest_job.status if latest_job else None,
            "latest_job_stage": latest_job.stage if latest_job else None,
            "latest_job_error": latest_job.error_message if latest_job else None,
            "message": "No completed scan yet for this repository.",
        }

    return {
        "repository": {"id": repo.id, "name": repo.name, "status": repo.status},
        "ready": True,
        "scan_job_id": job.id,
        "scanned_at": job.finished_at.isoformat() if job.finished_at else None,
        **job.result,
    }
