# Agentic SOAP Test Framework

This project turns integration context into a reviewed, evidence-linked test suite for a REST application that consumes a SOAP exception service. It identifies scenarios at the operation, field, fault, protocol, mapping, resilience, security, and observability layers; explains the public basis for each decision; and generates runnable `pytest` assets plus a detailed test dossier.

The framework is deliberately useful without an AI key. Its deterministic planner guarantees baseline coverage. An optional model pass can propose additional edge cases, but it cannot replace the baseline, cite unknown evidence, or silently redefine the service contract.

## Learn the framework

- Start with the [20-minute crash course](docs/01-CRASH-COURSE.md).
- Follow the [complete user guide](docs/02-USER-GUIDE.md) for an end-to-end workflow.
- Use the [documentation and training hub](docs/README.md) for context authoring, API reference, generated-test guidance, troubleshooting, labs, instructor material, and the cheat sheet.

## What is implemented

- `POST /v1/generations` accepts structured context, WSDL/OpenAPI/requirements documents, or both.
- The context analyzer normalizes the SOAP and REST boundaries and assigns stable evidence IDs.
- The scenario planner expands every SOAP operation into specific, named tests.
- The coverage reviewer independently rejects duplicate IDs, unknown evidence, missing oracles, and uncovered declared SOAP faults.
- The artifact generator emits a manifest, a detailed Markdown dossier, safe-by-default pytest modules, environment instructions, and a controllable SOAP test double.
- `GET /v1/generations/{run_id}` retrieves a completed run from the in-process repository.
- The CLI writes all generated artifacts to a directory with path-traversal protection.

## Architectural boundary

```text
                    input contract and narrative
                  (JSON/YAML/WSDL/OpenAPI/text)
                               |
                               v
                    +--------------------+
                    | Context Analyzer   |
                    | normalize + cite   |
                    +---------+----------+
                              |
                     IntegrationContext
                     + EvidenceRef[]
                              |
                              v
                    +--------------------+
                    | Scenario Planner   |---- optional ----> Model augmenter
                    | deterministic risk |                  additive only
                    +---------+----------+
                              |
                         TestScenario[]
                              |
                              v
                    +--------------------+
                    | Coverage Reviewer  |
                    | independent gates  |
                    +---------+----------+
                              |
                              v
                    +--------------------+
                    | Artifact Generator |
                    +---------+----------+
                              |
          +-------------------+--------------------+
          |                   |                    |
    scenario JSON      detailed test plan    generated pytest
                                             + SOAP test double
```

The generated tests preserve another important split:

```text
REST test client --> REST application --> SOAP adapter --> SOAP service/test double
       |                   |                   |                  |
 REST contract       error mapping       XML mapping       SOAP contract
 and status          and timing          and headers       faults/protocol
```

A test can therefore state exactly which layer failed. A REST status mismatch does not automatically imply a SOAP failure, and a valid SOAP envelope does not prove that the REST adapter mapped the correct business values.

## Quick start

