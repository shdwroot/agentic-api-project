from pathlib import Path

import yaml

from agentic_api.analyzer import ContextAnalyzer
from agentic_api.models import GenerateRequest


def test_wsdl_only_request_discovers_service_operation_and_fields():
    path = Path(__file__).resolve().parents[1] / "examples" / "wsdl_only_request.yaml"
    request = GenerateRequest.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))

    result = ContextAnalyzer().analyze(request)

    assert result.context.soap_service.service_name == "ApplicationExceptionService"
    assert result.context.soap_service.target_namespace == "urn:example:application-exception:v1"
    operation = result.context.soap_service.operations[0]
    assert operation.name == "RecordApplicationException"
    assert operation.soap_action == "urn:example:RecordApplicationException"
    assert [field.name for field in operation.fields] == [
        "applicationName",
        "correlationId",
        "message",
    ]
    assert operation.fields[-1].required is False
    assert operation.faults[0].name == "InvalidExceptionFault"
    assert result.evidence.items
    assert all(item.sha256 for item in result.evidence.items)
