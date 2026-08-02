from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.copilot import answer_question
from app.agents.llm_client import LLMNotConfiguredError
from app.db.models import ChatMessage, Repository
from app.db.session import get_db
from app.schemas.requests import ChatRequest

router = APIRouter(prefix="/api/repos", tags=["chat"])


def _msg_dict(m: ChatMessage) -> dict:
    return {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}


@router.get("/{repo_id}/chat")
def get_chat_history(repo_id: str, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.repository_id == repo_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [_msg_dict(m) for m in messages]


@router.post("/{repo_id}/chat")
def post_chat_message(repo_id: str, payload: ChatRequest, db: Session = Depends(get_db)):
    repo = db.get(Repository, repo_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    if repo.status != "ready":
        raise HTTPException(409, f"Repository is not ready yet (status: {repo.status}). Wait for the scan to finish.")

    history = (
        db.query(ChatMessage)
        .filter(ChatMessage.repository_id == repo_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    history_dicts = [{"role": m.role, "content": m.content} for m in history]

    user_msg = ChatMessage(repository_id=repo_id, role="user", content=payload.message)
    db.add(user_msg)
    db.commit()

    try:
        answer, sources = answer_question(repo_id, payload.message, history_dicts)
    except LLMNotConfiguredError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc

    assistant_msg = ChatMessage(repository_id=repo_id, role="assistant", content=answer)
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    return {"message": _msg_dict(assistant_msg), "sources": sources}
