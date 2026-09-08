# User guide

This guide covers the complete operator workflow: prepare context, generate a plan, review agent output, run safe tests, add controlled failure injection, and promote the suite into CI.

## 1. Decide what boundary you are testing

Write down the answer before creating context:

- Is the SOAP service itself under test?
- Is the REST consumer and its SOAP adapter under test?
- Is the complete REST-to-SOAP flow under test?
- Can the REST application override the SOAP endpoint in a test environment?
- Can you inspect persisted exception records or audit events?

These decisions determine what can be automated. Direct SOAP validation needs only a SOAP test endpoint. REST mapping, fault mapping, timeout, and retry tests need a controllable SOAP dependency and usually an audit assertion.

## 2. Gather authoritative input

Collect what exists; do not wait for perfect documentation.

| Input | What the framework gets from it | What it usually does not contain |
|---|---|---|
| WSDL/XSD | Operations, messages, XML structure, namespaces, actions, declared faults | REST mapping, operational policy, safe error behavior |
| OpenAPI | REST routes, methods, schemas, response statuses | SOAP implementation details |
| Requirements | Business rules, redaction, timing, retry, audit behavior | Fully machine-readable constraints |
| Example exchanges | Real element ordering, headers, fault shapes | Complete boundary coverage |
| Structured context | The authoritative merged view | Only what you explicitly provide |

The best input is structured context plus the source documents that support it.

## 3. Create a request file

Copy the complete example:

```bash
cp examples/exception_service_context.yaml my-service-context.yaml
```

Edit these sections first:

1. `system_name` and `purpose`
2. `soap_service.service_name`, endpoint, namespace, version, and authentication
3. Every SOAP operation, request field, constraint, and declared fault
4. `rest_consumer`
5. `mappings`
6. `business_rules` and `non_functional_requirements`

Do not place real credentials in the file. Put environment-variable names such as `EXCEPTION_SERVICE_TOKEN` in the context and inject values only at runtime.

Use [the context authoring guide](03-CONTEXT-AUTHORING.md) for every field and quality check.

## 4. Generate locally

```bash
./scripts/uv-local run agentic-soap generate \
  --context my-service-context.yaml \
  --output generated/my-service \
  --result-json generated/my-service/result.json
```

Exit status meanings:

- `0`: the run completed or completed with warnings.
- `2`: independent review found an integrity error such as an uncovered declared fault.
- Other non-zero status: input validation, dependency, or runtime failure.

Warnings are not failures, but they are not decoration. For example, WSDL-only input warns that REST mapping coverage is limited.

## 5. Review before running tests

Review in this order:

### A. Validation findings

```bash
jq '.validation_findings' generated/my-service/result.json
```

Resolve errors before trusting the suite. Decide explicitly whether warnings are acceptable for the intended boundary.

### B. Coverage gaps

```bash
jq '.coverage | {by_category, by_layer, by_priority, uncovered_items}' \
  generated/my-service/result.json
```

An empty `uncovered_items` list means the planner met its minimum guarantees for the supplied context. It does not mean the input context itself was complete.

### C. P0 cases

```bash
jq '.scenarios[] | select(.priority == "P0") | {id, title, automation}' \
  generated/my-service/result.json
```

Confirm that every business-critical fault and mapping is represented.

### D. Evidence links

For a selected scenario:

```bash
jq '.scenarios[] | select(.id == "SCENARIO-ID-HERE")' generated/my-service/result.json
```

Then look up every ID in `evidence_ids`:

```bash
jq '.evidence[] | select(.id == "EVIDENCE-ID-HERE")' generated/my-service/result.json
```

If the evidence is wrong, fix the input rather than editing the generated scenario by hand.

## 6. Run offline definition tests

```bash
./scripts/uv-local run pytest generated/my-service/generated_tests -m "not live"
```

These checks validate that every scenario retains its objective, steps, expected results, mutation contract, and evidence references. They do not call SOAP or REST services.

Run this level in every pull request because it is deterministic and safe.

## 7. Configure direct SOAP tests

Copy the generated environment template into your secret-management workflow. Required values depend on the context:

```bash
export SOAP_ENDPOINT=https://soap-test.example.internal/exception
export SOAP_TIMEOUT_SECONDS=3
export EXCEPTION_SERVICE_TOKEN='test-token-from-secret-store'
```

Review the generated base data in `scenario_manifest.json`. Replace placeholder examples with valid non-production identifiers where necessary.

Enable direct calls only after confirming the target:

```bash
export ALLOW_LIVE_SOAP_TESTS=true
./scripts/uv-local run pytest generated/my-service/generated_tests --run-live -m live -vv
```

The runner asserts success versus SOAP/HTTP rejection. Domain-specific response assertions should be added in a maintained project test layer or a custom artifact generator.

## 8. Configure end-to-end fault injection

Start the generated SOAP double in one terminal:

```bash
MOCK_SOAP_MODE=fault:InvalidExceptionFault \
  ./scripts/uv-local run python generated/my-service/generated_tests/mock_soap_server.py
```

Configure the REST application’s SOAP endpoint override to:

```text
http://127.0.0.1:9089/soap
```

Invoke the REST operation and assert:

- REST status and safe response body
- number of outbound SOAP calls
- captured SOAP action, namespace, and field values
- correlation identifier propagation
- redaction of secrets and sensitive data
- persistence or absence of an exception record
- elapsed time and retry count

Repeat using `success`, `nonxml`, `reset`, and `timeout` modes. Full commands and limitations are in the [generated-test guide](05-GENERATED-TESTS.md).

## 9. Put the suite in CI

A sensible pipeline has separate jobs:

```text
context validation + offline definitions
                |
                v
direct SOAP contract tests against disposable environment
                |
                v
REST adapter tests with SOAP double
                |
                v
approved end-to-end tests
```

Recommended controls:

- Always run offline tests.
- Store endpoints and credentials in CI secrets.
- Require environment approval for live jobs.
- Block production hostnames through CI policy.
- Archive `result.json`, `TEST_PLAN.md`, redacted exchanges, and JUnit results.
- Fail if `validation_findings` contains an error or if accepted coverage gaps change unexpectedly.
- Regenerate when WSDL, OpenAPI, mappings, or business rules change.

## 10. Know the current storage model

The API stores generation runs in memory. `GET /v1/generations/{run_id}` works only while the same server process remains alive. Use `--result-json` or persist the API response if you need durable evidence.

For multi-user deployment, add authentication, tenant isolation, durable encrypted storage, rate limits, and artifact expiration before exposing this service beyond a trusted development environment.

