# Instructor guide

This guide supports a 90–120 minute team workshop for QA engineers, developers, architects, and operations staff.

## Outcomes

Learners should leave able to generate, audit, and safely execute a context-driven SOAP test plan without confusing generated coverage with proof of production correctness.

## Preparation checklist

At least one day before training:

- [ ] Confirm Python 3.11+, `uv`, `curl`, and `jq` on learner machines.
- [ ] Run `./scripts/uv-local sync --extra dev`.
- [ ] Run `./scripts/uv-local run pytest` and confirm framework tests pass.
- [ ] Start the API and confirm `/health` and `/docs` return 200.
- [ ] Generate the full example and run offline generated tests.
- [ ] Confirm ports 8088 and 9089 are available or choose alternatives.
- [ ] Decide whether the class will use only synthetic data.
- [ ] Do not distribute real credentials or production endpoints.
- [ ] Keep the [answer key](ANSWER-KEY.md) closed until discussion.

## Suggested agenda

| Time | Topic | Material |
|---:|---|---|
| 0–10 min | Why REST-only and SOAP-only tests both miss risk | Crash-course architecture |
| 10–20 min | Context, evidence, scenario, trace, artifact | Crash-course vocabulary |
| 20–35 min | API and CLI generation | Workbook labs 1–3 |
| 35–50 min | Audit one scenario and coverage report | Workbook labs 4–5 |
| 50–65 min | Full context versus WSDL-only | Workbook lab 6 |
| 65–80 min | Offline safety gate and automation honesty | Workbook lab 7 |
| 80–100 min | SOAP-double success and fault | Workbook lab 8 |
| 100–120 min | Capstone briefing and Q&A | Context authoring guide |

For a 90-minute session, demonstrate lab 8 instead of having every learner run it.

## Teaching notes

### Emphasize evidence over volume

A plan with 100 generic cases is weaker than 20 operation-specific cases tied to exact contract facts. Ask learners to explain what one evidence ID proves.

### Separate the layers

Use this prompt repeatedly:

> Which component’s behavior does this assertion prove?

If the answer is unclear, the scenario needs a tighter layer or better instrumentation.

### Explain automation honesty

`harness_required` is not a failure. It states that a test seam is necessary. The dangerous outcome is labeling a scenario automated when the test cannot control or observe its claimed behavior.

### Explain “show its work” carefully

The decision trace is an auditable product feature: facts, public decisions, consequences, warnings, and evidence references. It is not private model reasoning. Learners should judge the visible basis and oracle.

### Keep live execution out of introductory training

The offline and SOAP-double labs teach all core mechanics without calling a real service. Use live direct SOAP tests only in a separate environment-specific session.

## Discussion prompts

1. What failure can pass a direct SOAP happy-path test but fail through the REST adapter?
2. What failure can pass a REST status assertion while recording the wrong SOAP field values?
3. Why should declared faults be mandatory coverage?
4. Why is a blank XML element different from a missing element?
5. What evidence is needed to prove no duplicate record was created after a timeout?
6. Which context fields could contain sensitive information, and should model augmentation receive them?
7. What should cause a CI pipeline to block deployment?

## Demonstration script

```bash
curl -sS http://127.0.0.1:8088/health

./scripts/uv-local run agentic-soap generate \
  --context examples/exception_service_context.yaml \
  --output generated/training \
  --result-json generated/training/result.json

jq '.coverage' generated/training/result.json

jq '.decision_trace[] | {agent, status, summary}' \
  generated/training/result.json

./scripts/uv-local run pytest generated/training/generated_tests -m "not live" -q
```

Keep `generated/training/TEST_PLAN.md` open during discussion.

## Knowledge check

Ask learners to answer without notes:

1. What two controls enable live tests?
2. Where is the complete decision trace stored?
3. What does `harness_required` mean?
4. Why can WSDL-only analysis not verify REST mapping?
5. What happens to API run IDs when the process restarts?

Expected answers:

1. Environment variable `ALLOW_LIVE_SOAP_TESTS=true` and pytest flag `--run-live`.
2. `result.json` or the generation API response.
3. The scenario needs controlled downstream behavior or additional observation infrastructure.
4. WSDL does not define the REST/domain source fields or adapter policy.
5. The in-memory repository loses them.

## Capstone rubric

Score each dimension from 0 to 2. A strong submission scores at least 16/20 and has no safety failure.

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| Scope | Boundary unclear | Partial boundary | Trigger and layers explicit |
| SOAP contract | Generic/incomplete | Main operation only | Operations, fields, order, actions, namespace complete |
| Faults | Missing | Some faults | Every in-scope declared fault and mapping present |
| REST mapping | Missing | Partial | Every required SOAP field has explicit source/default |
| Business rules | Subjective | Some observable | Three or more precise invariants |
| Reliability | Missing | Timeout only | Timeout, retry, idempotency, duplicates explicit |
| Security | Secrets or production data | Basic redaction note | Sensitive fields, redaction, auth handling explicit |
| Observability | Missing | Correlation only | Correlation, audit, logs, call counts, persistence observable |
| Review | Findings ignored | Warnings noted | Trace/evidence audited and findings dispositioned |
| Execution plan | Unsafe or absent | Offline only | Offline pass plus credible harness/live approval plan |

Automatic failure conditions:

- Production credentials or personal data committed to context.
- Live execution against production.
- A declared fault knowingly omitted without a documented scope decision.
- A harness-required test reported as passed without controlling the dependency.

## Follow-up assignment

Have each integration team produce one reviewed context file and test dossier. Conduct a 30-minute peer review where another team traces three P0 scenarios to evidence and challenges the oracles.

