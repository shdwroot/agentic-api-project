from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from .analyzer import ContextAnalysisError
from .models import Capabilities, GenerateRequest, GenerationResult, ScenarioCategory
from .orchestrator import RunNotFoundError, TestGenerationOrchestrator

router = APIRouter()


def get_orchestrator() -> TestGenerationOrchestrator:
    from .main import orchestrator

    return orchestrator


OrchestratorDependency = Annotated[TestGenerationOrchestrator, Depends(get_orchestrator)]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/v1/capabilities", response_model=Capabilities)
def capabilities() -> Capabilities:
    return Capabilities(
        service="agentic-soap-test-framework",
        version="0.1.0",
        input_kinds=["structured_context", "wsdl", "openapi", "requirements", "examples"],
        scenario_categories=[item.value for item in ScenarioCategory],
        artifact_types=["pytest", "scenario_manifest", "markdown_test_plan", "soap_test_double"],
        guarantees=[
            "Every scenario cites an input evidence record.",
            "Declared SOAP faults are treated as mandatory coverage.",
            "Live generated tests are disabled by default.",
            "Deterministic planning works without a model API key.",
        ],
    )


@router.post(
    "/v1/generations",
    response_model=GenerationResult,
    status_code=status.HTTP_201_CREATED,
)
def generate(
    request: GenerateRequest,
    service: OrchestratorDependency,
) -> GenerationResult:
    try:
        return service.generate(request)
    except (ContextAnalysisError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/v1/generations/{run_id}", response_model=GenerationResult)
def get_generation(
    run_id: str,
    service: OrchestratorDependency,
) -> GenerationResult:
    try:
        return service.get(run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail="generation run not found") from exc
