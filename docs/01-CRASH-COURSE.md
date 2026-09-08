# Crash course: from context to SOAP tests

This is the shortest path from “the server is running” to understanding and using the framework correctly.

## The idea in one minute

Your REST application calls a SOAP exception service. Testing only the REST endpoint misses SOAP envelope, namespace, action, field-mapping, declared-fault, timeout, and XML-parser risks. Testing only the SOAP endpoint misses the REST adapter’s status mapping and business behavior.

The framework converts your known facts into a neutral test model:

```text
your context
    -> normalized contract + evidence IDs
    -> operation-specific scenarios
    -> independent coverage review
    -> pytest scripts + detailed test plan + SOAP test double
```

The deterministic planner always runs. A model can optionally add ideas, but it cannot remove baseline cases or redefine the supplied contract.

## Five terms to know

| Term | Meaning |
|---|---|
| Context | The SOAP contract, REST consumer, mappings, rules, and operational requirements you supply. |
| Evidence | A stable ID such as `EV-0012` pointing to the exact input fact used by a scenario. |
| Scenario | One named test with objective, rationale, setup, data, steps, oracle, layer, priority, and automation level. |
| Decision trace | The public, auditable record of what each framework stage decided and why. It is not hidden model chain-of-thought. |
| Artifact | A generated file such as `TEST_PLAN.md`, `scenario_manifest.json`, or a pytest module. |

## Step 1: confirm the API

Open [http://127.0.0.1:8088/docs](http://127.0.0.1:8088/docs) or run:

```bash
curl -sS http://127.0.0.1:8088/health
```

Expected response:

```json
{"status":"ok"}
```

If it is unreachable, use the [startup section of the troubleshooting runbook](06-TROUBLESHOOTING.md#the-browser-says-it-cannot-connect).

## Step 2: generate the complete example

From the repository root:

```bash
./scripts/uv-local run agentic-soap generate \
  --context examples/exception_service_context.yaml \
  --output generated \
  --result-json generated/result.json
```

Expected summary:

```json
{
  "status": "completed",
  "scenarios": 44,
  "artifacts": 9
}
```

The `run_id` changes on every run. That is expected.

## Step 3: inspect what the agent produced

Start with these files:

1. `generated/TEST_PLAN.md` — readable, detailed plan for humans.
2. `generated/scenario_manifest.json` — machine-readable scenarios.
3. `generated/result.json` — complete context, evidence, trace, coverage, findings, and inline artifacts.
4. `generated/generated_tests/test_recordapplicationexception.py` — generated pytest module.

Summarize coverage:

```bash
jq '.coverage' generated/result.json
```

The included example should report 44 scenarios, 11 categories, and an empty `uncovered_items` list.

Show the four framework stages:

```bash
jq '.decision_trace[] | {sequence, agent, phase, status, summary}' generated/result.json
```

You should see:

1. `context-analyzer`
2. `scenario-planner`
3. `coverage-reviewer`
4. `artifact-generator`

Trace one test back to its source facts:

```bash
jq '.scenarios[0] | {id, title, evidence_ids}' generated/result.json
jq '.evidence[] | select(.id == "EV-0012")' generated/result.json
```

The second command uses an example evidence ID. Use an ID returned by the first command if it differs.

## Step 4: understand automation honesty

Every scenario has one of three automation levels:

- `automated` means the direct SOAP runner can control the request and assert the response.
- `harness_required` means the test needs controlled downstream behavior such as a timeout, reset, SOAP Fault, or captured outbound XML.
- `manual` means essential contract information is missing. The framework reports the gap instead of inventing an assertion.

This distinction matters. A black-box REST client cannot force a SOAP dependency to reset its connection unless the application can point to a controllable test double.

## Step 5: run the safe tests

This command validates every generated scenario definition without sending network traffic:

```bash
./scripts/uv-local run pytest generated/generated_tests -m "not live"
```

Expected result for the included example:

```text
44 passed, 24 deselected
```

The deselected tests are the live SOAP cases. They are intentionally excluded.

## Step 6: know the live-test safety gate

Live tests require both conditions:

```bash
export ALLOW_LIVE_SOAP_TESTS=true
./scripts/uv-local run pytest generated/generated_tests --run-live -m live
```

Before doing this, replace the endpoint and test data with approved non-production values. Never point the generated suite at production merely to see whether it works.

## What to do next

- To model your service, continue to the [context authoring guide](03-CONTEXT-AUTHORING.md).
- To learn by doing, complete the [training workbook](training/WORKBOOK.md).
- To understand each API response field, use the [API reference](04-API-REFERENCE.md).
- To test SOAP faults and timeouts, read the [generated-test guide](05-GENERATED-TESTS.md).

