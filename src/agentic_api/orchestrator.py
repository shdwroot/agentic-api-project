from __future__ import annotations

from threading import RLock
from uuid import uuid4

from .analyzer import ContextAnalyzer
from .artifacts import ArtifactGenerator
from .config import Settings
from .models import (
    DecisionRecord,
    GenerateRequest,
    GenerationResult,
    TraceStep,
)
from .planner import ScenarioPlanner
from .providers import build_augmenter
from .reviewer import CoverageReviewer


class RunNotFoundError(KeyError):
    pass


class InMemoryRunRepository:
    """Small-process repository; replace through DI for durable production storage."""

    def __init__(self) -> None:
        self._runs: dict[str, GenerationResult] = {}
        self._lock = RLock()

    def save(self, result: GenerationResult) -> None:
        with self._lock:
            self._runs[result.run_id] = result

    def get(self, run_id: str) -> GenerationResult:
        with self._lock:
            try:
                return self._runs[run_id]
            except KeyError as exc:
                raise RunNotFoundError(run_id) from exc


class TestGenerationOrchestrator:
    __test__ = False

    def __init__(self, settings: Settings, repository: InMemoryRunRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or InMemoryRunRepository()
        self.analyzer = ContextAnalyzer()
        self.planner = ScenarioPlanner()
        self.reviewer = CoverageReviewer()
        self.artifact_generator = ArtifactGenerator()

    def generate(self, request: GenerateRequest) -> GenerationResult:
        total_bytes = sum(len(document.content.encode("utf-8")) for document in request.documents)
        if total_bytes > self.settings.max_context_bytes:
            raise ValueError(
                f"document context is {total_bytes} bytes; limit is {self.settings.max_context_bytes}"
            )
        if request.options.max_scenarios > self.settings.max_scenarios:
            raise ValueError(
                f"requested {request.options.max_scenarios} scenarios; server limit is {self.settings.max_scenarios}"
            )

        analysis = self.analyzer.analyze(request)
        planning = self.planner.plan(analysis.context, analysis.evidence, request.options)
        trace = [analysis.trace, planning.trace]
        scenarios = list(planning.scenarios)

        if request.options.model_augmentation:
            provider_trace = self._augment(request, analysis, scenarios)
            trace.append(provider_trace[0])
            scenarios.extend(provider_trace[1])

        review = self.reviewer.review(
            analysis.context,
            scenarios,
            {item.id for item in analysis.evidence.items},
        )
        review.trace.sequence = len(trace) + 1
        trace.append(review.trace)

        artifacts = []
        if request.options.include_generated_artifacts:
            artifacts, artifact_trace = self.artifact_generator.generate(
                analysis.context,
                scenarios,
                review.coverage,
                sequence=len(trace) + 1,
            )
            trace.append(artifact_trace)

        has_errors = any(finding.severity == "error" for finding in review.findings)
        has_warnings = any(step.status == "completed_with_warnings" for step in trace)
        status = (
            "failed" if has_errors else ("completed_with_warnings" if has_warnings else "completed")
        )
        result = GenerationResult(
            run_id=str(uuid4()),
            status=status,
            context=analysis.context,
            evidence=analysis.evidence.items,
            decision_trace=trace,
            scenarios=scenarios,
            coverage=review.coverage,
            validation_findings=review.findings,
            artifacts=artifacts,
        )
        self.repository.save(result)
        return result

    def _augment(
        self, request: GenerateRequest, analysis: object, scenarios: list
    ) -> tuple[TraceStep, list]:
        try:
            augmenter = build_augmenter(self.settings, enabled=True)
            proposals = augmenter.propose(analysis.context, analysis.evidence.items, scenarios)
            known_evidence = {item.id for item in analysis.evidence.items}
            valid = [
                scenario
                for scenario in proposals
                if set(scenario.evidence_ids).issubset(known_evidence)
                and scenario.operation
                in {operation.name for operation in analysis.context.soap_service.operations}
            ]
            warning = []
            if len(valid) != len(proposals):
                warning.append("Discarded model proposals with unknown operations or evidence ids.")
            return (
                TraceStep(
                    sequence=3,
                    agent="model-scenario-augmenter",
                    phase="novel_risk_discovery",
                    status="completed_with_warnings" if warning else "completed",
                    summary=f"Accepted {len(valid)} of {len(proposals)} additive model proposals.",
                    evidence_ids=list(known_evidence),
                    decisions=[
                        DecisionRecord(
                            decision="Accept only schema-valid, evidence-linked, known-operation proposals.",
                            basis=list(known_evidence)[:20],
                            consequence="Model output can add coverage but cannot replace deterministic baseline tests.",
                        )
                    ],
                    warnings=warning,
                ),
                valid,
            )
        except Exception as exc:  # provider errors must preserve deterministic output
            return (
                TraceStep(
                    sequence=3,
                    agent="model-scenario-augmenter",
                    phase="novel_risk_discovery",
                    status="completed_with_warnings",
                    summary="Model augmentation was unavailable; deterministic planning completed.",
                    evidence_ids=[],
                    warnings=[f"{type(exc).__name__}: {exc}"],
                ),
                [],
            )

    def get(self, run_id: str) -> GenerationResult:
        return self.repository.get(run_id)
