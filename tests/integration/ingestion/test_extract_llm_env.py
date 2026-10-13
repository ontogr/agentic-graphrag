"""Integration test: the OpenAI-compatible LLM client reaches a real endpoint.

Loads LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL_ID from the environment (or
.env) and runs BAMLExtractor through an ``openai-generic`` client.
Skips when those variables are not set, so a default ``make test-integration``
run needs no endpoint. No model name is hardcoded anywhere in this file.
"""

import os
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion.extract import BAMLExtractor, ExtractionLLMSettings


async def test_extraction_reaches_openai_compatible_endpoint() -> None:
    """A real endpoint returns a structured extraction result."""
    if not os.environ.get("LLM_BASE_URL") or not os.environ.get("LLM_MODEL_ID"):
        pytest.skip("LLM_BASE_URL/LLM_MODEL_ID not set; skipping live LLM test.")

    settings = ExtractionLLMSettings.from_openai_compatible_env()

    text = "Ada Lovelace worked at the Analytical Engine Company."
    chunk = Chunk(
        id=uuid4(),
        document_id=uuid4(),
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )
    schema = GraphSchema(
        name="env-check",
        version="1",
        entities=[EntityType(label="Person", description="A named individual.")],
        relations=[],
    )

    result = await BAMLExtractor(settings=settings).extract(chunk, schema)

    assert isinstance(result, ExtractionResult)
    assert isinstance(result.entities, list)
