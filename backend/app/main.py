"""FastAPI entry point."""

from fastapi import FastAPI, Response, status
from sqlalchemy import text

from app import auth
from app.database import engine

app = FastAPI(title="Enterprise AI Operations Pilot API")
# The frontend proxies /api/* here (see frontend/next.config.ts).
app.include_router(auth.router, prefix="/api")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz(response: Response) -> dict[str, str]:
    """Readiness: the database is reachable."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}
    return {"status": "ok"}
