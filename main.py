import logging
from contextlib import asynccontextmanager
from logger import setup_logging
setup_logging()   # must be first

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from middleware import RequestLoggingMiddleware
from api.routes import user, search, knowledge, sources
from config import get_settings

log = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    log.info("=" * 60)
    log.info("Academic Knowledge Base starting up")
    log.info("  default_llm  : %s", settings.default_llm)
    log.info("  openai key   : %s", "set" if settings.openai_api_key else "NOT SET")
    log.info("  anthropic key: %s", "set" if settings.anthropic_api_key else "NOT SET")
    log.info("  gemini key   : %s", "set" if settings.gemini_api_key else "NOT SET")
    log.info("  docs         : http://localhost:%d/docs", settings.port)
    log.info("=" * 60)
    yield
    log.info("Academic Knowledge Base shutting down")


app = FastAPI(
    title="Academic Knowledge Base",
    description="Build a personalised academic knowledge base with LLM enrichment.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(user.router)
app.include_router(search.router)
app.include_router(knowledge.router)
app.include_router(sources.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse("static/index.html")


@app.get("/health")
async def health():
    log.debug("health check")
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    log.info("Launching uvicorn on port %d", settings.port)
    uvicorn.run("main:app", host="0.0.0.0", port=settings.port, reload=True, log_level="warning")
