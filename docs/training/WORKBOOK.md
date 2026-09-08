# Hands-on training workbook

This workbook teaches the framework through direct use. Complete the exercises in order. The expected duration is 90 minutes for an individual or two hours with group discussion.

Use the [answer key](ANSWER-KEY.md) only after attempting each lab.

## Learning objectives

By the end, you will be able to:

1. Identify the SOAP-service, REST-adapter, and end-to-end test layers.
2. Generate a scenario plan through both the API and CLI.
3. Trace a scenario back to its source evidence.
4. Interpret coverage and automation levels without overstating what passed.
5. Improve a context contract to obtain more specific tests.
6. run offline checks and controlled SOAP-double behavior safely.

## Prerequisites

- Repository checkout
- Python 3.11+
- `uv`
- `curl`
- `jq`
- Two terminal windows for the SOAP-double lab

Install dependencies:

```bash
./scripts/uv-local sync --extra dev
```

Start the framework in terminal A:

```bash
./scripts/uv-local run uvicorn agentic_api.main:app --host 127.0.0.1 --port 8088
```

Use terminal B for the exercises.

## Lab 1 — Orient yourself

Time: 10 minutes.

### Task 1.1: check liveness

```bash
curl -sS http://127.0.0.1:8088/health
```

Write down what this proves and what it does not prove.

### Task 1.2: inspect capabilities

```bash
curl -sS http://127.0.0.1:8088/v1/capabilities | jq
```

Answer:

1. How many scenario categories are supported?
2. Which guarantee prevents a declared SOAP fault from silently disappearing?
3. Does the framework require a model API key?

### Task 1.3: classify boundaries

For each statement, choose `soap_service`, `rest_consumer`, `end_to_end`, or `contract_only`:

1. The SOAP endpoint rejects an incorrect namespace.
2. REST field `error.code` appears in SOAP element `exceptionCode`.
3. `InvalidExceptionFault` becomes REST status 422.
4. The supplied context lacks a mapping for a required SOAP field.

## Lab 2 — Generate through the REST API

Time: 10 minutes.

### Task 2.1: submit the training request

```bash
curl -sS http://127.0.0.1:8088/v1/generations \
  -H 'Content-Type: application/json' \
  --data @examples/training/minimal-generation.json \
  -o /tmp/agentic-soap-training-result.json
```

Inspect the top-level result:

```bash
jq '{run_id, status, scenarios: (.scenarios | length), artifacts: (.artifacts | length)}' \
  /tmp/agentic-soap-training-result.json
```

Questions:

1. Why is the status a warning rather than a failure?
2. Why does the response contain artifacts inline?
3. Where would you persist this result for audit evidence?

### Task 2.2: retrieve by run ID

```bash
RUN_ID=$(jq -r '.run_id' /tmp/agentic-soap-training-result.json)
curl -sS "http://127.0.0.1:8088/v1/generations/${RUN_ID}" \
  | jq '{run_id, status, scenario_count: (.scenarios | length)}'
```

Restarting the API invalidates this lookup because the MVP repository is in memory.

## Lab 3 — Generate through the CLI

Time: 10 minutes.

Generate the detailed project example:

```bash
./scripts/uv-local run agentic-soap generate \
  --context examples/exception_service_context.yaml \
  --output generated/training \
  --result-json generated/training/result.json
```

Confirm the artifact list:

```bash
find generated/training -maxdepth 2 -type f | sort
```

Questions:

1. Which file is best for a test-plan review meeting?
2. Which file is best for another program to consume?
3. Which file contains the complete “show your work” trace?
4. Why is CLI output more convenient than inline API artifacts for local use?

## Lab 4 — Audit one scenario

Time: 15 minutes.

### Task 4.1: choose a P0 field test

```bash
jq '.scenarios[] \
  | select(.priority == "P0" and .category == "field_validation") \
  | {id, title, objective, evidence_ids}' \
  generated/training/result.json
```

Pick one scenario ID and inspect its complete record:

```bash
SCENARIO_ID='replace-me'
jq --arg id "$SCENARIO_ID" '.scenarios[] | select(.id == $id)' \
  generated/training/result.json
```

### Task 4.2: resolve evidence

