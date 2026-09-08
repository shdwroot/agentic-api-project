# API reference

Base URL for local development:

```text
http://127.0.0.1:8088
```

Interactive OpenAPI documentation:

[http://127.0.0.1:8088/docs](http://127.0.0.1:8088/docs)

The API currently has no application-level authentication and is intended for a trusted local environment.

## `GET /health`

Confirms that the process can serve requests.

Response `200`:

```json
{"status":"ok"}
```

This proves API liveness. It does not prove connectivity to a SOAP service because generation does not fetch or call the supplied SOAP endpoint.

## `GET /v1/capabilities`

Returns supported input types, scenario categories, artifacts, and behavioral guarantees.

Example:

```bash
curl -sS http://127.0.0.1:8088/v1/capabilities | jq
```

Response `200` includes:

- `input_kinds`
- `scenario_categories`
- `artifact_types`
- `guarantees`

## `POST /v1/generations`

Analyzes context, creates scenarios, reviews coverage, and optionally returns generated artifacts.

Example:

```bash
curl -sS http://127.0.0.1:8088/v1/generations \
  -H 'Content-Type: application/json' \
  --data @examples/training/minimal-generation.json \
  -o /tmp/agentic-soap-training-result.json
```

Success response: `201 Created`.

Request top-level fields:

| Field | Required | Meaning |
|---|---:|---|
| `context` | Conditional | Structured authoritative integration context. |
| `documents` | Conditional | WSDL, XSD, OpenAPI, requirements, example, or other text documents. |
| `options` | No | Category, artifact, security, size, and augmentation settings. |

At least `context` or one document is required. Document-only mode requires a WSDL because the framework refuses to invent a SOAP contract from narrative alone.

Important options:

| Field | Default | Meaning |
|---|---:|---|
| `categories` | All | Optional allowlist of scenario categories. |
| `include_security` | `true` | Include isolated-harness XML security scenarios. |
| `include_generated_artifacts` | `true` | Return generated file content inline. |
| `max_scenarios` | `150` | Per-request cap; server default maximum is 250. |
| `live_test_policy` | `disabled_by_default` | Generated live tests retain their explicit safety gate. |
| `model_augmentation` | `false` | Request additive provider suggestions when configured. |

Response structure:

| Field | Meaning |
|---|---|
| `run_id` | Unique identifier for in-process retrieval. |
| `status` | `completed`, `completed_with_warnings`, or `failed`. |
| `context` | Normalized contract actually used by the planner. |
| `evidence` | Source excerpts, locations, and digests. |
| `decision_trace` | Ordered public decision records from each stage. |
| `scenarios` | Detailed test scenarios. |
| `coverage` | Counts and explicit uncovered items. |
| `validation_findings` | Review errors, warnings, and information. |
| `artifacts` | Generated paths, media types, content, and content digests. |

Input or analysis failure: `422 Unprocessable Entity`.

Common causes:

- Neither context nor documents were supplied.
- WSDL XML is malformed.
- Document-only input has no WSDL.
- A mapping names a SOAP operation that does not exist.
- Field bounds are inconsistent.
- Request bytes or scenario limit exceed server policy.

## `GET /v1/generations/{run_id}`

Returns a generation result from the current server process.

```bash
curl -sS http://127.0.0.1:8088/v1/generations/RUN-ID-HERE | jq
```

Responses:

- `200 OK`: result found.
- `404 Not Found`: unknown ID or server restarted.

The current repository is in-memory. Treat `run_id` as temporary and persist important results yourself.

## Scenario object reference

Each scenario includes:

| Field | Purpose |
|---|---|
| `id` | Stable identifier within the run. |
| `title` | Human-readable behavior under test. |
| `operation` | SOAP operation being exercised. |
| `category` | Risk taxonomy value. |
| `layer` | SOAP service, REST consumer, end-to-end, or contract-only. |
| `priority` | P0 through P3. |
| `objective` | The property being proved. |
| `rationale` | Why the test matters. |
| `preconditions` | Required environment and controls. |
| `test_data` | Valid baseline values. |
| `steps` | Ordered execution instructions. |
| `expected_results` | Observable pass/fail oracle. |
| `evidence_ids` | Links back to input facts. |
| `tags` | Search and selection labels. |
| `automation` | Automated, harness-required, or manual. |
| `mutation` | Machine-readable change applied to the baseline request. |

## Artifact integrity

Each returned artifact includes a SHA-256 digest. After writing an artifact, verify it with:

```bash
shasum -a 256 generated/TEST_PLAN.md
```

Compare the result with the corresponding artifact’s `sha256` field in `result.json`.

