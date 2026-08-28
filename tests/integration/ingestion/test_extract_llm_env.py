"""Integration test: the OpenAI-compatible LLM client reaches a real endpoint.

Loads LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL_ID from the environment (or
.env) and runs the BAML extraction function through an ``openai-generic`` client.
Skips when those variables are not set, so a default ``make test-integration``
run needs no endpoint. No model name is hardcoded anywhere in this file.
"""

import os

import pytest

from agrag.ingestion.extract import ExtractionLLMSettings
from agrag.llm.baml_client import b
from agrag.llm.baml_client.type_builder import TypeBuilder
from agrag.llm.client_registry import build_client_registry


@pytest.mark.integration
async def test_extraction_reaches_openai_compatible_endpoint() -> None:
    """A real endpoint returns a structured extraction result."""
    if not os.environ.get("LLM_BASE_URL") or not os.environ.get("LLM_MODEL_ID"):
        pytest.skip("LLM_BASE_URL/LLM_MODEL_ID not set; skipping live LLM test.")

    settings = ExtractionLLMSettings.from_openai_compatible_env()
    registry = build_client_registry(settings.clients, strategy=settings.strategy)

    type_builder = TypeBuilder()
    type_builder.ExtractedEntityLabel.add_value("Person")
    type_builder.ExtractedEntityLabel.add_value("Organization")
    type_builder.ExtractedRelationLabel.add_value("RELATED_TO")

    result = await b.ExtractEntitiesAndRelations(
        "Ada Lovelace worked at the Analytical Engine Company.",
        {"client_registry": registry, "tb": type_builder},
    )
    assert hasattr(result, "entities")
    assert isinstance(result.entities, list)
