from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DocumentKind(StrEnum):
    WSDL = "wsdl"
    XSD = "xsd"
    OPENAPI = "openapi"
    REQUIREMENTS = "requirements"
    EXAMPLE = "example"
    OTHER = "other"


class SoapVersion(StrEnum):
    SOAP_11 = "1.1"
    SOAP_12 = "1.2"


class ScenarioCategory(StrEnum):
    HAPPY_PATH = "happy_path"
    FIELD_VALIDATION = "field_validation"
    BOUNDARY = "boundary"
    SOAP_PROTOCOL = "soap_protocol"
    DECLARED_FAULT = "declared_fault"
    REST_MAPPING = "rest_mapping"
    AUTHENTICATION = "authentication"
    RESILIENCE = "resilience"
    SECURITY = "security"
    OBSERVABILITY = "observability"
    CONTRACT = "contract"


class TestLayer(StrEnum):
    SOAP_SERVICE = "soap_service"
    REST_CONSUMER = "rest_consumer"
    END_TO_END = "end_to_end"
    CONTRACT_ONLY = "contract_only"


class Priority(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class AutomationLevel(StrEnum):
    AUTOMATED = "automated"
    HARNESS_REQUIRED = "harness_required"
    MANUAL = "manual"


class InputDocument(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    kind: DocumentKind
    content: str = Field(min_length=1)


class FieldSpec(StrictModel):
    name: str
    xml_path: str | None = None
    data_type: str = "string"
    required: bool = True
    nullable: bool = False
    min_length: int | None = Field(default=None, ge=0)
    max_length: int | None = Field(default=None, ge=1)
    minimum: float | None = None
    maximum: float | None = None
    pattern: str | None = None
    enum: list[str] = Field(default_factory=list)
    example: Any | None = None
    description: str | None = None
    sensitive: bool = False

    @model_validator(mode="after")
    def validate_bounds(self) -> FieldSpec:
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError("min_length cannot exceed max_length")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")
        return self


class SoapFaultSpec(StrictModel):
    name: str
    fault_code: str | None = None
    description: str | None = None
    expected_rest_status: int | None = Field(default=None, ge=100, le=599)
    trigger: dict[str, Any] = Field(default_factory=dict)


class SoapOperationSpec(StrictModel):
    name: str
    soap_action: str | None = None
    request_element: str | None = None
    response_element: str | None = None
    fields: list[FieldSpec] = Field(default_factory=list)
    faults: list[SoapFaultSpec] = Field(default_factory=list)
    idempotent: bool = False
    description: str | None = None


class SoapAuthSpec(StrictModel):
    scheme: Literal["none", "basic", "bearer", "wsse_username_token", "mtls", "custom"] = "none"
    username_env: str | None = None
    password_env: str | None = None
    token_env: str | None = None
    description: str | None = None


class SoapServiceSpec(StrictModel):
    service_name: str
    endpoint: str | None = None
    wsdl_url: str | None = None
    target_namespace: str | None = None
    version: SoapVersion = SoapVersion.SOAP_11
    timeout_ms: int = Field(default=10_000, ge=1, le=300_000)
    auth: SoapAuthSpec = Field(default_factory=SoapAuthSpec)
    operations: list[SoapOperationSpec] = Field(min_length=1)


class RestConsumerSpec(StrictModel):
    service_name: str
    base_url: str | None = None
    endpoint: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    success_status: int = Field(default=200, ge=100, le=599)
    description: str | None = None


class OperationMapping(StrictModel):
    soap_operation: str
    trigger: str | None = None
    rest_to_soap: dict[str, str] = Field(default_factory=dict)
    soap_to_rest: dict[str, str] = Field(default_factory=dict)
    fault_to_status: dict[str, int] = Field(default_factory=dict)


class IntegrationContext(StrictModel):
    system_name: str
    purpose: str
    soap_service: SoapServiceSpec
    rest_consumer: RestConsumerSpec | None = None
    mappings: list[OperationMapping] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    non_functional_requirements: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def mappings_reference_known_operations(self) -> IntegrationContext:
        known = {operation.name for operation in self.soap_service.operations}
        unknown = {mapping.soap_operation for mapping in self.mappings} - known
        if unknown:
            raise ValueError(f"mappings reference unknown SOAP operations: {sorted(unknown)}")
        return self


class GenerationOptions(StrictModel):
    categories: list[ScenarioCategory] = Field(default_factory=list)
    include_security: bool = True
    include_generated_artifacts: bool = True
    max_scenarios: int = Field(default=150, ge=10, le=2_000)
    live_test_policy: Literal["disabled_by_default"] = "disabled_by_default"
    model_augmentation: bool = False


class GenerateRequest(StrictModel):
    context: IntegrationContext | None = None
    documents: list[InputDocument] = Field(default_factory=list)
    options: GenerationOptions = Field(default_factory=GenerationOptions)

    @model_validator(mode="after")
    def require_context_source(self) -> GenerateRequest:
        if self.context is None and not self.documents:
            raise ValueError("provide structured context, at least one document, or both")
        return self


class EvidenceRef(StrictModel):
    id: str
    source: str
    location: str
    excerpt: str
    sha256: str


class DecisionRecord(StrictModel):
    decision: str
    basis: list[str] = Field(default_factory=list)
    consequence: str


class TraceStep(StrictModel):
    sequence: int
    agent: str
    phase: str
    status: Literal["completed", "completed_with_warnings", "failed"]
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TestScenario(StrictModel):
    id: str
    title: str
    operation: str
    category: ScenarioCategory
    layer: TestLayer
    priority: Priority
    objective: str
    rationale: str
    preconditions: list[str]
    test_data: dict[str, Any] = Field(default_factory=dict)
    steps: list[str]
    expected_results: list[str]
    evidence_ids: list[str]
    tags: list[str] = Field(default_factory=list)
    automation: AutomationLevel
    mutation: dict[str, Any] = Field(default_factory=dict)


class CoverageReport(StrictModel):
    total_scenarios: int
    by_category: dict[str, int]
    by_layer: dict[str, int]
    by_priority: dict[str, int]
    operation_coverage: dict[str, list[str]]
    uncovered_items: list[str]
    review_warnings: list[str]


class ValidationFinding(StrictModel):
    severity: Literal["error", "warning", "info"]
    code: str
    message: str
    scenario_id: str | None = None


class Artifact(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    path: str
    media_type: str
    content: str
    sha256: str


class GenerationResult(StrictModel):
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: Literal["completed", "completed_with_warnings", "failed"]
    context: IntegrationContext
    evidence: list[EvidenceRef]
    decision_trace: list[TraceStep]
    scenarios: list[TestScenario]
    coverage: CoverageReport
    validation_findings: list[ValidationFinding]
    artifacts: list[Artifact] = Field(default_factory=list)


class Capabilities(StrictModel):
    service: str
    version: str
    input_kinds: list[str]
    scenario_categories: list[str]
    artifact_types: list[str]
    guarantees: list[str]
