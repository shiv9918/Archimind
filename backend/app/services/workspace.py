from pathlib import Path

from app.config import settings


class RepoWorkspace:
    """Resolves the on-disk layout for a single imported repository."""

    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        self.root = settings.workspace_path / repo_id

    @property
    def source_dir(self) -> Path:
        """Where the cloned/extracted source code lives."""
        path = self.root / "source"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def graph_file(self) -> Path:
        """Where the NetworkX knowledge graph is persisted (JSON)."""
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root / "graph.json"

    @property
    def vector_dir(self) -> Path:
        """Local-mode Qdrant on-disk storage directory."""
        path = self.root / "vectors"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def bm25_file(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root / "bm25.pkl"

    def delete(self) -> None:
        import shutil

        if self.root.exists():
            shutil.rmtree(self.root, ignore_errors=True)
