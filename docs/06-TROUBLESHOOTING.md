# Troubleshooting runbook

Use this runbook when startup, generation, retrieval, or generated tests do not behave as expected.

## The browser says it cannot connect

### Expected

[http://127.0.0.1:8088/docs](http://127.0.0.1:8088/docs) loads Swagger UI.

### Checks

From the repository root:

```bash
curl -i http://127.0.0.1:8088/health
```

If connection is refused, start the server:

```bash
./scripts/uv-local sync --extra dev
./scripts/uv-local run uvicorn agentic_api.main:app --host 127.0.0.1 --port 8088
```

Leave that terminal open. Open a second terminal for CLI commands.

If port 8088 is occupied:

```bash
lsof -nP -iTCP:8088 -sTCP:LISTEN
```

Either stop the known conflicting development process or choose a different port:

```bash
./scripts/uv-local run uvicorn agentic_api.main:app --host 127.0.0.1 --port 8090
```

Then use `http://127.0.0.1:8090/docs`.

## `uv` cannot write its cache

Point the cache at a writable temporary directory for the current command:

```bash
UV_CACHE_DIR=/tmp/agentic-api-uv-cache ./scripts/uv-local sync --extra dev
```

This changes dependency-cache location, not application storage.

## Why commands use `scripts/uv-local`

This checkout is under macOS `Documents`. Cloud storage may offload package files inside the project’s `.venv`; Python can then block while importing a dependency such as `pydantic_settings`. The wrapper sets `UV_PROJECT_ENVIRONMENT` and `UV_CACHE_DIR` to local paths under `/private/tmp` before invoking uv.

Use:

```bash
./scripts/uv-local sync --extra dev
./scripts/uv-local run agentic-soap --help
```

The temporary environment can be recreated safely after a reboot by running the sync command again. You may override either location with the corresponding environment variable.

## CLI command is not found

Run through the local uv wrapper:

```bash
./scripts/uv-local run agentic-soap --help
```

If it still fails, refresh the environment:

```bash
./scripts/uv-local sync --extra dev
```

Fallback invocation:

```bash
./scripts/uv-local run python -m agentic_api.cli --help
```

## Generation appears stuck while writing files

Current versions print one progress line per artifact and replace files atomically. A normal full-example run reaches `[10/10]` before printing its JSON summary.

The first run after source changes may spend roughly 20–30 seconds at `Building agentic-soap-test-framework`. That is package refresh, not test generation. A repeated run normally skips the build and proceeds directly to file progress.

Older versions wrote directly over existing files. On macOS, a project stored under `Documents` or another cloud-synchronized folder can contain `compressed,dataless` placeholders. Opening one in place may wait for cloud hydration even though the generated content is small.

Check file flags with:

```bash
find generated -type f -exec ls -lO {} \;
```

As an immediate isolation test, generate outside the synchronized folder:

```bash
./scripts/uv-local run agentic-soap generate \
  --context examples/exception_service_context.yaml \
  --output /tmp/agentic-soap-generated \
  --result-json /tmp/agentic-soap-generated/result.json
```

If `/tmp` completes but the workspace output does not, cloud-file hydration is the likely cause. Keep large ephemeral generation output outside synchronized folders or retain the atomic-write version of the CLI.

## API returns 422

Read the response detail:

```bash
curl -sS ... | jq
```

Common fixes:

- Supply either `context` or `documents`.
- Include a WSDL for document-only analysis.
- Quote SOAP version as `"1.1"` or `"1.2"` in YAML.
- Ensure every `mappings[].soap_operation` exactly matches an operation name.
- Ensure `min_length <= max_length` and `minimum <= maximum`.
- Keep document content below the configured byte limit.
- Keep `options.max_scenarios` at or below the server limit.

Use Pydantic’s returned field path to locate nested validation failures.

## Generation says `completed_with_warnings`

Inspect stage warnings:

```bash
jq '.decision_trace[] | select(.warnings | length > 0) | {agent, warnings}' result.json
```

Typical warnings:

- No SOAP endpoint: generation works, but live tests need `SOAP_ENDPOINT`.
- No REST consumer: SOAP tests work, but REST mapping coverage is limited.
- No fields discovered: WSDL extraction could not resolve request fields.
- Scenario limit applied: increase `options.max_scenarios` within server policy.
- Model unavailable: deterministic generation still completed.

## Retrieval returns 404 for a valid-looking run ID

Generation storage is currently in memory. Restarting the API erases retrievable runs. Generate again or read the `result.json` saved by the CLI.

## Offline tests are unexpectedly trying to connect

Run with marker exclusion:

```bash
./scripts/uv-local run pytest generated/generated_tests -m "not live"
```

Do not add `--run-live`. Ensure custom tests do not call `execute_scenario` outside a `live`-marked test.

## Live tests are skipped

Both controls are required:

```bash
export ALLOW_LIVE_SOAP_TESTS=true
./scripts/uv-local run pytest generated/generated_tests --run-live -m live
```

A skip is expected if either control is missing.

## Live success case returns a SOAP Fault

Check, in order:

1. `SOAP_ENDPOINT` is the approved test endpoint.
2. SOAP version and request content type match.
3. Target namespace is exact.
4. Operation request element is exact.
5. SOAPAction includes the required value and quoting.
6. Authentication environment variables are populated.
7. Example field values satisfy test-environment business rules.
8. XML element ordering matches the service schema.

The generic generator writes fields in context order. Put fields in schema sequence order.

## A negative case unexpectedly succeeds

Do not immediately change the test to accept success. Determine whether:

- the context incorrectly marked a field required
- the server performs only presence validation and accepts blank values
- schema validation is disabled
- a gateway normalized or removed the mutation
- the request reached a different operation or environment
- the service silently truncates or defaults data

Capture redacted outbound XML and verify the mutation was actually transmitted.

## SOAP fault mapping test cannot run automatically

This is expected when the scenario is `harness_required`. The REST application must support a test-time SOAP endpoint override. Start the generated double with the named fault and point the REST deployment at it.

If endpoint override is impossible, document the test as manual or add a supported virtualization seam. Do not claim that ordinary invalid input proves every dependency fault path.

## Model augmentation does nothing

All conditions must be present:

```bash
./scripts/uv-local sync --extra dev --extra openai
export AGENTIC_API_MODEL_PROVIDER=openai
export OPENAI_API_KEY='value-from-secret-store'
export OPENAI_MODEL='an-available-model-name'
```

The request must also set:

```yaml
options:
  model_augmentation: true
```

Provider errors appear as trace warnings and deterministic generation remains available. Confirm data-governance approval before sending internal context to an external provider.

## Escalation evidence

When asking for help, include:

- exact command or API request with secrets removed
- exact error text and HTTP status
- framework version and Python version
- context section involved
- relevant decision-trace warning
- scenario ID and its evidence IDs
- redacted SOAP exchange when a live test failed
- whether the failure is generation, test harness, SOAP service, REST adapter, or environment setup
