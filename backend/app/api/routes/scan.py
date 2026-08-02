from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import ScanJob
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["scan"])


def _job_to_dict(job: ScanJob) -> dict:
    return {
        "id": job.id,
        "repository_id": job.repository_id,
        "status": job.status,
        "stage": job.stage,
        "error_message": job.error_message,
        "result": job.result,
        "created_at": job.created_at.isoformat(),
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.get("/repos/{repo_id}/scan/latest")
def latest_scan(repo_id: str, db: Session = Depends(get_db)):
    job = (
        db.query(ScanJob)
        .filter(ScanJob.repository_id == repo_id)
        .order_by(ScanJob.created_at.desc())
        .first()
    )
    if job is None:
        raise HTTPException(404, "No scan jobs for this repository yet")
    return _job_to_dict(job)


@router.get("/scan-jobs/{job_id}")
def get_scan_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(ScanJob, job_id)
    if job is None:
        raise HTTPException(404, "Scan job not found")
    return _job_to_dict(job)
