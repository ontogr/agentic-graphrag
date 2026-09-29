"""Integration proof that MilvusVectorStore emits a connected span tree.

Runs a multi-batch ``upsert``, a ``search``, and a ``hybrid_search``
against the Docker Compose Milvus instance from
``docker/docker-compose.ci.yml`` with a real SDK ``TracerProvider``/
``InMemorySpanExporter`` passed to the store's constructor. The captured
span tree goes to a JSON artifact for hand inspection.
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
from opentelemetry.trace import StatusCode

from agrag.common.data_models.vector_record import Distance, VectorRecord
from agrag.vectordb import build_vector_store


milvus_missing = importlib.util.find_spec("pymilvus") is None

VECTOR_DIM = 4


def _span_tree_path() -> Path:
    """Return the artifact path for the captured span tree."""
    root = Path(__file__).resolve().parents[3]
    directory = root / "reports" / "vectordb"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "milvus_tracing.json"


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


def _by_name(spans: list[ReadableSpan]) -> dict[str, list[ReadableSpan]]:
    """Group spans by name."""
    grouped: dict[str, list[ReadableSpan]] = {}
    for span in spans:
        grouped.setdefault(span.name, []).append(span)
    return grouped


def _assert_batched_upsert_spans(
    by_name: dict[str, list[ReadableSpan]], *, collection: str, backend: str
) -> None:
    """Assert one outer upsert span over N nested batch spans.

    Three records written at ``batch_size=1`` must produce exactly one
    ``agrag.vectordb.upsert`` span and one ``upsert_batch`` span per
    record, each parented to that outer span.
    """
    assert len(by_name.get("agrag.vectordb.upsert", [])) == 1
    (outer,) = by_name["agrag.vectordb.upsert"]
    assert (outer.attributes or {}).get("db.collection.name") == collection
    assert (outer.attributes or {}).get("agrag.record_count") == 3
    batches = by_name.get("agrag.vectordb.upsert_batch", [])
    assert len(batches) == 3
    for batch in batches:
        assert batch.parent is not None
        assert batch.parent.span_id == outer.context.span_id
        assert (batch.attributes or {}).get("db.system.name") == backend
        assert (batch.attributes or {}).get("db.collection.name") == collection
        assert (batch.attributes or {}).get("agrag.batch_size") == 1


async def _exercise_hybrid_search(
    store: Any, exporter: InMemorySpanExporter, hybrid_name: str
) -> None:
    """Upsert into a hybrid collection, search it, and assert its spans.

    Milvus's native ``hybrid_search`` is a single call, so it emits one
    ``CLIENT`` span under no outer wrapper.
    """
    hybrid_records = [
        VectorRecord(
            id=uuid4(),
            vector=[1.0, 0.0, 0.0, 0.0],
            payload={"text": "sepsis protocol"},
        ),
        VectorRecord(
            id=uuid4(),
            vector=[0.0, 1.0, 0.0, 0.0],
            payload={"text": "ventilator setup"},
        ),
    ]
    await store.upsert(hybrid_name, hybrid_records)
    hybrid_hits = await store.hybrid_search(
        hybrid_name, [1.0, 0.0, 0.0, 0.0], "sepsis protocol", limit=2
    )
    assert len(hybrid_hits) >= 1
    assert hybrid_hits[0].payload["text"] == "sepsis protocol"

    by_name = _by_name(list(exporter.get_finished_spans()))
    hybrid_spans = [
        span
        for span in by_name.get("agrag.vectordb.hybrid_search", [])
        if (span.attributes or {}).get("db.collection.name") == hybrid_name
    ]
    assert len(hybrid_spans) == 1
    (hybrid_span,) = hybrid_spans
    assert (hybrid_span.attributes or {}).get("db.system.name") == "milvus"
    assert (hybrid_span.attributes or {}).get("agrag.limit") == 2


@pytest.mark.skipif(milvus_missing, reason="pymilvus extra not installed")
class TestMilvusVectorStoreTracing:
    """Traced calls against a real Milvus instance emit the expected spans."""

    async def test_traced_upsert_search_and_hybrid_emit_expected_spans(
        self,
    ) -> None:
        """Multi-batch upsert nests batch spans; search and hybrid do one."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("agrag-test")
        store = build_vector_store("milvus", tracer=tracer)
        try:
            name = f"chunks_{uuid4().hex[:8]}"
            hybrid_name = f"chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE
            )
            await store.ensure_collection(
                hybrid_name,
                dimensions=VECTOR_DIM,
                distance=Distance.COSINE,
                hybrid=True,
            )
            records = [
                VectorRecord(
                    id=uuid4(), vector=[1.0, 0.0, 0.0, 0.0], payload={"text": "a"}
                ),
                VectorRecord(
                    id=uuid4(), vector=[0.0, 1.0, 0.0, 0.0], payload={"text": "b"}
                ),
                VectorRecord(
                    id=uuid4(), vector=[0.0, 0.0, 1.0, 0.0], payload={"text": "c"}
                ),
            ]
            await store.upsert(name, records, batch_size=1)

            by_name = _by_name(list(exporter.get_finished_spans()))
            _assert_batched_upsert_spans(by_name, collection=name, backend="milvus")

            hits = await store.search(name, [1.0, 0.0, 0.0, 0.0], limit=2)
            assert len(hits) >= 1
            assert hits[0].payload["text"] == "a"

            by_name = _by_name(list(exporter.get_finished_spans()))
            assert len(by_name.get("agrag.vectordb.search", [])) == 1
            (search_span,) = by_name["agrag.vectordb.search"]
            assert (search_span.attributes or {}).get("db.system.name") == "milvus"
            assert (search_span.attributes or {}).get("db.collection.name") == name
            assert (search_span.attributes or {}).get("agrag.limit") == 2

            await _exercise_hybrid_search(store, exporter, hybrid_name)

            spans = list(exporter.get_finished_spans())
            for span in spans:
                assert span.status.status_code is not StatusCode.ERROR

            _write_span_tree(_span_tree_path(), spans)
            await store.delete_collection(name)
            await store.delete_collection(hybrid_name)
        finally:
            await store.close()
