"""Integration proof that Neo4j graph-store spans carry queries, not vectors.

Runs ``upsert_nodes``, ``upsert_relations``, a read, and a ``transaction()``
block with a write inside it against the Docker Compose Neo4j instance from
``docker/docker-compose.ci.yml`` (``make dev-services-up``), through a real
SDK ``TracerProvider`` with an in-memory exporter. The captured span tree
goes to a JSON artifact for hand inspection.
"""

import importlib.util
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.cypher.entities import validate_identifier
from agrag.graphdb.neo4j import Neo4jGraphStore


neo4j_missing = importlib.util.find_spec("neo4j") is None


def _span_tree_path() -> Path:
    """Return the artifact path for the captured span tree."""
    root = Path(__file__).resolve().parents[3]
    directory = root / "reports" / "graphdb"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "neo4j_tracing.json"


def _write_span_tree(path: Path, spans: Sequence[ReadableSpan]) -> None:
    """Write the captured span tree artifact, verifying the round trip."""
    payload: dict[str, Any] = {
        "spans": [
            {
                "id": span.context.span_id,
                "trace_id": format(span.context.trace_id, "032x"),
                "parent_id": span.parent.span_id if span.parent else None,
                "name": span.name,
                "attributes": dict(span.attributes or {}),
                "status": span.status.status_code.name,
            }
            for span in spans
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    assert json.loads(path.read_text()) == payload


def _assert_query_parameters_never_carry_vectors(
    spans: Sequence[ReadableSpan],
) -> None:
    """Assert no vector value reaches a span while the scalars beside it do.

    Two shapes are covered. A top-level vector parameter is skipped whole
    by ``_query_parameter_attributes``, so the read that binds one never
    grows a ``db.query.parameter.<vector key>`` attribute at all. A vector
    nested inside an ``UNWIND $records`` write's record dictionaries is
    stripped field by field, so the serialized records attribute survives
    with its scalar fields intact and its vector fields gone.

    The two nodes written by this test use distinctive leading digits
    (``7.x`` and ``8.x``) rather than a value shared with the probe read, so
    a leaked vector is caught by inspecting the serialized records
    themselves instead of by a substring that no failure could ever produce.
    """
    for span in spans:
        assert "db.query.parameter.embedding" not in (span.attributes or {})

    probe = next(
        span
        for span in spans
        if (span.attributes or {}).get("db.query.text") == "RETURN $text AS text"
    )
    probe_attributes = probe.attributes or {}
    assert probe_attributes["db.query.parameter.text"] == "sepsis protocol"
    assert "db.query.parameter.embedding" not in probe_attributes

    records_spans = [
        span
        for span in spans
        if span.name == "agrag.graphdb.execute_write"
        and "db.query.parameter.records" in (span.attributes or {})
    ]
    assert records_spans, "no UNWIND $records write span was captured"
    for span in records_spans:
        records_attribute = str((span.attributes or {})["db.query.parameter.records"])
        assert "embedding" not in records_attribute
        assert "7.1" not in records_attribute
        assert "8.1" not in records_attribute
    assert any(
        "sepsis protocol" in str((span.attributes or {})["db.query.parameter.records"])
        for span in records_spans
    )


def _assert_span_tree(exporter: InMemorySpanExporter, first_id: Any) -> None:
    """Assert the captured Neo4j span tree and write its JSON artifact.

    The read count is asserted exactly; the write count is not, because the
    constraint and relation-type setup writes the store issues along the way
    make a bare write total backend-state dependent, so the transactional
    write is checked through its ``agrag.transactional`` attribute instead.
    """
    spans = list(exporter.get_finished_spans())
    by_name: dict[str, list[ReadableSpan]] = {}
    for span in spans:
        by_name.setdefault(span.name, []).append(span)

    assert len(by_name["agrag.graphdb.build_driver"]) == 1
    (upsert_nodes_span,) = by_name["agrag.graphdb.upsert_nodes"]
    assert (upsert_nodes_span.attributes or {})["agrag.written"] == 2
    (upsert_relations_span,) = by_name["agrag.graphdb.upsert_relations"]
    assert (upsert_relations_span.attributes or {})["agrag.written"] == 1
    (transaction_span,) = by_name["agrag.graphdb.transaction"]
    # One read span per store-level execute_read above: the id read, the
    # vector-parameter probe, and the post-transaction read.
    assert len(by_name["agrag.graphdb.execute_read"]) == 3
    assert by_name.get("agrag.graphdb.execute_write"), (
        "no execute_write span was captured"
    )

    transactional_writes = [
        span
        for span in by_name["agrag.graphdb.execute_write"]
        if (span.attributes or {}).get("agrag.transactional") is True
    ]
    assert len(transactional_writes) == 1
    assert (
        transactional_writes[0].parent is not None
        and transactional_writes[0].parent.span_id == transaction_span.context.span_id
    )

    for span in (
        *by_name["agrag.graphdb.execute_read"],
        *by_name["agrag.graphdb.execute_write"],
    ):
        query_text = (span.attributes or {}).get("db.query.text")
        assert isinstance(query_text, str) and query_text.strip()

    by_id_read = next(
        span
        for span in by_name["agrag.graphdb.execute_read"]
        if (span.attributes or {}).get("db.query.parameter.id") == str(first_id)
    )
    assert by_id_read.name == "agrag.graphdb.execute_read"

    _assert_query_parameters_never_carry_vectors(spans)

    _write_span_tree(_span_tree_path(), spans)


@pytest.mark.skipif(neo4j_missing, reason="neo4j extra not installed")
class TestNeo4jTracing:
    """Traced graph-store calls export query text without embedding vectors."""

    async def test_traced_calls_export_queries_without_vectors(self) -> None:
        """Writes, a read, and a transaction export the expected span tree."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("agrag-test")
        # A unique label per run keeps this test isolated from other runs
        # sharing the same long-lived local Neo4j instance, matching the
        # unique-collection-name pattern tests/integration/vectordb/ uses.
        label = validate_identifier(f"Trace_{uuid4().hex[:8]}")
        store = Neo4jGraphStore(tracer=tracer)
        await store.connect()
        try:
            first_id = uuid4()
            second_id = uuid4()
            node_result = await store.upsert_nodes(
                label,
                [
                    NodeRecord(
                        id=first_id,
                        labels=[label],
                        properties={
                            "text": "sepsis protocol",
                            "embedding": [7.1, 7.2, 7.3, 7.4],
                        },
                    ),
                    NodeRecord(
                        id=second_id,
                        labels=[label],
                        properties={
                            "text": "flu guide",
                            "embedding": [8.1, 8.2, 8.3, 8.4],
                        },
                    ),
                ],
            )
            assert node_result.written == 2
            relation_result = await store.upsert_relations(
                [
                    RelationRecord(
                        id=uuid4(),
                        type="RELATES",
                        start_id=first_id,
                        end_id=second_id,
                        properties={"weight": 1.0},
                    )
                ]
            )
            assert relation_result.written == 1
            rows = await store.execute_read(
                f"MATCH (n:{label} {{id: $id}}) RETURN n.text AS text",
                {"id": str(first_id)},
            )
            assert [row["text"] for row in rows] == ["sepsis protocol"]
            probe = await store.execute_read(
                "RETURN $text AS text",
                {"text": "sepsis protocol", "embedding": [0.1, 0.2, 0.3]},
            )
            assert [row["text"] for row in probe] == ["sepsis protocol"]
            transacted_id = uuid4()
            async with store.transaction() as tx:
                await tx.execute_write(
                    f"CREATE (n:{label} {{id: $id, text: $text}})",
                    {"id": str(transacted_id), "text": "transactional node"},
                )
            transacted = await store.execute_read(
                f"MATCH (n:{label} {{id: $id}}) RETURN n.text AS text",
                {"id": str(transacted_id)},
            )
            assert [row["text"] for row in transacted] == ["transactional node"]

            _assert_span_tree(exporter, first_id)
        finally:
            await store.execute_write(f"MATCH (n:{label}) DETACH DELETE n")
            await store.close()
