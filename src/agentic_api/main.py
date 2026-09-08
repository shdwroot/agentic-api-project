from __future__ import annotations

from fastapi import FastAPI

from .api import router
from .config import get_settings
from .orchestrator import TestGenerationOrchestrator

settings = get_settings()
orchestrator = TestGenerationOrchestrator(settings)

app = FastAPI(
    title="Agentic SOAP Test Framework",
    version="0.1.0",
    description=(
        "Turns REST-to-SOAP integration context into evidence-linked scenarios, "
        "coverage findings, and executable pytest assets."
    ),
)
app.include_router(router)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "agentic_api.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
