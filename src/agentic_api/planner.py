from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .evidence import EvidenceIndex
from .models import (
    AutomationLevel,
    DecisionRecord,
    GenerationOptions,
    IntegrationContext,
    Priority,
    ScenarioCategory,
    TestLayer,
    TestScenario,
    TraceStep,
)


@dataclass
class PlanningOutput:
    scenarios: list[TestScenario]
    trace: TraceStep


class ScenarioPlanner:
    """Generates operation- and field-specific tests from normalized evidence."""

    def plan(
        self,
        context: IntegrationContext,
        evidence: EvidenceIndex,
        options: GenerationOptions,
    ) -> PlanningOutput:
        scenarios: list[TestScenario] = []
        enabled = set(options.categories) if options.categories else set(ScenarioCategory)
        if not options.include_security:
            enabled.discard(ScenarioCategory.SECURITY)

        for operation_index, operation in enumerate(context.soap_service.operations):
            op_evidence = evidence.find(
                location_contains=f"soap_service.operations[{operation_index}]"
            ) or [item.id for item in evidence.items[:1]]
            base_data = {field.name: self._example_for(field) for field in operation.fields}
            slug = self._slug(operation.name)
            ordinal = 1

            def add(
                *,
                suffix: str,
                title: str,
                category: ScenarioCategory,
                layer: TestLayer,
                priority: Priority,
                objective: str,
                rationale: str,
                steps: list[str],
                expected: list[str],
                mutation: dict[str, Any],
                automation: AutomationLevel = AutomationLevel.AUTOMATED,
                extra_evidence: list[str] | None = None,
                tags: list[str] | None = None,
                test_data: dict[str, Any] | None = None,
                _operation: Any = operation,
                _op_evidence: list[str] = op_evidence,
                _slug: str = slug,
                _base_data: dict[str, Any] = base_data,
            ) -> None:
                nonlocal ordinal
                if category not in enabled:
                    return
                evidence_ids = list(dict.fromkeys(_op_evidence + (extra_evidence or [])))
                scenarios.append(
                    TestScenario(
                        id=f"SCN-{_slug.upper()}-{suffix}-{ordinal:03d}",
                        title=title,
                        operation=_operation.name,
                        category=category,
                        layer=layer,
                        priority=priority,
                        objective=objective,
                        rationale=rationale,
                        preconditions=self._preconditions(context, layer),
                        test_data=test_data if test_data is not None else _base_data,
                        steps=steps,
                        expected_results=expected,
                        evidence_ids=evidence_ids,
                        tags=[category.value, layer.value, _operation.name, *(tags or [])],
                        automation=automation,
                        mutation=mutation,
                    )
                )
                ordinal += 1

            add(
                suffix="HP",
                title=f"Accept a valid {operation.request_element or operation.name} request",
                category=ScenarioCategory.HAPPY_PATH,
                layer=TestLayer.SOAP_SERVICE,
                priority=Priority.P0,
                objective=f"Prove {operation.name} accepts a contract-valid SOAP request.",
                rationale="A passing baseline is required before negative failures can be interpreted.",
                steps=[
                    "Build a SOAP envelope with the declared namespace and one valid value per field.",
                    f"Send it with SOAPAction {operation.soap_action!r} and the SOAP {context.soap_service.version.value} content type.",
                    "Capture HTTP status, response headers, elapsed time, and the redacted XML body.",
                ],
                expected=[
                    "The transport returns a 2xx response.",
                    "The XML body contains no SOAP Fault element.",
                    f"The response matches {operation.response_element or 'the declared response element'}.",
                ],
                mutation={"kind": "none", "expected_kind": "success"},
                tags=["smoke"],
            )

            for field_index, field in enumerate(operation.fields):
                field_evidence = evidence.find(
                    location_contains=(
                        f"soap_service.operations[{operation_index}].fields[{field_index}]"
                    )
                )
                if field.required:
                    add(
                        suffix="REQ",
                        title=f"Reject {operation.name} when required field {field.name} is omitted",
                        category=ScenarioCategory.FIELD_VALIDATION,
                        layer=TestLayer.SOAP_SERVICE,
                        priority=Priority.P0,
                        objective=f"Verify required XML element {field.name} cannot be omitted.",
                        rationale="The contract marks the field as required; silent acceptance risks incomplete exception records.",
                        steps=[
                            f"Start from the valid {operation.name} request.",
                            f"Remove the {field.xml_path or field.name} element completely (do not send an empty element).",
                            "Send the request and capture both HTTP and SOAP fault details.",
                        ],
                        expected=[
                            "The request is rejected deterministically.",
                            "The response is either a declared SOAP Fault or a documented 4xx validation response.",
                            f"The diagnostic identifies {field.name} without exposing credentials or stack traces.",
                        ],
                        mutation={
                            "kind": "omit_field",
                            "field": field.name,
                            "expected_kind": "soap_or_http_fault",
                        },
                        extra_evidence=field_evidence,
                    )
                if (
                    field.data_type.lower() in {"string", "normalizedstring", "token"}
                    and field.required
                ):
                    add(
                        suffix="BLANK",
                        title=f"Handle a blank value for {field.name} explicitly",
                        category=ScenarioCategory.FIELD_VALIDATION,
                        layer=TestLayer.SOAP_SERVICE,
                        priority=Priority.P1,
                        objective=f"Distinguish an empty {field.name} element from a missing element.",
                        rationale="SOAP serializers frequently emit empty tags, which can bypass presence-only validation.",
                        steps=[
                            f"Set {field.name} to an empty string in an otherwise valid request.",
                            "Send the request using the normal SOAP headers.",
                            "Compare the result with the omitted-field scenario.",
                        ],
                        expected=[
                            "Behavior matches the documented blank-value rule.",
                            "If blank values are invalid, a stable validation fault is returned.",
                            "The service does not convert blank input into misleading default data.",
                        ],
                        mutation={
                            "kind": "set_value",
                            "field": field.name,
                            "value": "",
                            "expected_kind": "soap_or_http_fault",
                        },
                        extra_evidence=field_evidence,
                    )
                if field.max_length is not None:
                    add(
                        suffix="MAX",
                        title=f"Reject {field.name} above its {field.max_length}-character limit",
                        category=ScenarioCategory.BOUNDARY,
                        layer=TestLayer.SOAP_SERVICE,
                        priority=Priority.P1,
                        objective=f"Enforce the maximum length of {field.name} at the exact boundary.",
                        rationale="Boundary-plus-one catches off-by-one validation and truncation defects.",
                        steps=[
                            f"Create one request with {field.max_length} characters and one with {field.max_length + 1} characters.",
                            "Send both requests with otherwise identical data.",
                            "Compare persistence and fault behavior.",
                        ],
                        expected=[
                            f"Exactly {field.max_length} characters are accepted when all other rules pass.",
                            f"{field.max_length + 1} characters are rejected without silent truncation.",
                            "The rejection is reported as a client-data fault.",
                        ],
                        mutation={
                            "kind": "set_value",
                            "field": field.name,
                            "value": "X" * (field.max_length + 1),
                            "expected_kind": "soap_or_http_fault",
                        },
                        extra_evidence=field_evidence,
                    )
                if field.enum:
                    invalid = "__UNDECLARED_ENUM_VALUE__"
                    add(
                        suffix="ENUM",
                        title=f"Reject an undeclared {field.name} enumeration value",
                        category=ScenarioCategory.FIELD_VALIDATION,
                        layer=TestLayer.SOAP_SERVICE,
                        priority=Priority.P1,
                        objective=f"Restrict {field.name} to {', '.join(field.enum)}.",
                        rationale="Unknown enum values often reveal inconsistent schema and domain validation.",
                        steps=[
                            f"Replace the valid {field.name} value with {invalid}.",
                            "Send the request and retain the raw fault code for assertion.",
                        ],
                        expected=[
                            "The value is rejected as a validation error.",
                            f"The error names {field.name} or the violated enumeration constraint.",
                        ],
                        mutation={
                            "kind": "set_value",
                            "field": field.name,
                            "value": invalid,
                            "expected_kind": "soap_or_http_fault",
                        },
                        extra_evidence=field_evidence,
                    )
                if not field.required:
                    add(
                        suffix="OPT",
                        title=f"Accept omission of optional field {field.name}",
                        category=ScenarioCategory.BOUNDARY,
                        layer=TestLayer.SOAP_SERVICE,
                        priority=Priority.P2,
                        objective=f"Verify the optionality contract for {field.name}.",
                        rationale="Optional elements should not become accidentally mandatory in implementation.",
                        steps=[
                            f"Remove optional element {field.name} from a valid request.",
                            "Send the request and inspect the response.",
                        ],
                        expected=[
                            "The request is accepted when no business rule conditionally requires the element.",
                            "No empty or fabricated value is persisted for the omitted field.",
                        ],
                        mutation={
                            "kind": "omit_field",
                            "field": field.name,
                            "expected_kind": "success",
                        },
                        extra_evidence=field_evidence,
                    )

            for fault_index, fault in enumerate(operation.faults):
                fault_evidence = evidence.find(
                    location_contains=(
                        f"soap_service.operations[{operation_index}].faults[{fault_index}]"
                    )
                )
                expected_status = fault.expected_rest_status or self._mapped_status(
                    context, operation.name, fault.name
                )
                add(
                    suffix="FAULT",
                    title=f"Map declared {fault.name} from SOAP to the REST consumer",
                    category=ScenarioCategory.DECLARED_FAULT,
                    layer=TestLayer.END_TO_END if context.rest_consumer else TestLayer.SOAP_SERVICE,
                    priority=Priority.P0,
                    objective=f"Verify the complete handling contract for SOAP fault {fault.name}.",
                    rationale="Declared faults are part of the public contract and must not collapse into generic 500 responses.",
                    steps=[
                        f"Configure the SOAP harness to return {fault.name} with a valid SOAP Fault envelope.",
                        "Invoke the REST operation that triggers the SOAP call."
                        if context.rest_consumer
                        else "Invoke the SOAP operation with the declared trigger data.",
                        "Capture the REST response, SOAP exchange, correlation identifiers, and logs.",
                    ],
                    expected=[
                        f"The SOAP fault code/detail identifies {fault.fault_code or fault.name}.",
                        f"The REST adapter returns HTTP {expected_status}."
                        if expected_status
                        else "The REST adapter returns its explicitly documented status.",
                        "The client-facing body is stable and does not leak the raw stack trace.",
                    ],
                    mutation={
                        "kind": "inject_fault",
                        "fault": fault.name,
                        "trigger": fault.trigger,
                        "expected_kind": "declared_fault",
                        "expected_rest_status": expected_status,
                    },
                    automation=AutomationLevel.HARNESS_REQUIRED,
                    extra_evidence=fault_evidence,
                    test_data={**base_data, **fault.trigger},
                )

            self._add_protocol_scenarios(add, operation, context)
            self._add_resilience_scenarios(add, operation, context)
            self._add_mapping_scenarios(add, operation_index, operation, context, evidence)
            self._add_security_scenarios(add, operation, context)

        rule_evidence = evidence.find(location_contains="business_rules")
        for rule_index, rule in enumerate(context.business_rules):
            operation = context.soap_service.operations[
                rule_index % len(context.soap_service.operations)
            ]
            if ScenarioCategory.CONTRACT not in enabled:
                continue
            scenarios.append(
                TestScenario(
                    id=f"SCN-{self._slug(operation.name).upper()}-RULE-{rule_index + 1:03d}",
                    title=f"Enforce business rule: {rule}",
                    operation=operation.name,
                    category=ScenarioCategory.CONTRACT,
                    layer=TestLayer.END_TO_END,
                    priority=Priority.P1,
                    objective=f"Prove the implementation enforces: {rule}",
                    rationale="Explicit business rules need observable examples and oracles beyond XML validity.",
                    preconditions=self._preconditions(context, TestLayer.END_TO_END),
                    test_data={},
                    steps=[
                        "Construct one example that satisfies the rule and one minimally different example that violates it.",
                        "Execute both through the REST boundary and retain the SOAP exchanges.",
                        "Compare client response, downstream call count, and persisted audit record.",
                    ],
                    expected_results=[
                        "The satisfying example completes according to the success contract.",
                        "The violating example is rejected at the documented layer.",
                        "The audit trail explains the rule outcome without sensitive data.",
                    ],
                    evidence_ids=rule_evidence or [item.id for item in evidence.items[:1]],
                    tags=["business_rule", "end_to_end"],
                    automation=AutomationLevel.HARNESS_REQUIRED,
                    mutation={"kind": "business_rule", "rule": rule, "expected_kind": "harness"},
                )
            )

        scenarios = self._deduplicate(scenarios)
        original_count = len(scenarios)
        scenarios = self._bounded(scenarios, options.max_scenarios)
        warnings = []
        if len(scenarios) < original_count:
            warnings.append(
                f"Scenario limit retained {len(scenarios)} of {original_count}; raise options.max_scenarios for exhaustive boundaries."
            )
        counts = Counter(scenario.category.value for scenario in scenarios)
        trace = TraceStep(
            sequence=2,
            agent="scenario-planner",
            phase="risk_and_scenario_discovery",
            status="completed_with_warnings" if warnings else "completed",
            summary=f"Generated {len(scenarios)} scenarios across {len(counts)} risk categories and {len(context.soap_service.operations)} SOAP operations.",
            evidence_ids=list(
                dict.fromkeys(eid for scenario in scenarios for eid in scenario.evidence_ids)
            ),
            decisions=[
                DecisionRecord(
                    decision="Generate at least one positive baseline and then expand fields, faults, protocol, adapter, resilience, security, and observability risks.",
                    basis=list(
                        dict.fromkeys(
                            eid for scenario in scenarios for eid in scenario.evidence_ids
                        )
                    )[:20],
                    consequence="The plan is contract-specific while retaining a consistent minimum risk floor.",
                ),
                DecisionRecord(
                    decision="Mark scenarios requiring downstream fault control as harness_required.",
                    basis=[],
                    consequence="Generated suites do not pretend black-box clients can force upstream timeouts or declared faults.",
                ),
            ],
            warnings=warnings,
        )
        return PlanningOutput(scenarios=scenarios, trace=trace)

    def _add_protocol_scenarios(
        self, add: Any, operation: Any, context: IntegrationContext
    ) -> None:
        cases = [
            (
                "ACTION",
                "Reject a missing or incorrect SOAPAction",
                "Send the valid body with SOAPAction removed, then with an unrelated action.",
                "The request is rejected or routed exactly as documented; it is never processed as a different operation.",
                {
                    "kind": "header",
                    "header": "SOAPAction",
                    "value": "urn:invalid-action",
                    "expected_kind": "soap_or_http_fault",
                },
            ),
            (
                "NS",
                "Reject an incorrect operation namespace",
                "Change only the operation element namespace while retaining a valid envelope.",
                "The service returns a stable client/protocol fault and performs no business action.",
                {
                    "kind": "namespace",
                    "value": "urn:invalid:test-namespace",
                    "expected_kind": "soap_or_http_fault",
                },
            ),
            (
                "XML",
                "Reject malformed XML without partial processing",
                "Truncate the closing operation and envelope tags before sending the request.",
                "The parser rejects the request, no record is written, and no internal parser trace is exposed.",
                {"kind": "malformed_xml", "expected_kind": "soap_or_http_fault"},
            ),
            (
                "VER",
                f"Reject a SOAP version mismatch against SOAP {context.soap_service.version.value}",
                "Use the alternate SOAP envelope namespace and content type.",
                "The service returns VersionMismatch or the documented transport error.",
                {"kind": "soap_version", "expected_kind": "soap_or_http_fault"},
            ),
        ]
        for suffix, title, step, expected, mutation in cases:
            add(
                suffix=suffix,
                title=f"{title} for {operation.name}",
                category=ScenarioCategory.SOAP_PROTOCOL,
                layer=TestLayer.SOAP_SERVICE,
                priority=Priority.P1,
                objective=f"Verify protocol-level rejection behavior for {operation.name}.",
                rationale="SOAP dispatch depends on the envelope, namespace, action, and content type together.",
                steps=[
                    "Build the valid baseline request.",
                    step,
                    "Capture HTTP and SOAP fault metadata.",
                ],
                expected=[expected, "The operation produces no partial side effect."],
                mutation=mutation,
            )

    def _add_resilience_scenarios(
        self, add: Any, operation: Any, context: IntegrationContext
    ) -> None:
        layer = TestLayer.END_TO_END if context.rest_consumer else TestLayer.SOAP_SERVICE
        cases = [
            (
                "TIMEOUT",
                "SOAP response exceeds the configured timeout",
                f"Delay the SOAP harness beyond {context.soap_service.timeout_ms} ms.",
                "The REST call terminates within its latency budget with a controlled error; the timeout is observable.",
                Priority.P0,
            ),
            (
                "RESET",
                "SOAP connection resets before a response",
                "Accept the connection in the harness and close it before sending headers.",
                "The adapter returns a controlled dependency error and preserves the correlation ID.",
                Priority.P1,
            ),
            (
                "NONXML",
                "SOAP dependency returns a non-XML 500 body",
                "Return HTTP 500 with text/html instead of a SOAP Fault.",
                "The adapter classifies a protocol/dependency failure without exposing the body to the REST client.",
                Priority.P1,
            ),
        ]
        for suffix, title, step, expected, priority in cases:
            add(
                suffix=suffix,
                title=f"Handle {title.lower()} during {operation.name}",
                category=ScenarioCategory.RESILIENCE,
                layer=layer,
                priority=priority,
                objective=f"Verify deterministic recovery when the SOAP dependency cannot complete {operation.name}.",
                rationale="Transport failures are distinct from declared business faults and need separate mapping.",
                steps=[
                    "Configure the controllable SOAP harness.",
                    step,
                    "Invoke the consumer and inspect timing, response, call count, and logs.",
                ],
                expected=[
                    expected,
                    "Any retry behavior matches the operation's idempotency contract.",
                    "No duplicate exception record is created.",
                ],
                mutation={
                    "kind": "transport_fault",
                    "mode": suffix.lower(),
                    "expected_kind": "harness",
                },
                automation=AutomationLevel.HARNESS_REQUIRED,
            )

    def _add_mapping_scenarios(
        self,
        add: Any,
        operation_index: int,
        operation: Any,
        context: IntegrationContext,
        evidence: EvidenceIndex,
    ) -> None:
        if not context.rest_consumer:
            return
        mapping = next((m for m in context.mappings if m.soap_operation == operation.name), None)
        mapping_evidence = evidence.find(location_contains="mappings")
        if mapping and mapping.rest_to_soap:
            for source, target in mapping.rest_to_soap.items():
                add(
                    suffix="MAPIN",
                    title=f"Map REST value {source} to SOAP field {target}",
                    category=ScenarioCategory.REST_MAPPING,
                    layer=TestLayer.END_TO_END,
                    priority=Priority.P0,
                    objective=f"Prove {source} reaches {target} unchanged or via its documented transform.",
                    rationale="A valid SOAP call can still carry the wrong business value due to adapter mapping defects.",
                    steps=[
                        f"Send a distinctive sentinel value in REST field {source}.",
                        "Capture the SOAP request at the harness.",
                        f"Read {target} from the XML using a namespace-aware selector.",
                    ],
                    expected=[
                        f"SOAP field {target} contains the expected mapped sentinel.",
                        "No unrelated field contains the sentinel.",
                        "Sensitive values are redacted in logs.",
                    ],
                    mutation={
                        "kind": "mapping_assertion",
                        "source": source,
                        "target": target,
                        "expected_kind": "harness",
                    },
                    automation=AutomationLevel.HARNESS_REQUIRED,
                    extra_evidence=mapping_evidence,
                )
        else:
            add(
                suffix="MAPMISS",
                title=f"Define and verify REST-to-SOAP mapping for {operation.name}",
                category=ScenarioCategory.REST_MAPPING,
                layer=TestLayer.CONTRACT_ONLY,
                priority=Priority.P0,
                objective="Prevent an undocumented adapter mapping from being accepted as complete.",
                rationale="The REST consumer exists, but no field-level mapping was provided for this operation.",
                steps=[
                    "Obtain the REST request schema and SOAP request element list.",
                    "Create an explicit source-to-target mapping table.",
                    "Add sentinel-value adapter tests for every row.",
                ],
                expected=[
                    "Every required SOAP field has one documented source or default.",
                    "Transforms and default values have named tests.",
                ],
                mutation={"kind": "missing_contract", "expected_kind": "manual"},
                automation=AutomationLevel.MANUAL,
            )

        add(
            suffix="CORR",
            title=f"Propagate correlation identity through REST and SOAP for {operation.name}",
            category=ScenarioCategory.OBSERVABILITY,
            layer=TestLayer.END_TO_END,
            priority=Priority.P1,
            objective="Make a single failure traceable across the protocol boundary.",
            rationale="Exception services are only operationally useful when records can be correlated to the originating request.",
            steps=[
                "Invoke REST with a unique correlation identifier.",
                "Capture the outbound SOAP request and application logs.",
                "Query the exception record or audit sink by that identifier.",
            ],
            expected=[
                "The same identifier appears in the allowed REST, SOAP, and audit locations.",
                "Logs do not contain secrets, authorization headers, or unredacted sensitive fields.",
            ],
            mutation={"kind": "correlation", "expected_kind": "harness"},
            automation=AutomationLevel.HARNESS_REQUIRED,
            extra_evidence=mapping_evidence,
        )

    def _add_security_scenarios(
        self, add: Any, operation: Any, context: IntegrationContext
    ) -> None:
        if context.soap_service.auth.scheme != "none":
            add(
                suffix="AUTH",
                title=f"Reject missing credentials for {operation.name}",
                category=ScenarioCategory.AUTHENTICATION,
                layer=TestLayer.SOAP_SERVICE,
                priority=Priority.P0,
                objective=f"Require {context.soap_service.auth.scheme} authentication before processing XML.",
                rationale="Unauthenticated exception submissions can poison operational data or leak service behavior.",
                steps=[
                    "Build a valid request.",
                    "Remove the configured authentication material.",
                    "Send the request and inspect side effects and diagnostics.",
                ],
                expected=[
                    "The request is rejected with the documented authentication failure.",
                    "No exception record is created.",
                    "The response does not reveal whether a business identifier exists.",
                ],
                mutation={"kind": "remove_auth", "expected_kind": "auth_rejection"},
            )
        add(
            suffix="XXE",
            title=f"Reject external entity expansion in {operation.name}",
            category=ScenarioCategory.SECURITY,
            layer=TestLayer.SOAP_SERVICE,
            priority=Priority.P0,
            objective="Verify XML parsing does not resolve external entities.",
            rationale="SOAP exposes an XML parser boundary; XXE can read files or trigger server-side requests.",
            steps=[
                "Run only against the isolated test harness.",
                "Add a harmless external entity referencing a non-routable test URI.",
                "Send the envelope and inspect response plus harness egress logs.",
            ],
            expected=[
                "The parser rejects DTD/entity use before business processing.",
                "No outbound lookup is attempted.",
                "No referenced content appears in the response or logs.",
            ],
            mutation={"kind": "xxe", "expected_kind": "harness"},
            automation=AutomationLevel.HARNESS_REQUIRED,
            tags=["non_production_only"],
        )

    @staticmethod
    def _mapped_status(context: IntegrationContext, operation: str, fault: str) -> int | None:
        mapping = next(
            (item for item in context.mappings if item.soap_operation == operation), None
        )
        return mapping.fault_to_status.get(fault) if mapping else None

    @staticmethod
    def _example_for(field: Any) -> Any:
        if field.example is not None:
            return field.example
        if field.enum:
            return field.enum[0]
        field_type = field.data_type.lower()
        if field_type in {"int", "integer", "long", "short", "decimal", "double", "float"}:
            return field.minimum if field.minimum is not None else 1
        if field_type in {"boolean", "bool"}:
            return True
        if field_type in {"datetime", "dateTime".lower()}:
            return "2026-01-15T10:30:00Z"
        return f"valid-{field.name}"

    @staticmethod
    def _preconditions(context: IntegrationContext, layer: TestLayer) -> list[str]:
        result = ["Use an isolated test environment with deterministic data cleanup."]
        if layer in {TestLayer.SOAP_SERVICE, TestLayer.END_TO_END}:
            result.append(
                "The SOAP endpoint and credentials are supplied through environment variables."
            )
        if layer in {TestLayer.REST_CONSUMER, TestLayer.END_TO_END}:
            result.append("The REST consumer is configured to use a controllable SOAP test double.")
        return result

    @staticmethod
    def _slug(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "operation"

    @staticmethod
    def _deduplicate(scenarios: list[TestScenario]) -> list[TestScenario]:
        seen: set[tuple[str, str, str]] = set()
        result: list[TestScenario] = []
        for scenario in scenarios:
            key = (scenario.operation, scenario.category.value, scenario.title)
            if key not in seen:
                seen.add(key)
                result.append(scenario)
        return result

    @staticmethod
    def _bounded(scenarios: list[TestScenario], maximum: int) -> list[TestScenario]:
        rank = {Priority.P0: 0, Priority.P1: 1, Priority.P2: 2, Priority.P3: 3}
        indexed = list(enumerate(scenarios))
        indexed.sort(key=lambda item: (rank[item[1].priority], item[0]))
        selected = indexed[:maximum]
        selected.sort(key=lambda item: item[0])
        return [scenario for _, scenario in selected]
