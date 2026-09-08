from __future__ import annotations

import hashlib
import json
import pprint
import re
from collections import defaultdict

from .models import (
    Artifact,
    AutomationLevel,
    CoverageReport,
    DecisionRecord,
    IntegrationContext,
    TestScenario,
    TraceStep,
)


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _artifact(path: str, media_type: str, content: str) -> Artifact:
    return Artifact(path=path, media_type=media_type, content=content, sha256=_sha256(content))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "operation"


class ArtifactGenerator:
    """Produces runnable pytest assets and a detailed, evidence-linked dossier."""

    def generate(
        self,
        context: IntegrationContext,
        scenarios: list[TestScenario],
        coverage: CoverageReport,
        sequence: int,
    ) -> tuple[list[Artifact], TraceStep]:
        artifacts: list[Artifact] = []
        manifest = {
            "schema_version": "1.0",
            "system": context.system_name,
            "scenarios": [scenario.model_dump(mode="json") for scenario in scenarios],
        }
        artifacts.append(
            _artifact(
                "scenario_manifest.json",
                "application/json",
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            )
        )
        artifacts.append(
            _artifact(
                "TEST_PLAN.md",
                "text/markdown",
                self._render_dossier(context, scenarios, coverage),
            )
        )
        artifacts.append(
            _artifact(
                "generated_tests/soap_test_support.py",
                "text/x-python",
                self._render_test_support(context),
            )
        )
        artifacts.append(
            _artifact(
                "generated_tests/conftest.py",
                "text/x-python",
                self._render_conftest(),
            )
        )
        artifacts.append(
            _artifact(
                "generated_tests/pytest.ini",
                "text/plain",
                "[pytest]\nmarkers =\n    live: sends requests to configured services\n    harness: requires a controllable SOAP test double\n",
            )
        )
        artifacts.append(
            _artifact(
                "generated_tests/requirements.txt",
                "text/plain",
                "httpx>=0.28,<1\npytest>=8.4,<9\n",
            )
        )
        artifacts.append(
            _artifact(
                "generated_tests/.env.example",
                "text/plain",
                self._render_generated_env(context),
            )
        )
        artifacts.append(
            _artifact(
                "generated_tests/mock_soap_server.py",
                "text/x-python",
                self._render_mock_server(context),
            )
        )

        by_operation: dict[str, list[TestScenario]] = defaultdict(list)
        for scenario in scenarios:
            by_operation[scenario.operation].append(scenario)
        for operation in context.soap_service.operations:
            operation_scenarios = by_operation[operation.name]
            artifacts.append(
                _artifact(
                    f"generated_tests/test_{_slug(operation.name)}.py",
                    "text/x-python",
                    self._render_operation_tests(operation.name, operation_scenarios),
                )
            )

        trace = TraceStep(
            sequence=sequence,
            agent="artifact-generator",
            phase="test_implementation",
            status="completed",
            summary=f"Rendered {len(artifacts)} artifacts, including {len(by_operation)} operation-specific pytest modules.",
            evidence_ids=list(
                dict.fromkeys(eid for scenario in scenarios for eid in scenario.evidence_ids)
            ),
            decisions=[
                DecisionRecord(
                    decision="Keep live execution disabled unless --run-live and ALLOW_LIVE_SOAP_TESTS=true are both present.",
                    basis=[],
                    consequence="Generated suites are reviewable and syntax-testable without contacting a real service.",
                ),
                DecisionRecord(
                    decision="Separate directly executable SOAP cases from harness-required adapter and failure-injection cases.",
                    basis=[],
                    consequence="Automation claims remain honest about controllability prerequisites.",
                ),
            ],
        )
        return artifacts, trace

    def _render_dossier(
        self,
        context: IntegrationContext,
        scenarios: list[TestScenario],
        coverage: CoverageReport,
    ) -> str:
        lines = [
            f"# Test plan: {context.system_name}",
            "",
            "## Mission",
            "",
            context.purpose,
            "",
            "## System boundary",
            "",
            f"- SOAP service: `{context.soap_service.service_name}`",
            f"- SOAP version: `{context.soap_service.version.value}`",
            f"- SOAP endpoint source: `{context.soap_service.endpoint or 'SOAP_ENDPOINT environment variable'}`",
            f"- Target namespace: `{context.soap_service.target_namespace or 'not supplied'}`",
            f"- REST consumer: `{context.rest_consumer.service_name if context.rest_consumer else 'not supplied'}`",
            "- Live-safety policy: no live requests unless explicitly enabled",
            "",
            "## Coverage summary",
            "",
            f"Total scenarios: **{coverage.total_scenarios}**",
            "",
            "| Category | Count |",
            "|---|---:|",
        ]
        lines.extend(f"| `{name}` | {count} |" for name, count in coverage.by_category.items())
        lines.extend(["", "| Layer | Count |", "|---|---:|"])
        lines.extend(f"| `{name}` | {count} |" for name, count in coverage.by_layer.items())
        if coverage.uncovered_items:
            lines.extend(["", "## Explicit coverage gaps", ""])
            lines.extend(f"- {item}" for item in coverage.uncovered_items)

        lines.extend(
            [
                "",
                "## Execution contract",
                "",
                "1. Review `scenario_manifest.json` and replace placeholder examples with environment-valid identifiers.",
                "2. Copy `generated_tests/.env.example` to a secure environment configuration; never commit credentials.",
                "3. Run definition checks first with `pytest generated_tests -m 'not live'`.",
                "4. Run direct SOAP cases only in an isolated environment with `ALLOW_LIVE_SOAP_TESTS=true pytest generated_tests --run-live`.",
                "5. For `harness_required` cases, configure the REST consumer's SOAP base URL to the generated test double and record that configuration in CI evidence.",
                "6. Retain redacted request/response XML, status, elapsed time, correlation id, and downstream call count for each result.",
                "",
                "## Detailed scenarios",
                "",
            ]
        )
        for scenario in scenarios:
            lines.extend(
                [
                    f"### {scenario.id} — {scenario.title}",
                    "",
                    f"- Operation: `{scenario.operation}`",
                    f"- Risk: `{scenario.category.value}` / `{scenario.priority.value}`",
                    f"- Layer: `{scenario.layer.value}`",
                    f"- Automation: `{scenario.automation.value}`",
                    f"- Evidence: {', '.join(f'`{item}`' for item in scenario.evidence_ids)}",
                    f"- Objective: {scenario.objective}",
                    f"- Why this exists: {scenario.rationale}",
                    "",
                    "Preconditions:",
                    "",
                ]
            )
            lines.extend(f"- {item}" for item in scenario.preconditions)
            lines.extend(["", "Steps:", ""])
            lines.extend(f"{index}. {item}" for index, item in enumerate(scenario.steps, start=1))
            lines.extend(["", "Expected results:", ""])
            lines.extend(f"- {item}" for item in scenario.expected_results)
            lines.extend(
                [
                    "",
                    "Test data and mutation:",
                    "",
                    "```json",
                    json.dumps(
                        {"base": scenario.test_data, "mutation": scenario.mutation},
                        indent=2,
                        sort_keys=True,
                        default=str,
                    ),
                    "```",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def _render_operation_tests(self, operation_name: str, scenarios: list[TestScenario]) -> str:
        payload = [scenario.model_dump(mode="json") for scenario in scenarios]
        literal = pprint.pformat(payload, width=100, sort_dicts=True)
        automated = [
            scenario
            for scenario in scenarios
            if scenario.automation == AutomationLevel.AUTOMATED
            and scenario.layer.value == "soap_service"
        ]
        automated_ids = pprint.pformat([scenario.id for scenario in automated], width=100)
        return f'''"""Generated tests for {operation_name}. Review test data before live execution."""

import pytest
from soap_test_support import execute_scenario

SCENARIOS = {literal}
AUTOMATED_IDS = set({automated_ids})


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda item: item["id"])
def test_scenario_definition_is_complete(scenario):
    """Runs offline and verifies every generated case remains auditable."""
    assert scenario["objective"]
    assert scenario["steps"]
    assert scenario["expected_results"]
    assert scenario["evidence_ids"]
    assert scenario["mutation"].get("expected_kind")


@pytest.mark.live
@pytest.mark.parametrize(
    "scenario",
    [item for item in SCENARIOS if item["id"] in AUTOMATED_IDS],
    ids=lambda item: item["id"],
)
def test_live_soap_scenario(scenario, live_enabled):
    """Sends only directly controllable SOAP-service cases."""
    assert live_enabled, "the live_enabled fixture should skip before this assertion"
    execute_scenario(scenario)
'''

    def _render_conftest(self) -> str:
        return """import os

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="allow tests marked live to send network requests",
    )


@pytest.fixture
def live_enabled(request):
    cli_enabled = request.config.getoption("--run-live")
    env_enabled = os.getenv("ALLOW_LIVE_SOAP_TESTS", "false").lower() == "true"
    if not (cli_enabled and env_enabled):
        pytest.skip(
            "live SOAP tests require both --run-live and ALLOW_LIVE_SOAP_TESTS=true"
        )
    return True
"""

    def _render_test_support(self, context: IntegrationContext) -> str:
        config = {
            "soap_endpoint": context.soap_service.endpoint,
            "target_namespace": context.soap_service.target_namespace or "urn:replace-me",
            "soap_version": context.soap_service.version.value,
            "timeout_seconds": context.soap_service.timeout_ms / 1000,
            "auth": context.soap_service.auth.model_dump(mode="json"),
            "operations": {
                operation.name: {
                    "soap_action": operation.soap_action,
                    "request_element": operation.request_element or operation.name,
                    "response_element": operation.response_element,
                }
                for operation in context.soap_service.operations
            },
        }
        literal = pprint.pformat(config, width=100, sort_dicts=True)
        return f'''"""Runtime used by generated SOAP tests. No request is sent on import."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import httpx

CONFIG = {literal}
SOAP_NAMESPACES = {{
    "1.1": "http://schemas.xmlsoap.org/soap/envelope/",
    "1.2": "http://www.w3.org/2003/05/soap-envelope",
}}


def build_envelope(operation_name, values, namespace=None, soap_version=None):
    operation = CONFIG["operations"][operation_name]
    version = soap_version or CONFIG["soap_version"]
    envelope_ns = SOAP_NAMESPACES[version]
    target_ns = namespace or CONFIG["target_namespace"]
    envelope = ET.Element(f"{{{{{{envelope_ns}}}}}}Envelope")
    body = ET.SubElement(envelope, f"{{{{{{envelope_ns}}}}}}Body")
    request = ET.SubElement(body, f"{{{{{{target_ns}}}}}}{{operation['request_element']}}")
    for name, value in values.items():
        if value is None:
            continue
        child = ET.SubElement(request, f"{{{{{{target_ns}}}}}}{{name}}")
        child.text = str(value).lower() if isinstance(value, bool) else str(value)
    return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)


def _credentials(headers):
    auth = CONFIG["auth"]
    scheme = auth["scheme"]
    if scheme == "bearer":
        token = os.getenv(auth.get("token_env") or "SOAP_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {{token}}"
    if scheme == "basic":
        username = os.getenv(auth.get("username_env") or "SOAP_USERNAME")
        password = os.getenv(auth.get("password_env") or "SOAP_PASSWORD")
        if username is not None and password is not None:
            return httpx.BasicAuth(username, password)
    return None


def prepare_request(scenario):
    mutation = scenario["mutation"]
    values = dict(scenario["test_data"])
    kind = mutation.get("kind", "none")
    if kind == "omit_field":
        values.pop(mutation["field"], None)
    elif kind == "set_value":
        values[mutation["field"]] = mutation.get("value")

    namespace = mutation.get("value") if kind == "namespace" else None
    version = None
    if kind == "soap_version":
        version = "1.2" if CONFIG["soap_version"] == "1.1" else "1.1"
    body = build_envelope(scenario["operation"], values, namespace, version)
    if kind == "malformed_xml":
        body = body[:-12]

    active_version = version or CONFIG["soap_version"]
    if active_version == "1.2":
        headers = {{"Content-Type": "application/soap+xml; charset=utf-8"}}
    else:
        headers = {{"Content-Type": "text/xml; charset=utf-8"}}
    action = CONFIG["operations"][scenario["operation"]].get("soap_action")
    if action:
        headers["SOAPAction"] = f'"{{action}}"'
    if kind == "header":
        headers[mutation["header"]] = mutation.get("value", "")
    auth = _credentials(headers)
    return body, headers, auth


def execute_scenario(scenario):
    endpoint = os.getenv("SOAP_ENDPOINT") or CONFIG.get("soap_endpoint")
    if not endpoint:
        raise AssertionError("SOAP_ENDPOINT is required for live execution")
    body, headers, auth = prepare_request(scenario)
    response = httpx.post(
        endpoint,
        content=body,
        headers=headers,
        auth=auth,
        timeout=float(os.getenv("SOAP_TIMEOUT_SECONDS", CONFIG["timeout_seconds"])),
        follow_redirects=False,
    )
    expected_kind = scenario["mutation"]["expected_kind"]
    has_fault = b"Fault" in response.content
    if expected_kind == "success":
        assert 200 <= response.status_code < 300, response.text[:1000]
        assert not has_fault, response.text[:1000]
    elif expected_kind in {{"soap_or_http_fault", "auth_rejection"}}:
        assert response.status_code >= 400 or has_fault, (
            f"expected rejection, got {{response.status_code}}: {{response.text[:1000]}}"
        )
    else:
        raise AssertionError(f"scenario {{scenario['id']}} requires a dedicated harness")
'''

    def _render_generated_env(self, context: IntegrationContext) -> str:
        lines = [
            "# Safety gate: leave false until the target is confirmed as non-production.",
            "ALLOW_LIVE_SOAP_TESTS=false",
            f"SOAP_ENDPOINT={context.soap_service.endpoint or ''}",
            f"SOAP_TIMEOUT_SECONDS={context.soap_service.timeout_ms / 1000}",
        ]
        auth = context.soap_service.auth
        if auth.username_env:
            lines.append(f"{auth.username_env}=")
        if auth.password_env:
            lines.append(f"{auth.password_env}=")
        if auth.token_env:
            lines.append(f"{auth.token_env}=")
        if context.rest_consumer:
            lines.extend(
                [
                    f"REST_BASE_URL={context.rest_consumer.base_url or ''}",
                    "# Configure the REST service under test to use this URL for fault injection.",
                    "SOAP_STUB_URL=http://127.0.0.1:9089/soap",
                ]
            )
        return "\n".join(lines) + "\n"

    def _render_mock_server(self, context: IntegrationContext) -> str:
        namespace = context.soap_service.target_namespace or "urn:generated:test"
        return f'''"""Controllable local SOAP double for REST-adapter failure injection."""

import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
TARGET_NS = {namespace!r}


def envelope(body):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soap:Envelope xmlns:soap="{{SOAP_NS}}" xmlns:tns="{{TARGET_NS}}">'
        f'<soap:Body>{{body}}</soap:Body></soap:Envelope>'
    ).encode()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        mode = os.getenv("MOCK_SOAP_MODE", "success")
        if mode == "timeout":
            time.sleep(float(os.getenv("MOCK_SOAP_DELAY_SECONDS", "15")))
        if mode == "reset":
            self.connection.close()
            return
        if mode == "nonxml":
            return self._send(500, b"upstream proxy failure", "text/plain")
        if mode.startswith("fault:"):
            fault_name = mode.split(":", 1)[1]
            body = (
                '<soap:Fault><faultcode>soap:Server</faultcode>'
                f'<faultstring>{{fault_name}}</faultstring>'
                f'<detail><tns:{{fault_name}}/></detail></soap:Fault>'
            )
            return self._send(500, envelope(body), "text/xml; charset=utf-8")
        return self._send(200, envelope("<tns:GeneratedSuccess/>"), "text/xml; charset=utf-8")

    def _send(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    host = os.getenv("MOCK_SOAP_HOST", "127.0.0.1")
    port = int(os.getenv("MOCK_SOAP_PORT", "9089"))
    print(f"SOAP test double listening on http://{{host}}:{{port}}/soap")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
'''
