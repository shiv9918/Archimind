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
- **Hybrid retrieval** -- local ONNX embeddings (via fastembed) + BM25, fused for search.
- **Architecture detection** -- rule-based pattern classification (MVC, Layered, Clean/Hexagonal, DDD, CQRS, Event-Driven, Microservices, Monolith, Serverless) with confidence scores.
- **Health scores** -- documentation, complexity, estimated test coverage, dependency health, basic security scan, architecture score, and a composite technical debt index. All formulas are transparent and documented in code (`backend/app/agents/health_scorer.py`).
- **Developer Copilot chat** -- RAG-based Q&A over the repo using Groq.

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
cp .env.example .env   # then add GROQ_API_KEY to enable chat
./venv/Scripts/uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## Deploying

**Backend -> Render** (Blueprint at `render.yaml`, repo root):
1. https://dashboard.render.com/blueprints -> New Blueprint Instance -> pick this repo. Render reads `render.yaml` automatically (`rootDir: backend`, free plan, health check on `/api/health`).
2. After it deploys, open the service -> Environment -> set `GROQ_API_KEY` (your key) and `FRONTEND_ORIGIN` (your Vercel URL, once you have it -- comma-separate if there's more than one, e.g. prod + a custom domain).
3. Note the service URL, e.g. `https://archmind-backend.onrender.com` -- the frontend needs it.

Storage note: the free plan's disk is **ephemeral** -- imported repos, the SQLite DB, and the vector index reset on every redeploy/restart. Fine for demoing; add a Render persistent disk or migrate to Postgres/managed Qdrant if you need durability. The frontend papers over this for GitHub imports (not ZIP uploads) by remembering the source URL client-side and silently re-importing if the backend reports the repo as gone, but a rescan still costs whatever time the original import took.

**Frontend -> Vercel**:
1. https://vercel.com/new -> import this repo.
2. Set **Root Directory** to `frontend` (required -- this is a monorepo).
3. Add env var `NEXT_PUBLIC_API_BASE_URL` = your Render backend URL from above.
4. Deploy. Then go back to Render and set `FRONTEND_ORIGIN` to the resulting Vercel URL so CORS allows it (Vercel preview-deployment URLs on `*.vercel.app` are allowed automatically).

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
