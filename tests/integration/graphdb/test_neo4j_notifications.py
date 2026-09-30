"""Integration test that opening and filling a graph raises no Neo4j notifications.

Runs against the Docker Compose Neo4j instance from ``docker/docker-compose.ci.yml``.
A fresh database is the strict case: it has none of the labels and property keys the
store probes, which the server reports as UNRECOGNIZED notifications unless the driver
disables that classification. The second ``add`` brings a new name, which finds the
first entity as a stored candidate, so it also runs the neighbour lookup for stored
entities.
"""

import importlib.util
import logging
from collections.abc import Sequence
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity, ExtractionResult
from agrag.common.data_models.graph_schema import EntityType, GraphSchema
from agrag.cypher.entities import validate_identifier
from agrag.embedding.base import Embedder
from agrag.graphdb import build_graph_store
from agrag.ingestion import Graph
from agrag.ingestion.extract import Extractor
from tests.integration._schema_cleanup import drop_schema_for


neo4j_missing = importlib.util.find_spec("neo4j") is None


class _ConstantEmbedder(Embedder):
    """Embedder that returns one fixed four-dimensional vector for every text."""

    model = "constant"

    async def dimensions(self) -> int:
        """Return 4 dimensions."""
        return 4

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return the same vector for every text."""
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


class _FirstWordExtractor(Extractor):
    """Extractor that returns the first word of each chunk as one entity."""

    def __init__(self, label: str) -> None:
        """Store the entity label to emit."""
        self._label = label

    async def extract(self, chunk: Chunk, schema: GraphSchema) -> ExtractionResult:
        """Return the first word of the chunk as one entity."""
        word = chunk.text.split()[0]
        entity = ExtractedEntity(
            chunk_id=chunk.id,
            label=self._label,
            text=word,
            char_start=0,
            char_end=len(word),
        )
        return ExtractionResult(entities=[entity], relations=[], extractor_name="test")


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
async def test_open_and_add_log_no_server_notifications(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Graph.open and two Graph.add calls log no notification at WARNING or above."""
    label = validate_identifier(f"Thing_{uuid4().hex[:8]}")
    schema = GraphSchema(
        name="notifications-test",
        version="1",
        entities=[EntityType(label=label, description="A test entity.")],
        relations=[],
    )
    store = build_graph_store("neo4j")
    caplog.set_level(logging.WARNING, logger="neo4j.notifications")
    try:
        graph = await Graph.open(
            schema=schema,
            graph_store=store,
            embedder=_ConstantEmbedder(),
            extractor=_FirstWordExtractor(label),
        )
        await graph.add(text="Ada worked with Babbage in London.")
        await graph.add(text="Lovelace wrote notes on the Analytical Engine.")
    finally:
        try:
            await store.execute_write(
                "MATCH (d:Document)-[:PART_OF]->(:Chunk)-[:MENTIONED_IN]->"
                f"(:{label}) DETACH DELETE d"
            )
            await store.execute_write(
                f"MATCH (c:Chunk)-[:MENTIONED_IN]->(:{label}) DETACH DELETE c"
            )
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await drop_schema_for(store, label)
        finally:
            await store.close()

    notifications = [
        record.getMessage()
        for record in caplog.records
        if record.name == "neo4j.notifications"
    ]
    assert notifications == []
