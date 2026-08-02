"""Embedding + Hybrid Retrieval Agent.

Embeds every file/class/function into a local vector store (Qdrant running
in embedded/local mode -- real Qdrant, no server process needed) using a
locally-run sentence-transformer (no API key required), and also builds a
BM25 index over the same text. Retrieval fuses both via min-max normalized
weighted score fusion, which is what "hybrid search" means in the spec.
"""

import gc
import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from rank_bm25 import BM25Okapi

from app.agents.ast_parser.base import ParsedFile

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_COLLECTION = "chunks"
_VECTOR_SIZE = 384  # all-MiniLM-L6-v2
_MODEL_NAME = "all-MiniLM-L6-v2"
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# Small on purpose: on memory-constrained hosts (e.g. Render free tier, 512MB)
# a large batch's transient tensors during model.encode() can be enough to
# get the whole process OOM-killed. This trades a bit of throughput for
# staying inside a much smaller memory ceiling.
_ENCODE_BATCH_SIZE = 8

_model: "SentenceTransformer | None" = None


def _get_model() -> "SentenceTransformer":
    global _model
    if _model is None:
        # sentence-transformers pulls in torch, which is expensive to import
        # (CPU/memory) -- deferred to first real use instead of app startup,
        # so the server can boot and serve /api/health on memory-constrained hosts.
        import torch
        from sentence_transformers import SentenceTransformer

        # Multi-threaded BLAS/OpenMP kernels each allocate their own buffers;
        # on a memory- (not compute-) constrained host, single-threaded uses
        # meaningfully less peak RAM for a small drop in raw speed.
        torch.set_num_threads(1)

        _model = SentenceTransformer(_MODEL_NAME)
    return _model


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class EmbeddingDocument:
    id: str
    type: str
    text: str
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    id: str
    type: str
    text: str
    metadata: dict
    score: float


def documents_from_parsed_files(parsed_files: list[ParsedFile]) -> list[EmbeddingDocument]:
    docs: list[EmbeddingDocument] = []

    for pf in parsed_files:
        if pf.error:
            continue

        for cls in pf.classes:
            text_parts = [f"class {cls.name} in {pf.path}"]
            if cls.bases:
                text_parts.append(f"inherits from {', '.join(cls.bases)}")
            if cls.docstring:
                text_parts.append(cls.docstring)
            method_names = ", ".join(m.name for m in cls.methods[:20])
            if method_names:
                text_parts.append(f"methods: {method_names}")
            docs.append(
                EmbeddingDocument(
                    id=f"class:{pf.path}:{cls.qualified_name}",
                    type="Class",
                    text="\n".join(text_parts),
                    metadata={"file": pf.path, "name": cls.name, "line": cls.line},
                )
            )

            for method in cls.methods:
                text_parts = [f"method {method.qualified_name}({', '.join(method.parameters)}) in {pf.path}"]
                if method.docstring:
                    text_parts.append(method.docstring)
                docs.append(
                    EmbeddingDocument(
                        id=f"func:{pf.path}:{method.qualified_name}",
                        type="Function",
                        text="\n".join(text_parts),
                        metadata={"file": pf.path, "name": method.name, "line": method.line},
                    )
                )

        for func in pf.functions:
            text_parts = [f"function {func.name}({', '.join(func.parameters)}) in {pf.path}"]
            if func.docstring:
                text_parts.append(func.docstring)
            docs.append(
                EmbeddingDocument(
                    id=f"func:{pf.path}:{func.qualified_name}",
                    type="Function",
                    text="\n".join(text_parts),
                    metadata={"file": pf.path, "name": func.name, "line": func.line},
                )
            )

        docs.append(
            EmbeddingDocument(
                id=f"file:{pf.path}",
                type="File",
                text=f"file {pf.path} ({pf.language}), defines {len(pf.classes)} classes and {len(pf.functions)} functions",
                metadata={"file": pf.path, "language": pf.language},
            )
        )

    return docs


class HybridRetriever:
    def __init__(self, vector_dir: Path, bm25_file: Path):
        self.vector_dir = vector_dir
        self.bm25_file = bm25_file

    def build(self, documents: list[EmbeddingDocument]) -> None:
        if not documents:
            return

        model = _get_model()
        texts = [d.text for d in documents]
        vectors = model.encode(texts, show_progress_bar=False, batch_size=_ENCODE_BATCH_SIZE).tolist()
        gc.collect()  # release the model's transient tensors before the next memory-heavy step

        client = QdrantClient(path=str(self.vector_dir))
        try:
            if client.collection_exists(_COLLECTION):
                client.delete_collection(_COLLECTION)
            client.create_collection(
                collection_name=_COLLECTION,
                vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            )
            points = [
                PointStruct(id=idx, vector=vec, payload={"doc_id": d.id, "type": d.type, "text": d.text, **d.metadata})
                for idx, (d, vec) in enumerate(zip(documents, vectors))
            ]
            client.upsert(collection_name=_COLLECTION, points=points)
        finally:
            client.close()
        del vectors

        tokenized = [_tokenize(d.text) for d in documents]
        bm25 = BM25Okapi(tokenized)
        payload = {
            "bm25": bm25,
            "doc_ids": [d.id for d in documents],
            "types": [d.type for d in documents],
            "texts": texts,
            "metadata": [d.metadata for d in documents],
        }
        with open(self.bm25_file, "wb") as f:
            pickle.dump(payload, f)

    def search(self, query: str, top_k: int = 8) -> list[SearchResult]:
        if not self.bm25_file.exists():
            return []

        with open(self.bm25_file, "rb") as f:
            payload = pickle.load(f)

        bm25: BM25Okapi = payload["bm25"]
        doc_ids: list[str] = payload["doc_ids"]
        types: list[str] = payload["types"]
        texts: list[str] = payload["texts"]
        metas: list[dict] = payload["metadata"]

        bm25_scores = bm25.get_scores(_tokenize(query))
        bm25_norm = _min_max_normalize(bm25_scores)

        vector_scores: dict[int, float] = {}
        model = _get_model()
        query_vector = model.encode([query], show_progress_bar=False)[0].tolist()

        client = QdrantClient(path=str(self.vector_dir))
        try:
            if client.collection_exists(_COLLECTION):
                hits = client.query_points(
                    collection_name=_COLLECTION, query=query_vector, limit=min(len(doc_ids), max(top_k * 4, 20))
                ).points
                for hit in hits:
                    vector_scores[hit.id] = hit.score
        finally:
            client.close()

        vector_norm_map = _min_max_normalize_dict(vector_scores)

        fused: list[tuple[int, float]] = []
        for idx in range(len(doc_ids)):
            v = vector_norm_map.get(idx, 0.0)
            b = bm25_norm[idx] if idx < len(bm25_norm) else 0.0
            fused.append((idx, 0.6 * v + 0.4 * b))

        fused.sort(key=lambda x: x[1], reverse=True)
        top = fused[:top_k]

        return [
            SearchResult(id=doc_ids[idx], type=types[idx], text=texts[idx], metadata=metas[idx], score=round(score, 4))
            for idx, score in top
            if score > 0
        ]


def _min_max_normalize(scores) -> list[float]:
    scores = list(scores)
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [0.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def _min_max_normalize_dict(scores: dict[int, float]) -> dict[int, float]:
    if not scores:
        return {}
    values = list(scores.values())
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return {k: 0.0 for k in scores}
    return {k: (v - lo) / (hi - lo) for k, v in scores.items()}
