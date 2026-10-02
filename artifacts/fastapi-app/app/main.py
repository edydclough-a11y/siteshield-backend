from fastapi import FastAPI

app = FastAPI(
    title="FastAPI Starter",
    description="A small, ready-to-extend FastAPI service.",
    version="0.1.0",
)


@app.get("/", tags=["General"])
async def read_root() -> dict[str, str]:
    """Return basic service information."""
    return {
        "name": "FastAPI Starter",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Report whether the service is responding."""
    return {"status": "ok"}