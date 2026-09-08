from pathlib import Path

import yaml

from agentic_api.models import GenerateRequest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_example_request() -> GenerateRequest:
    content = (PROJECT_ROOT / "examples" / "exception_service_context.yaml").read_text(
        encoding="utf-8"
    )
    return GenerateRequest.model_validate(yaml.safe_load(content))
