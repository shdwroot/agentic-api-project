# Training answer key

Attempt each lab before using this guide.

## Lab 1

`GET /health` proves the API process is responsive. It does not prove WSDL validity, generation correctness, SOAP connectivity, credentials, or REST-to-SOAP behavior.

The capabilities response lists 11 scenario categories. The relevant guarantee is: “Declared SOAP faults are treated as mandatory coverage.” A model key is not required because deterministic planning is the default.

Boundary classifications:

1. Incorrect namespace rejection: `soap_service`.
2. REST-to-SOAP field value mapping: `end_to_end`.
3. SOAP fault to REST 422: `end_to_end`.
4. Missing mapping contract: `contract_only`.

## Lab 2

The minimal training request produces 16 scenarios and 9 inline artifacts. Its expected status is `completed_with_warnings` because no REST consumer was supplied, so REST mapping coverage is intentionally limited.

Artifacts are inline because the synchronous API returns a self-contained result. For durable evidence, save the response in controlled artifact storage; the built-in run repository is in memory.

Retrieval succeeds only until the server process restarts.

## Lab 3

- Review meeting: `TEST_PLAN.md`.
- Programmatic use: `scenario_manifest.json`.
- Complete audit record: `result.json`.
- CLI output materializes individual files immediately, while an API client must decode and write each inline artifact.

The full example should produce 44 scenarios and 9 artifacts.

## Lab 4

A good audit result has all of these:

- Scenario title names the exact operation and field or fault.
- `objective` says what property is proved.
- `rationale` explains the risk.
- Expected results are observable rather than subjective.
- Every evidence ID exists and points to a relevant context location.

The coverage reviewer is separate so generation and evaluation do not share the same blind spot. It independently checks duplicate IDs, evidence validity, missing oracles, minimum category coverage, and every declared fault.

## Lab 5

For the supplied full example:

- P0: 21
- P1: 22
- P2: 1
- Total: 44
- Categories: 11
- Uncovered items: none

Zero framework-reported gaps means all minimum rules were satisfied for the supplied context. It cannot prove that a human listed every real operation, fault, rule, or mapping.

Harness-required timeout cases need control over downstream delay. Fault cases need control over the returned SOAP Fault. Mapping cases need captured outbound XML and the ability to route the REST application to the test double.

## Lab 6

The WSDL-only example should generate 15 scenarios with `completed_with_warnings`. It warns that no REST consumer contract was supplied. WSDL describes the SOAP contract, not the REST domain model or adapter’s mapping policy; inferring those would create untrustworthy tests.

## Lab 7

The full example’s offline run should report:

```text
44 passed, 24 deselected
```

The live-only command skips unless both `ALLOW_LIVE_SOAP_TESTS=true` and `--run-live` are present. Two controls reduce accidental execution caused by a stale environment variable or a copied command alone.

## Lab 8

Success returns HTTP 200 with `GeneratedSuccess`. The named fault returns HTTP 500 with a SOAP Fault containing `InvalidExceptionFault`.

The real REST application needs a supported test-time SOAP endpoint override pointing to the double. Automated mapping assertions also need request capture plus visibility into REST results, logs, audit records, and downstream call counts.

## Capstone review

Reject the capstone as incomplete when it has generic field names, credentials in source, omitted declared faults, implicit mappings, non-measurable requirements, production data, or no plan for harness-required cases.

Prefer a smaller precise scope over a broad context filled with assumptions.

