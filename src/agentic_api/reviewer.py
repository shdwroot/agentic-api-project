from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from .models import (
    CoverageReport,
    DecisionRecord,
    IntegrationContext,
    ScenarioCategory,
    TestScenario,
    TraceStep,
    ValidationFinding,
)


@dataclass
class ReviewOutput:
    coverage: CoverageReport
    findings: list[ValidationFinding]
    trace: TraceStep


class CoverageReviewer:
    """Checks plan integrity independently from scenario creation."""

    REQUIRED_PER_OPERATION = {
        ScenarioCategory.HAPPY_PATH,
        ScenarioCategory.FIELD_VALIDATION,
        ScenarioCategory.SOAP_PROTOCOL,
        ScenarioCategory.RESILIENCE,
        ScenarioCategory.SECURITY,
    }

    def review(
        self, context: IntegrationContext, scenarios: list[TestScenario], evidence_ids: set[str]
    ) -> ReviewOutput:
        findings: list[ValidationFinding] = []
        identifiers = Counter(scenario.id for scenario in scenarios)
        for identifier, count in identifiers.items():
            if count > 1:
                findings.append(
                    ValidationFinding(
                        severity="error",
                        code="DUPLICATE_SCENARIO_ID",
                        message=f"Scenario id {identifier} appears {count} times.",
                        scenario_id=identifier,
                    )
                )
        for scenario in scenarios:
            missing = set(scenario.evidence_ids) - evidence_ids
            if missing:
                findings.append(
                    ValidationFinding(
                        severity="error",
                        code="UNKNOWN_EVIDENCE",
                        message=f"References unknown evidence ids: {sorted(missing)}",
                        scenario_id=scenario.id,
                    )
                )
            if not scenario.expected_results:
                findings.append(
                    ValidationFinding(
                        severity="error",
                        code="MISSING_ORACLE",
                        message="Scenario has no expected results.",
                        scenario_id=scenario.id,
                    )
                )

        operation_categories: dict[str, set[ScenarioCategory]] = defaultdict(set)
        for scenario in scenarios:
            operation_categories[scenario.operation].add(scenario.category)
        uncovered: list[str] = []
        for operation in context.soap_service.operations:
            required = set(self.REQUIRED_PER_OPERATION)
            if not operation.fields:
                required.discard(ScenarioCategory.FIELD_VALIDATION)
            missing = required - operation_categories[operation.name]
            for category in sorted(missing, key=lambda item: item.value):
                message = f"{operation.name} has no {category.value} scenario."
                uncovered.append(message)
                findings.append(
                    ValidationFinding(
                        severity="warning",
                        code="CATEGORY_GAP",
                        message=message,
                    )
                )
            for fault in operation.faults:
                if not any(
                    scenario.operation == operation.name
                    and scenario.category == ScenarioCategory.DECLARED_FAULT
                    and fault.name in scenario.title
                    for scenario in scenarios
                ):
                    message = f"{operation.name} fault {fault.name} is not covered."
                    uncovered.append(message)
                    findings.append(
                        ValidationFinding(
                            severity="error",
                            code="FAULT_GAP",
                            message=message,
                        )
                    )

        if context.rest_consumer and not any(
            scenario.category == ScenarioCategory.REST_MAPPING for scenario in scenarios
        ):
            message = "REST consumer is present but no adapter mapping scenario was generated."
            uncovered.append(message)
            findings.append(
                ValidationFinding(severity="warning", code="REST_MAPPING_GAP", message=message)
            )

        by_category = Counter(scenario.category.value for scenario in scenarios)
        by_layer = Counter(scenario.layer.value for scenario in scenarios)
        by_priority = Counter(scenario.priority.value for scenario in scenarios)
        operation_coverage = {
            operation.name: sorted(
                category.value for category in operation_categories[operation.name]
            )
            for operation in context.soap_service.operations
        }
        warnings = [finding.message for finding in findings if finding.severity == "warning"]
        coverage = CoverageReport(
            total_scenarios=len(scenarios),
            by_category=dict(sorted(by_category.items())),
            by_layer=dict(sorted(by_layer.items())),
            by_priority=dict(sorted(by_priority.items())),
            operation_coverage=operation_coverage,
            uncovered_items=uncovered,
            review_warnings=warnings,
        )
        errors = [finding for finding in findings if finding.severity == "error"]
        trace = TraceStep(
            sequence=3,
            agent="coverage-reviewer",
            phase="independent_plan_review",
            status="failed" if errors else ("completed_with_warnings" if warnings else "completed"),
            summary=f"Reviewed {len(scenarios)} scenarios: {len(errors)} errors and {len(warnings)} warnings.",
            evidence_ids=sorted(evidence_ids),
            decisions=[
                DecisionRecord(
                    decision="Fail plan integrity on duplicate ids, missing oracles, unknown evidence, or uncovered declared faults.",
                    basis=sorted(evidence_ids)[:20],
                    consequence="A completed run cannot silently omit an explicit SOAP fault contract.",
                )
            ],
            warnings=warnings,
        )
        return ReviewOutput(coverage=coverage, findings=findings, trace=trace)