Prerequisites: Python 3.11+ and [`uv`](https://docs.astral.sh/uv/).

Use the repository's local `uv` wrapper for commands. It keeps the project environment and cache outside a synchronized `Documents` checkout, where cloud storage can offload files inside `.venv` and make ordinary `uv run` imports appear frozen. `make` targets select the appropriate wrapper automatically.

### macOS

```bash
./scripts/uv-local sync --extra dev
./scripts/uv-local run pytest
./scripts/uv-local run uvicorn agentic_api.main:app --reload --host 127.0.0.1 --port 8088
```

### Windows PowerShell or Command Prompt

```powershell
.\scripts\uv-local.cmd sync --extra dev
.\scripts\uv-local.cmd run pytest
.\scripts\uv-local.cmd run uvicorn agentic_api.main:app --reload --host 127.0.0.1 --port 8088
```

The Windows wrapper keeps its environment and cache in the standard Windows temporary directory and does not depend on PowerShell execution-policy settings. In the remaining command examples, substitute `.\scripts\uv-local.cmd` for `./scripts/uv-local`.

The first command after source or dependency changes may rebuild the local package. Subsequent generation runs should begin printing `[1/10] Writing ...` progress almost immediately.

OpenAPI documentation is then available at `http://127.0.0.1:8088/docs` and health at `http://127.0.0.1:8088/health`.

Generate the included exception-service example:

```bash
./scripts/uv-local run agentic-soap generate \
  --context examples/exception_service_context.yaml \
  --output generated \
  --result-json generated/result.json
```

The output contains:

```text
generated/
├── TEST_PLAN.md
├── scenario_manifest.json
├── result.json
└── generated_tests/
    ├── .env.example
    ├── conftest.py
    ├── mock_soap_server.py
    ├── pytest.ini
    ├── requirements.txt
    ├── soap_test_support.py
    └── test_recordapplicationexception.py
```

Run the generated definition checks without making network calls:

```bash
./scripts/uv-local run pytest generated/generated_tests -m "not live"
```

Live SOAP tests require both an environment safety gate and a CLI flag:

```bash
export ALLOW_LIVE_SOAP_TESTS=true
export SOAP_ENDPOINT=https://soap-test.example.internal/exception
export EXCEPTION_SERVICE_TOKEN=replace-with-a-test-secret
./scripts/uv-local run pytest generated/generated_tests --run-live -m live
```

Use only a non-production target with disposable test data. The double gate prevents an ordinary `pytest` command from unexpectedly transmitting exception payloads.

## API example

The YAML example is a `GenerateRequest`. Convert it to JSON before sending it to the API, or use this minimal request:

```json
{
  "context": {
    "system_name": "orders to exception service",
    "purpose": "Record order failures through SOAP",
    "soap_service": {
      "service_name": "ApplicationExceptionService",
      "endpoint": "http://127.0.0.1:9089/soap",
      "target_namespace": "urn:example:exception:v1",
      "version": "1.1",
      "operations": [
        {
          "name": "RecordException",
          "soap_action": "urn:RecordException",
          "request_element": "RecordExceptionRequest",
          "response_element": "RecordExceptionResponse",
          "fields": [
            {"name": "correlationId", "required": true, "max_length": 64},
            {"name": "message", "required": true, "max_length": 2000}
          ],
          "faults": [
            {"name": "InvalidExceptionFault", "expected_rest_status": 422}
          ]
        }
      ]
    }
  }
}
```

```bash
curl -sS http://127.0.0.1:8088/v1/generations \
  -H 'Content-Type: application/json' \
  --data @request.json
```

The response returns four audit surfaces:

1. `evidence` — immutable excerpts with source, location, and SHA-256 digest.
2. `decision_trace` — public observations, decisions, consequences, warnings, and coverage counts from each agent stage.
3. `scenarios` — detailed preconditions, data, steps, expected results, automation level, and evidence links.
4. `validation_findings` and `coverage` — independent omissions or integrity failures.

This is the supported meaning of “show its work.” The framework exposes concise decision records and input evidence; it does not request, store, or reveal private model chain-of-thought.

## Input strategy

### Preferred: structured context plus source documents

Structured context is authoritative because WSDL usually lacks REST mappings, safe error policy, authentication deployment details, data-redaction rules, idempotency behavior, and operational budgets. Attach WSDL/OpenAPI/requirements documents as additional evidence when calling the API.

Important fields include:

- Every SOAP operation and its action, request/response element, request fields, and declared faults.
- Field constraints: required/nullable, type, length, numeric bounds, regex, enum, sensitivity, and a safe test example.
- The REST consumer endpoint and success contract.
- Source-to-target and target-to-source mappings.
- Every SOAP-fault-to-REST-status mapping.
- Business rules, timeout policy, retry/idempotency behavior, and observability requirements.

### WSDL-only mode

Submit a document with `kind: wsdl` when structured context does not exist. The analyzer extracts service name, address, target namespace, SOAP version, operations, actions, fields it can resolve, and declared faults. It intentionally does not invent REST mappings or business semantics. Gaps appear as warnings or explicit contract-only scenarios.

See `examples/wsdl_only_request.yaml`.

## Scenario taxonomy

| Category | What it proves | Typical layer |
|---|---|---|
| `happy_path` | A valid envelope establishes a trustworthy baseline | SOAP service |
| `field_validation` | Required, blank, enum, and type rules reject bad values | SOAP service |
| `boundary` | Exact limits and optionality behave without truncation/defaulting | SOAP service |
| `soap_protocol` | Envelope version, namespace, action, and XML parsing are correct | SOAP service |
| `declared_fault` | Every WSDL/business fault has a stable downstream mapping | End-to-end |
| `rest_mapping` | Distinctive REST values arrive in the correct XML elements | End-to-end |
| `authentication` | Missing credentials fail before business processing | SOAP service |
| `resilience` | Timeout, reset, malformed upstream body, and retry behavior are controlled | End-to-end |
| `security` | Parser and data-handling controls resist XML and leakage risks | Isolated harness |
| `observability` | Correlation, redaction, audit, timing, and call count are provable | End-to-end |
| `contract` | Explicit business rules and contract gaps have named tests | Contract/end-to-end |

The planner generates scenarios from actual operations and field names rather than emitting a generic checklist. A required `correlationId`, for example, receives a named omitted-field case; an enum `severity` receives an undeclared-value case; each declared fault receives its own mapping case.

## Automation levels

- `automated`: The generated direct SOAP runner can control the input and assert the result.
- `harness_required`: The case needs controlled behavior such as an upstream timeout, reset, or named fault. Use `mock_soap_server.py` or your existing service virtualization layer.
- `manual`: Required contract information is missing, so a reliable executable assertion would be dishonest. The dossier gives the exact closure steps.

Start the generated test double with a behavior profile:

```bash
MOCK_SOAP_MODE=success python generated/generated_tests/mock_soap_server.py
MOCK_SOAP_MODE=fault:InvalidExceptionFault python generated/generated_tests/mock_soap_server.py
MOCK_SOAP_MODE=nonxml python generated/generated_tests/mock_soap_server.py
MOCK_SOAP_MODE=timeout MOCK_SOAP_DELAY_SECONDS=5 python generated/generated_tests/mock_soap_server.py
```

Configure the REST service under test to point at `http://127.0.0.1:9089/soap`, then exercise its public REST route. The framework does not assume the name of your application's SOAP-endpoint override setting; record that adapter configuration as test evidence.

## Optional model augmentation

Deterministic mode is the default:

```bash
AGENTIC_API_MODEL_PROVIDER=disabled
```

For an additive model pass:

```bash
./scripts/uv-local sync --extra dev --extra openai
export AGENTIC_API_MODEL_PROVIDER=openai
export OPENAI_API_KEY=replace-me
export OPENAI_MODEL=replace-with-an-available-model
```

Set `options.model_augmentation: true` per request. Proposed scenarios must validate against the same schema, name a known operation, and cite known evidence IDs. Provider failure leaves deterministic output intact and becomes a visible trace warning. Context sent to an external provider may contain sensitive service details, so keep augmentation disabled unless data handling has been approved.

## Reliability and production hardening

The current repository is an intentionally complete local MVP, not a horizontally scalable control plane. Before multi-user production use, revisit:

- Replace `InMemoryRunRepository` with encrypted durable storage and tenant isolation.
- Add authentication/authorization, request quotas, audit retention, and artifact-expiry policy.
- Move generation to a job queue if documents or model calls exceed ordinary HTTP timeouts.
- Add WSDL/XSD import resolution with an explicit allowlist, size limits, and SSRF-safe fetcher. The MVP never fetches supplied URLs.
- Run generated code in a network-restricted sandbox before accepting custom generator extensions.
- Add secret scanning and policy redaction before any context is sent to a model provider.
- Version the `IntegrationContext`, `TestScenario`, and artifact schemas before external clients depend on them.
- Export OpenTelemetry spans and metrics for stage latency, warnings, coverage gaps, and provider failure rate.

### Scale estimate

Planning is currently in-process and approximately linear in document lines, operation fields, declared faults, mappings, and generated scenarios. The defaults cap document content at 1 MB and a run at 250 scenarios. At higher concurrency, API workers should enqueue immutable generation jobs and write results to object storage plus a relational metadata store.

### Explicit trade-offs

- Deterministic rules are less imaginative than a model but reproducible, inspectable, cheap, and available offline.
- Inline artifacts make the API simple but enlarge responses; object storage is better for large suites.
- Conservative WSDL extraction avoids hidden network access but cannot resolve remote imports.
- Generated generic XML avoids binding the framework to one SOAP client library; teams can add a generator for Zeep, Java/JUnit, Karate, SoapUI, or Postman without changing scenario discovery.
- A local SOAP double provides transport control, but the REST application still needs a supported endpoint override for true adapter tests.

## Extending the framework

- Add a planner rule in `src/agentic_api/planner.py` when it applies deterministically to a known contract feature.
- Add a generator beside `ArtifactGenerator` for another runtime while keeping `TestScenario` as the intermediate representation.
- Implement a durable repository with `save` and `get`, then inject it into `TestGenerationOrchestrator`.
- Add an external provider behind `ScenarioAugmenter`; never permit it to mutate authoritative context or remove deterministic cases.
- Expand the review gate before expanding generation. Coverage should fail visibly before a new contract feature can be silently ignored.

## Development checks

```bash
./scripts/uv-local run ruff check .
./scripts/uv-local run pytest --cov=agentic_api --cov-report=term-missing
./scripts/uv-local run agentic-soap generate \
  --context examples/exception_service_context.yaml \
  --output generated \
  --result-json generated/result.json
./scripts/uv-local run pytest generated/generated_tests -m "not live"
```
