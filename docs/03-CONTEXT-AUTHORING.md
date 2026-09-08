# Context authoring guide

Scenario quality is bounded by context quality. This guide explains how to describe a REST-to-SOAP exception-service integration so generated tests are specific, traceable, and executable.

## Authoring rule

Record facts, not guesses. If a mapping, fault status, timeout, or field rule is unknown, leave it absent and let the framework expose the gap. A visible `manual` scenario is safer than a precise-looking assertion based on invented behavior.

Start from [the complete example](../examples/exception_service_context.yaml).

## Top-level request

```yaml
context:
  system_name: order-api to exception-service
  purpose: Records terminal order failures through SOAP.
  soap_service: {}
  rest_consumer: {}
  mappings: []
  business_rules: []
  non_functional_requirements: []
  assumptions: []
documents: []
options: {}
```

You can provide `context`, documents, or both. When both exist, structured context is authoritative and documents remain supporting evidence.

## System identity and purpose

### `system_name`

Name the integration boundary, not the organization or entire platform.

Good:

```yaml
system_name: claims-rest-api to application-exception-service
```

Weak:

```yaml
system_name: backend
```

### `purpose`

State the trigger, downstream action, and expected outcome.

```yaml
purpose: >-
  When claims processing reaches a terminal failure, the REST API records a
  redacted exception through SOAP and preserves a stable REST error response.
```

## SOAP service

```yaml
soap_service:
  service_name: ApplicationExceptionService
  endpoint: https://soap-test.example.internal/exception
  wsdl_url: https://soap-test.example.internal/exception?wsdl
  target_namespace: urn:example:application-exception:v1
  version: "1.1"
  timeout_ms: 3000
  auth:
    scheme: bearer
    token_env: EXCEPTION_SERVICE_TOKEN
  operations: []
```

### Endpoint handling

The framework does not fetch `endpoint` or `wsdl_url` during generation. They are contract data and generated-test defaults. Supply local WSDL content through `documents` for analysis.

Do not embed credentials in URLs.

### SOAP version

Use string values:

- `"1.1"` for the `http://schemas.xmlsoap.org/soap/envelope/` envelope and `text/xml` requests.
- `"1.2"` for the `http://www.w3.org/2003/05/soap-envelope` envelope and `application/soap+xml` requests.

The planner creates a version-mismatch scenario because content type and envelope namespace must agree.

### Authentication

Supported context schemes:

- `none`
- `basic`
- `bearer`
- `wsse_username_token`
- `mtls`
- `custom`

Use environment-variable names:

```yaml
auth:
  scheme: basic
  username_env: SOAP_USERNAME
  password_env: SOAP_PASSWORD
```

Never put the username, password, token, certificate, or private key in context. The generic generated runner directly implements bearer and basic authentication. WS-Security, mTLS, and custom schemes require a project-specific transport extension.

## SOAP operations

Create one entry for every operation in scope:

```yaml
operations:
  - name: RecordApplicationException
    soap_action: urn:exception:v1/RecordApplicationException
    request_element: RecordApplicationExceptionRequest
    response_element: RecordApplicationExceptionResponse
    idempotent: true
    description: Records one immutable exception and returns its record id.
    fields: []
    faults: []
```

### Idempotency

Set `idempotent: true` only when repeated equivalent requests are safe by contract. Also state the idempotency key and equivalence rule in `business_rules`.

This affects the expected behavior of timeout and retry scenarios. It does not authorize the generated runner to retry automatically.

## Request fields

Document constraints that have observable behavior:

```yaml
fields:
  - name: severity
    xml_path: /RecordApplicationExceptionRequest/severity
    data_type: string
    required: true
    nullable: false
    enum: [INFO, WARN, ERROR, FATAL]
    example: ERROR
    description: Operational severity after REST-domain normalization.
    sensitive: false
```

Available constraints:

| Field | Use |
|---|---|
| `name` | XML element name used by the generic generator. |
| `xml_path` | Human-readable mapping and assertion location. |
| `data_type` | XSD-like type such as string, integer, boolean, or dateTime. |
| `required` | Whether the element must be present. |
| `nullable` | Whether `xsi:nil` is permitted. |
| `min_length` / `max_length` | Exact string boundaries. |
| `minimum` / `maximum` | Numeric boundaries. |
| `pattern` | Regex or contract pattern. |
| `enum` | Complete set of allowed lexical values. |
| `example` | Safe, environment-valid baseline value. |
| `description` | Business meaning and transformations. |
| `sensitive` | Whether logs and artifacts require redaction. |

The current deterministic planner expands required strings, blank strings, maximum lengths, enums, and optional fields. Other constraints remain evidence for custom rules or model augmentation and are candidates for future deterministic expansion.

### Required, empty, and nil are different