Copy one evidence ID from the scenario:

```bash
EVIDENCE_ID='replace-me'
jq --arg id "$EVIDENCE_ID" '.evidence[] | select(.id == $id)' \
  generated/training/result.json
```

Verify:

- The evidence location points to the relevant operation or field.
- The excerpt supports the scenario.
- The SHA-256 field is present.
- The expected results describe observable behavior.

### Task 4.3: inspect the stage trace

```bash
jq '.decision_trace[] \
  | {sequence, agent, phase, status, summary, decisions, warnings}' \
  generated/training/result.json
```

Explain why the `coverage-reviewer` is separate from the `scenario-planner`.

## Lab 5 — Read coverage honestly

Time: 10 minutes.

```bash
jq '.coverage' generated/training/result.json
```

Answer:

1. How many scenarios are P0, P1, and P2?
2. Which categories are represented?
3. Are there uncovered items?
4. Does zero uncovered items prove that the source context listed every real business rule?

Now list scenarios requiring a harness:

```bash
jq '.scenarios[] \
  | select(.automation == "harness_required") \
  | {id, category, title}' generated/training/result.json
```

Choose one timeout or fault case and describe the external behavior that must be controlled.

## Lab 6 — Compare full context with WSDL-only context

Time: 10 minutes.

```bash
./scripts/uv-local run agentic-soap generate \
  --context examples/wsdl_only_request.yaml \
  --output generated/wsdl-training \
  --result-json generated/wsdl-training/result.json
```

Inspect warnings and categories:

```bash
jq '{
  status,
  warnings: [.decision_trace[].warnings[]],
  coverage: .coverage.by_category,
  scenario_count: (.scenarios | length)
}' generated/wsdl-training/result.json
```

Explain why the framework does not invent REST field mappings from a WSDL.

## Lab 7 — Run generated tests safely

Time: 10 minutes.

### Task 7.1: offline suite

```bash
./scripts/uv-local run pytest generated/training/generated_tests -m "not live" -q
```

Expected: 44 definition checks pass and live tests are deselected.

### Task 7.2: prove the safety gate

Run without either explicit control:

```bash
./scripts/uv-local run pytest generated/training/generated_tests -m live -q
```

The live cases should skip. Do not enable them during this training unless an instructor has provided a disposable SOAP target.

Explain why two controls are safer than only an environment variable or only a CLI flag.

## Lab 8 — Control a SOAP dependency

Time: 15 minutes.

Use a third terminal or temporarily stop the API in terminal A. The SOAP double uses port 9089, not 8088.

### Task 8.1: success response

Start the double:

```bash
MOCK_SOAP_MODE=success \
  ./scripts/uv-local run python generated/training/generated_tests/mock_soap_server.py
```

From another terminal:

```bash
curl -i http://127.0.0.1:9089/soap \
  -H 'Content-Type: text/xml; charset=utf-8' \
  --data '<Envelope/>'
```

Expected: HTTP 200 and a SOAP envelope containing `GeneratedSuccess`.

### Task 8.2: named fault

Stop the double with Ctrl+C and restart it:

```bash
MOCK_SOAP_MODE=fault:InvalidExceptionFault \
  ./scripts/uv-local run python generated/training/generated_tests/mock_soap_server.py
```

Repeat the curl request. Expected: HTTP 500 with a SOAP Fault naming `InvalidExceptionFault`.

Explain what configuration the real REST application needs before this can test its fault mapping.

## Capstone — Model your exception integration

Time: 30–60 minutes beyond the core workshop.

Copy the full context example and replace it with one real, non-production integration:

```bash
cp examples/exception_service_context.yaml /tmp/my-exception-context.yaml
```

Deliver:

1. One or more SOAP operations with ordered request fields.
2. Every declared SOAP fault in scope.
3. The REST route and trigger.
4. Field and fault mappings.
5. At least three observable business rules.
6. Explicit timeout, retry, idempotency, redaction, and correlation expectations.
7. A completed generation with reviewed warnings.
8. Passing offline definition tests.
9. A written plan for harness-required cases.

Use the rubric in the [instructor guide](INSTRUCTOR-GUIDE.md#capstone-rubric) for self-assessment.

