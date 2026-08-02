from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.agents.orchestrator import run_pipeline
from app.config import settings
from app.db.models import Repository, ScanJob
from app.db.session import get_db
from app.schemas.requests import GithubImportRequest
from app.services.repo_importer import ImportError_, clone_github_repo, extract_zip, repo_name_from_github_url
from app.services.workspace import RepoWorkspace

router = APIRouter(prefix="/api/repos", tags=["repositories"])


def _repo_to_dict(repo: Repository) -> dict:
    return {
        "id": repo.id,
        "name": repo.name,
        "source_type": repo.source_type,
        "source_ref": repo.source_ref,
        "status": repo.status,
        "created_at": repo.created_at.isoformat(),
    }


def _start_scan(db: Session, background_tasks: BackgroundTasks, repo: Repository) -> ScanJob:
    job = ScanJob(repository_id=repo.id, status="pending", stage="queued")
    db.add(job)
    repo.status = "scanning"
    db.commit()
    db.refresh(job)
    background_tasks.add_task(run_pipeline, repo.id, job.id)
    return job


@router.get("")
def list_repositories(db: Session = Depends(get_db)):
    repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
    return [_repo_to_dict(r) for r in repos]


@router.get("/{repo_id}")
def get_repository(repo_id: str, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    return _repo_to_dict(repo)


@router.delete("/{repo_id}")
def delete_repository(repo_id: str, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    RepoWorkspace(repo_id).delete()
    db.delete(repo)
    db.commit()
    return {"status": "deleted"}


@router.post("/import/github", status_code=201)
def import_github(payload: GithubImportRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        name = repo_name_from_github_url(payload.url)
    except ImportError_ as exc:
        raise HTTPException(400, str(exc)) from exc

    repo = Repository(name=name, source_type="github", source_ref=payload.url, local_path="", status="importing")
    db.add(repo)
    db.commit()
    db.refresh(repo)

    workspace = RepoWorkspace(repo.id)
    try:
        clone_github_repo(payload.url, workspace.source_dir)
    except ImportError_ as exc:
        repo.status = "failed"
        db.commit()
        workspace.delete()
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        repo.status = "failed"
        db.commit()
        workspace.delete()
        raise HTTPException(500, "Unexpected error while cloning the repository") from exc

    repo.local_path = str(workspace.source_dir)
    repo.status = "imported"
    db.commit()

    job = _start_scan(db, background_tasks, repo)
    return {"repository": _repo_to_dict(repo), "scan_job_id": job.id}


@router.post("/import/zip", status_code=201)
async def import_zip(background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".zip"):
        raise HTTPException(400, "Please upload a .zip file")

    contents = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(400, f"File exceeds {settings.max_upload_mb}MB limit")

    name = file.filename.rsplit(".", 1)[0]
    repo = Repository(name=name, source_type="zip", source_ref=file.filename, local_path="", status="importing")
    db.add(repo)
    db.commit()
    db.refresh(repo)

    workspace = RepoWorkspace(repo.id)
    try:
        extract_zip(contents, workspace.source_dir)
    except ImportError_ as exc:
        repo.status = "failed"
        db.commit()
        workspace.delete()
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        repo.status = "failed"
        db.commit()
        workspace.delete()
        raise HTTPException(500, "Unexpected error while extracting the ZIP archive") from exc

    repo.local_path = str(workspace.source_dir)
    repo.status = "imported"
    db.commit()

    job = _start_scan(db, background_tasks, repo)
    return {"repository": _repo_to_dict(repo), "scan_job_id": job.id}


@router.post("/{repo_id}/rescan", status_code=201)
def rescan_repository(repo_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    job = _start_scan(db, background_tasks, repo)
    return {"scan_job_id": job.id}
