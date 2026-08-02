# ArchMind AI

An autonomous codebase architect: import a repository and get a real knowledge
graph, architecture analysis, health scores, and an AI copilot that can
answer questions about the code with actual retrieved context -- not keyword
matching.

This is **Phase 1** of the full vision: a working core slice, end to end,
with nothing faked. See "Roadmap" below for what's deliberately deferred.

## What works today

- **Repository import** -- GitHub URL (public repos, shallow clone) or ZIP upload.
- **Repository Scanner** -- languages, frameworks, package managers, Docker/K8s/CI-CD detection, dependency counts.
- **AST parsing** -- full-fidelity Python (stdlib `ast`); JavaScript/TypeScript via tree-sitter.
- **Knowledge graph** -- Files/Classes/Functions/Modules with imports/defines/inherits/calls edges, explorable via an interactive graph view.
- **Hybrid retrieval** -- local sentence-transformer embeddings + BM25, fused for search.
- **Architecture detection** -- rule-based pattern classification (MVC, Layered, Clean/Hexagonal, DDD, CQRS, Event-Driven, Microservices, Monolith, Serverless) with confidence scores.
- **Health scores** -- documentation, complexity, estimated test coverage, dependency health, basic security scan, architecture score, and a composite technical debt index. All formulas are transparent and documented in code (`backend/app/agents/health_scorer.py`).
- **Developer Copilot chat** -- RAG-based Q&A over the repo using Grok (xAI).

## Architecture

```
backend/   FastAPI + SQLite + NetworkX + local-mode Qdrant + BM25
frontend/  Next.js (App Router) + TypeScript + Tailwind + React Flow
```

No Docker required to run Phase 1. See `docker-compose.yml` for the
documented upgrade path to Neo4j/Postgres/Redis/Qdrant-server once available.

## Running locally

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/pip install -r requirements.txt   # Windows
cp .env.example .env   # then add XAI_API_KEY to enable chat
./venv/Scripts/uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## Testing

```bash
cd backend
./venv/Scripts/pytest -q
```

## Roadmap (explicitly deferred from Phase 1)

Full Security Agent, Performance Agent, Bug Impact Agent, Refactoring Agent,
Git History Agent, Test Intelligence Agent, Code Review Agent, Simulation
Agent, full Documentation Agent (README/diagram generation), cross-session
Repository Memory Agent, Neo4j/Postgres/Redis backends, GitLab/Bitbucket
connectors, and deep parsing for languages beyond Python/JS/TS.
