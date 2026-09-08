from __future__ import annotations

import json
from typing import Protocol

from pydantic import BaseModel, Field

from .config import Settings
from .models import EvidenceRef, IntegrationContext, TestScenario


class ScenarioProposal(BaseModel):
    scenarios: list[TestScenario] = Field(default_factory=list)


class ScenarioAugmenter(Protocol):
    def propose(
        self,
        context: IntegrationContext,
        evidence: list[EvidenceRef],
        baseline: list[TestScenario],
    ) -> list[TestScenario]: ...


class DisabledAugmenter:
    def propose(
        self,
        context: IntegrationContext,
        evidence: list[EvidenceRef],
        baseline: list[TestScenario],
    ) -> list[TestScenario]:
        return []


class OpenAIResponsesAugmenter:
    """Optional additive scenario proposer; deterministic coverage remains authoritative."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key or not settings.openai_model:
            raise ValueError("OPENAI_API_KEY and OPENAI_MODEL are required for model augmentation")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "install the 'openai' project extra to enable model augmentation"
            ) from exc
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def propose(
        self,
        context: IntegrationContext,
        evidence: list[EvidenceRef],
        baseline: list[TestScenario],
    ) -> list[TestScenario]:
        prompt = {
            "context": context.model_dump(mode="json"),
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "existing_scenario_summaries": [
                {
                    "id": item.id,
                    "title": item.title,
                    "category": item.category.value,
                    "operation": item.operation,
                }
                for item in baseline
            ],
        }
        response = self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You are an API integration test analyst. Propose only material missing "
                        "REST-to-SOAP scenarios. Every scenario must cite supplied evidence ids. "
                        "Give concise, auditable rationales; never provide private chain-of-thought. "
                        "Do not duplicate an existing scenario."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt)},
            ],
            text_format=ScenarioProposal,
        )
        parsed = response.output_parsed
        return parsed.scenarios if parsed else []


def build_augmenter(settings: Settings, enabled: bool) -> ScenarioAugmenter:
    if not enabled:
        return DisabledAugmenter()
    if settings.model_provider == "openai":
        return OpenAIResponsesAugmenter(settings)
    raise ValueError("model augmentation was requested but AGENTIC_API_MODEL_PROVIDER is disabled")
