from fastapi import FastAPI

from app.routers.ingest import router as ingest_router

app = FastAPI(
    title="SiteShield Omni-Ingest Engine",
    description="Classifies construction-site notes and media into daily logs, snags, and variations.",
    version="0.2.0",
)

app.include_router(ingest_router)


@app.get("/", tags=["General"])
async def read_root() -> dict[str, str]:
    """Return basic service information."""
    return {
        "name": "SiteShield Omni-Ingest Engine",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Report whether the service is responding."""
    return {"status": "ok"}