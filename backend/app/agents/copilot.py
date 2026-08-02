"""Developer Copilot -- retrieval-augmented Q&A over an imported repository."""

from app.agents.embedding_agent import HybridRetriever
from app.agents.llm_client import chat_completion
from app.services.workspace import RepoWorkspace

SYSTEM_PROMPT = (
    "You are ArchMind AI, a senior software architect assistant embedded in a developer platform. "
    "Answer questions about the given repository using ONLY the provided code context below. "
    "Cite specific file paths and function/class names you rely on. "
    "If the context doesn't contain enough information to answer confidently, say so plainly instead of guessing."
)


def answer_question(repo_id: str, question: str, history: list[dict]) -> tuple[str, list[dict]]:
    workspace = RepoWorkspace(repo_id)
    retriever = HybridRetriever(workspace.vector_dir, workspace.bm25_file)
    results = retriever.search(question, top_k=8)

    context_blocks = []
    sources = []
    for r in results:
        context_blocks.append(f"[{r.type}] {r.metadata.get('file', '')}\n{r.text}")
        sources.append({"id": r.id, "type": r.type, "file": r.metadata.get("file"), "score": r.score})

    context_text = "\n\n---\n\n".join(context_blocks) if context_blocks else "(no relevant context found -- the repository may not be scanned yet)"

    history_text = ""
    if history:
        history_lines = [f"{m['role']}: {m['content']}" for m in history[-6:]]
        history_text = "Conversation so far:\n" + "\n".join(history_lines) + "\n\n"

    user_prompt = f"{history_text}Repository context:\n{context_text}\n\nQuestion: {question}"

    answer = chat_completion(SYSTEM_PROMPT, user_prompt)
    return answer, sources
