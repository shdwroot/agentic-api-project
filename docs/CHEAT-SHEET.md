# Cheat sheet

## Start

```bash
./scripts/uv-local sync --extra dev
./scripts/uv-local run uvicorn agentic_api.main:app --host 127.0.0.1 --port 8088
```

Swagger: [http://127.0.0.1:8088/docs](http://127.0.0.1:8088/docs)

## Health

```bash
curl -sS http://127.0.0.1:8088/health
```

## Generate

```bash
./scripts/uv-local run agentic-soap generate \
  --context examples/exception_service_context.yaml \
  --output generated \
  --result-json generated/result.json
```

A full run prints `[1/10]` through `[10/10]`. If cloud-synchronized workspace storage is slow, use `/tmp/agentic-soap-generated` for both output paths.

## Inspect

```bash
jq '.coverage' generated/result.json
jq '.validation_findings' generated/result.json
jq '.decision_trace[] | {agent, status, summary, warnings}' generated/result.json
jq '.scenarios[] | select(.priority == "P0") | {id, title, automation}' generated/result.json
```

## Safe offline tests

```bash
./scripts/uv-local run pytest generated/generated_tests -m "not live"
```

## Explicit live tests

```bash
export SOAP_ENDPOINT=https://approved-test-host/soap
export ALLOW_LIVE_SOAP_TESTS=true
./scripts/uv-local run pytest generated/generated_tests --run-live -m live -vv
```

## SOAP double

```bash
MOCK_SOAP_MODE=success ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
MOCK_SOAP_MODE=fault:InvalidExceptionFault ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
MOCK_SOAP_MODE=nonxml ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
MOCK_SOAP_MODE=reset ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
MOCK_SOAP_MODE=timeout MOCK_SOAP_DELAY_SECONDS=5 ./scripts/uv-local run python generated/generated_tests/mock_soap_server.py
```

## Automation meanings

- `automated`: direct SOAP runner can execute it.
- `harness_required`: requires controlled SOAP dependency or captured request.
- `manual`: missing contract/test seam prevents honest automation.

## Golden rule

Fix incorrect context and regenerate. Do not hide a coverage gap or rewrite a failing oracle merely to make the suite green.
