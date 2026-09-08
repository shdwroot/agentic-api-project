# Documentation and training hub

Use this page as the front door for the Agentic SOAP Test Framework.

## Choose your path

| I want to… | Start here | Time |
|---|---|---:|
| Understand the framework quickly | [Crash course](01-CRASH-COURSE.md) | 20 minutes |
| Use it on my own SOAP integration | [User guide](02-USER-GUIDE.md) | 45 minutes |
| Build a high-quality context file | [Context authoring guide](03-CONTEXT-AUTHORING.md) | 30 minutes |
| Call the REST API directly | [API reference](04-API-REFERENCE.md) | 15 minutes |
| Run and customize generated tests | [Generated-test guide](05-GENERATED-TESTS.md) | 30 minutes |
| Fix a problem | [Troubleshooting runbook](06-TROUBLESHOOTING.md) | As needed |
| Teach or learn through exercises | [Training workbook](training/WORKBOOK.md) | 90 minutes |
| Deliver a team workshop | [Instructor guide](training/INSTRUCTOR-GUIDE.md) | 90–120 minutes |
| Check exercise results | [Answer key](training/ANSWER-KEY.md) | After attempting labs |
| Recall a command quickly | [Cheat sheet](CHEAT-SHEET.md) | 2 minutes |

## Recommended learning order

```text
Crash course
    |
    v
Generate the included example
    |
    v
Read one scenario and trace it to evidence
    |
    v
Run offline generated tests
    |
    v
Author context for your service
    |
    v
Add a SOAP test double for fault and timeout cases
    |
    v
Run explicitly approved tests against a non-production endpoint
```

## Audience map

- QA engineers should complete the crash course, context-authoring guide, and workbook.
- Developers integrating the SOAP client should focus on REST-to-SOAP mappings, declared-fault handling, test-double configuration, and generated tests.
- Architects and technical leads should review the system boundary and deterministic-versus-model trade-offs in the main [README](../README.md).
- Operations and support staff should focus on correlation identifiers, safe logging, dependency errors, and the troubleshooting runbook.

## Training promise

After completing the workbook, a learner should be able to:

1. Explain what the framework can and cannot prove.
2. Describe a REST-to-SOAP exception-service integration as structured context.
3. Generate evidence-linked scenarios through the CLI or API.
4. Interpret the decision trace, coverage report, and validation findings.
5. Run offline definition tests without contacting any service.
6. Use the generated SOAP double for controlled fault injection.
7. Enable live tests only against an approved non-production endpoint.

