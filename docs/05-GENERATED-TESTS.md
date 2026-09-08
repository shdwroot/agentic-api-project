# Generated-test guide

This guide explains what each artifact does, how the pytest runner works, and how to use the SOAP double for controlled REST-adapter tests.

## Artifact map

| Artifact | Reader | Purpose |
|---|---|---|
| `TEST_PLAN.md` | Human | Detailed plan with rationale, data, steps, expected results, and evidence IDs. |
| `scenario_manifest.json` | Tools and tests | Stable machine-readable scenario model. |
| `result.json` | Auditor/operator | Entire normalized context, evidence, trace, review, scenarios, and inline artifacts. |
| `generated_tests/conftest.py` | Pytest | Adds the explicit `--run-live` gate. |
| `generated_tests/soap_test_support.py` | Pytest | Builds envelopes, applies mutations, injects basic/bearer auth, sends requests, and checks generic outcomes. |
| `generated_tests/test_<operation>.py` | Pytest | One definition check per scenario and live cases for directly automatable SOAP scenarios. |
| `generated_tests/mock_soap_server.py` | REST integration harness | Returns controlled SOAP success, fault, malformed, reset, and timeout behavior. |
| `generated_tests/.env.example` | Operator | Lists endpoint and credential variable names without secrets. |

## Offline definition tests

```bash
./scripts/uv-local run pytest generated/generated_tests -m "not live" -vv
```

These tests assert that generated scenarios remain complete and auditable. They do not prove SOAP behavior. They are useful for catching broken generation templates, accidentally empty oracles, and artifact editing mistakes.

## Live direct-SOAP tests

The generated runner builds a document-style envelope:

```xml
<soap:Envelope>
  <soap:Body>
    <tns:OperationRequest>
      <tns:fieldName>value</tns:fieldName>
    </tns:OperationRequest>
  </soap:Body>
</soap:Envelope>
```

It applies mutation metadata such as:

- remove a required or optional field
- set a blank, oversized, or invalid enum value
- change SOAPAction
- change target namespace
- send malformed XML
- switch SOAP version
- remove supported authentication

Run only after setting the endpoint, credentials, and two safety controls:

```bash
export SOAP_ENDPOINT=https://approved-non-production.example/soap
export EXCEPTION_SERVICE_TOKEN='value-from-secret-store'
export ALLOW_LIVE_SOAP_TESTS=true
./scripts/uv-local run pytest generated/generated_tests --run-live -m live -vv
```

If either `ALLOW_LIVE_SOAP_TESTS=true` or `--run-live` is absent, pytest skips the live cases.

## Generic oracle boundaries

The runner can reliably assert:

- success returns 2xx and no SOAP Fault
- invalid input returns HTTP rejection or a SOAP Fault
- authentication removal returns rejection

It cannot generically assert your domain response fields, persistence model, audit system, or REST error body. Add those assertions in your application repository or implement a custom generator.

## SOAP test-double modes

Start the double from the generated directory:

```bash
./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
```

It binds to `127.0.0.1:9089` by default.

### Success

```bash
MOCK_SOAP_MODE=success \
  ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
```

Returns HTTP 200 with `GeneratedSuccess` in a SOAP envelope.

### Named SOAP Fault

```bash
MOCK_SOAP_MODE=fault:InvalidExceptionFault \
  ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
```

Returns HTTP 500 with a SOAP 1.1 Fault whose detail element uses the named fault.

### Non-XML dependency failure

```bash
MOCK_SOAP_MODE=nonxml \
  ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
```

Returns HTTP 500 and `text/plain`. Use this to ensure the adapter does not assume every upstream failure is a parseable SOAP Fault.

### Connection reset

```bash
MOCK_SOAP_MODE=reset \
  ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
```

Closes the connection before sending response headers.

### Timeout

```bash
MOCK_SOAP_MODE=timeout \
MOCK_SOAP_DELAY_SECONDS=5 \
  ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
```

Delays before returning success. Choose a delay greater than the REST application’s SOAP timeout but short enough for a practical test.

### Alternate bind address

```bash
MOCK_SOAP_HOST=127.0.0.1 \
MOCK_SOAP_PORT=9099 \
  ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
```

Update the REST test environment’s SOAP endpoint override accordingly.

## End-to-end test arrangement

```text
test case
   |
   | REST request with unique sentinel values
   v
REST service under test
   |
   | SOAP request redirected by test configuration
   v
generated SOAP double or organization service virtualizer
   |
   +--> captured XML/action/headers/call count
```

For a mapping scenario, the double should capture the request and expose it to the test. The generated minimal double currently discards request bodies; extend it or use an existing virtualizer when automated capture assertions are required.

For every end-to-end result retain:

- REST request and safe response
- redacted SOAP request and response
- HTTP status and SOAP fault code/detail
- elapsed time
- downstream call and retry counts
- correlation ID
- relevant structured logs and audit event
- persistence assertion

## Safe customization

Generated files can be edited for exploration, but reproducible team suites should avoid maintaining long-lived changes inside `generated/`. Prefer:

1. Fix or enrich the input context.
2. Regenerate.
3. Copy stable project-specific assertions into the consuming application’s test package.
4. Add reusable behavior to `ArtifactGenerator` when it applies broadly.

This avoids losing hand edits on regeneration.

## CI example

```yaml
steps:
  - run: ./scripts/uv-local sync --extra dev
  - run: ./scripts/uv-local run agentic-soap generate --context integration-context.yaml --output generated --result-json generated/result.json
  - run: jq -e '[.validation_findings[] | select(.severity == "error")] | length == 0' generated/result.json
  - run: ./scripts/uv-local run pytest generated/generated_tests -m "not live"
```

Put live and harness jobs behind environment-specific approval and hostname controls.