For SOAP/XML, distinguish:

```xml
<!-- Missing -->

<!-- Present but empty -->
<message/>

<!-- Explicit nil -->
<message xsi:nil="true"/>
```

Set `required` and `nullable` independently and add a business rule when empty strings have special meaning.

### Safe examples

An example should:

- pass all field and business rules
- be valid in a disposable test environment
- contain no production personal or secret data
- be recognizable in captured XML
- avoid collision with other parallel tests

Correlation IDs should be unique per execution when the real service enforces uniqueness. Adjust generated fixtures or inject them at runtime.

## Declared faults

Every known fault needs its own entry:

```yaml
faults:
  - name: InvalidExceptionFault
    fault_code: Client.InvalidException
    description: The submitted exception violates a field or business rule.
    expected_rest_status: 422
    trigger:
      severity: NOT_A_SEVERITY
```

### `trigger`

Use `trigger` only when input deterministically produces the fault in a test environment. Some faults, such as store unavailability, should be generated by the SOAP test double instead.

### REST status

You can place expected REST status on the fault, in `mapping.fault_to_status`, or both. If both are present, keep them consistent.

The coverage reviewer treats every declared fault as mandatory. Omitting its scenario is an integrity error.

## REST consumer

```yaml
rest_consumer:
  service_name: Order API
  base_url: http://127.0.0.1:8081
  endpoint: /v1/orders
  method: POST
  success_status: 201
  description: Reports terminal processing exceptions before returning an error.
```

This describes the entry boundary under test. It does not configure the REST application. Your integration-test deployment must separately support a SOAP endpoint override.

## Operation mappings

Mappings are where adapter defects become testable:

```yaml
mappings:
  - soap_operation: RecordApplicationException
    trigger: A reportable order-processing exception occurs.
    rest_to_soap:
      request.headers.X-Correlation-ID: correlationId
      error.code: exceptionCode
      error.safeMessage: message
    soap_to_rest:
      exceptionRecordId: error.reference
    fault_to_status:
      InvalidExceptionFault: 422
      ServiceUnavailableFault: 503
```

Use clear dotted paths for the REST/domain side and exact field names or XML paths for SOAP. Describe transformations in field descriptions or business rules.

For every required SOAP field, answer one question: “Where does this value come from?” It must have a source, a documented default, or an explicitly tested derivation.

## Business rules

Write rules as observable invariants:

Good:

```yaml
business_rules:
  - A repeated correlation id with an identical body returns the original record id.
  - A repeated correlation id with a different body returns DuplicateCorrelationFault.
  - The REST error code is preserved when exception recording fails.
  - Authorization headers and payment data are removed before message is sent.
```

Weak:

```yaml
business_rules:
  - Handle duplicates correctly.
  - Be secure.
```

The current planner creates a harness-required scenario for each explicit rule. Detailed custom data may still be required before the case becomes directly executable.

## Non-functional requirements

Use measurable thresholds and a named environment:

```yaml
non_functional_requirements:
  - SOAP p95 response time is below 750 ms during a 10-minute, 20-RPS test.
  - The REST request terminates within 3500 ms when the SOAP dependency times out.
  - Every exchange emits one audit event containing the correlation id.
```

Avoid “fast,” “reliable,” or “well logged” without an observable target.

## Assumptions

Assumptions are accepted conditions that the framework cannot prove from the input:

```yaml
assumptions:
  - The REST test deployment can override its SOAP endpoint.
  - A test-only audit query can confirm record creation.
```

Review assumptions before every environment promotion. When an assumption becomes false, the corresponding tests may stop proving what their titles claim.

## Attach documents

Example WSDL evidence:

```yaml
documents:
  - name: application-exception-service.wsdl
    kind: wsdl
    content: |
      <?xml version="1.0"?>
      <wsdl:definitions>...</wsdl:definitions>
```

Document kinds are `wsdl`, `xsd`, `openapi`, `requirements`, `example`, and `other`.

The CLI accepts one YAML/JSON request file. If source documents are separate, embed their content during your build process or call the API with assembled JSON.

## Authoring checklist

Before generation, confirm:

- [ ] The boundary and trigger are explicit.
- [ ] SOAP version and target namespace are exact.
- [ ] Every in-scope operation is present.
- [ ] Required and nullable semantics are not conflated.
- [ ] Examples are safe and valid.
- [ ] Every declared fault has a name and expected behavior.
- [ ] Every required SOAP field has a source or default.
- [ ] Fault-to-REST status mappings are explicit.
- [ ] Timeout and idempotency rules are measurable.
- [ ] Sensitive fields and redaction rules are named.
- [ ] Test endpoint override and audit visibility assumptions are written down.
- [ ] No credentials or production personal data are stored in the file.

