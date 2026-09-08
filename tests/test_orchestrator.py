import ast
import hashlib

from conftest import load_example_request

from agentic_api.config import Settings
from agentic_api.models import ScenarioCategory
from agentic_api.orchestrator import TestGenerationOrchestrator


def test_generation_is_specific_traceable_and_complete():
    request = load_example_request()
    service = TestGenerationOrchestrator(Settings())

    result = service.generate(request)

    assert result.status in {"completed", "completed_with_warnings"}
    assert len(result.scenarios) >= 35
    assert len(result.decision_trace) == 4
    assert [step.agent for step in result.decision_trace] == [
        "context-analyzer",
        "scenario-planner",
        "coverage-reviewer",
        "artifact-generator",
    ]
    evidence_ids = {item.id for item in result.evidence}
    assert all(set(scenario.evidence_ids) <= evidence_ids for scenario in result.scenarios)
    assert all(scenario.objective and scenario.rationale for scenario in result.scenarios)
    assert any(
        scenario.category == ScenarioCategory.FIELD_VALIDATION and "correlationId" in scenario.title
        for scenario in result.scenarios
    )
    for fault in request.context.soap_service.operations[0].faults:
        assert any(fault.name in scenario.title for scenario in result.scenarios)
    assert result.coverage.uncovered_items == []
    assert not [finding for finding in result.validation_findings if finding.severity == "error"]


def test_generated_python_is_valid_and_artifact_hashes_match():
    result = TestGenerationOrchestrator(Settings()).generate(load_example_request())

    for artifact in result.artifacts:
        assert artifact.sha256 == hashlib.sha256(artifact.content.encode()).hexdigest()
        if artifact.path.endswith(".py"):
            ast.parse(artifact.content, filename=artifact.path)


def test_security_category_can_be_disabled():
    request = load_example_request()
    request.options.include_security = False

    result = TestGenerationOrchestrator(Settings()).generate(request)

    assert all(scenario.category != ScenarioCategory.SECURITY for scenario in result.scenarios)


def test_saved_run_can_be_retrieved():
    service = TestGenerationOrchestrator(Settings())
    result = service.generate(load_example_request())

    assert service.get(result.run_id) == result
