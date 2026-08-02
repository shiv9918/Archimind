import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import chat, dashboard, graph, repos, scan
from app.config import settings
from app.db.session import init_db

logger = logging.getLogger("archmind")
logging.basicConfig(level=logging.INFO)

init_db()  # idempotent -- also called at import time so DB is ready even without lifespan (e.g. plain TestClient())
@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="ArchMind AI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    # Also allow Vercel preview-deployment URLs (they're per-branch/PR, so a
    # fixed origin list can't cover them), in addition to the exact origins above.
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "llm_configured": settings.llm_configured}


app.include_router(repos.router)
app.include_router(scan.router)
app.include_router(dashboard.router)
app.include_router(graph.router)
app.include_router(chat.router)
