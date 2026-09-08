import json
import re
from pathlib import Path

from agentic_api.config import Settings
from agentic_api.models import GenerateRequest
from agentic_api.orchestrator import TestGenerationOrchestrator

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"\]\(([^)]+)\)")


def test_training_request_matches_documented_expected_result():
    payload = json.loads(
        (PROJECT_ROOT / "examples" / "training" / "minimal-generation.json").read_text()
    )

    result = TestGenerationOrchestrator(Settings()).generate(
        GenerateRequest.model_validate(payload)
    )

    assert result.status == "completed_with_warnings"
    assert len(result.scenarios) == 16
    assert len(result.artifacts) == 9
    assert any(
        "No REST consumer" in warning for step in result.decision_trace for warning in step.warnings
    )


def test_local_markdown_links_resolve():
    markdown_files = [PROJECT_ROOT / "README.md", *(PROJECT_ROOT / "docs").rglob("*.md")]

    for markdown_file in markdown_files:
        for raw_target in MARKDOWN_LINK.findall(markdown_file.read_text(encoding="utf-8")):
            target = raw_target.split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            assert (markdown_file.parent / target).resolve().exists(), (
                f"broken link in {markdown_file.relative_to(PROJECT_ROOT)}: {raw_target}"
            )
