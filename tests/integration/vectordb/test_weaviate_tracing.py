"""Integration proof that WeaviateVectorStore emits a connected span tree.

Runs a multi-batch ``upsert`` and a ``search`` against the Docker Compose
Weaviate instance from ``docker/docker-compose.ci.yml`` with a real SDK
``TracerProvider``/``InMemorySpanExporter`` passed to the store's
constructor. Hybrid search tracing stays out of scope here: the plan
covers ``hybrid_search`` spans for Qdrant and Milvus only, even though
this store implements ``hybrid_search`` (covered functionally by
``test_weaviate.py``). The captured span tree goes to a JSON artifact
for hand inspection.
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
from opentelemetry.trace import StatusCode, Tracer

from agrag.common.data_models.vector_record import Distance, VectorRecord
from agrag.vectordb.settings import WeaviateSettings
from agrag.vectordb.weaviate import WeaviateVectorStore


weaviate_missing = importlib.util.find_spec("weaviate") is None

VECTOR_DIM = 4


def _span_tree_path() -> Path:
    """Return the artifact path for the captured span tree."""
    root = Path(__file__).resolve().parents[3]
    directory = root / "reports" / "vectordb"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "weaviate_tracing.json"


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


@pytest.mark.skipif(weaviate_missing, reason="weaviate-client extra not installed")
class TestWeaviateVectorStoreTracing:
    """Traced calls against a real Weaviate instance emit the expected spans."""

    def _store(self, tracer: Tracer) -> WeaviateVectorStore:
        """Build a traced store pointed at the local Docker Compose instance."""
        return WeaviateVectorStore(
            settings=WeaviateSettings(mode="custom", url="http://localhost:8080"),
            tracer=tracer,
        )

    async def test_traced_upsert_and_search_emit_expected_spans(self) -> None:
        """Multi-batch upsert nests batch spans; search emits one span."""
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("agrag-test")
        store = self._store(tracer)
        try:
            name = f"Chunks_{uuid4().hex[:8]}"
            await store.ensure_collection(
                name, dimensions=VECTOR_DIM, distance=Distance.COSINE
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
            assert len(by_name.get("agrag.vectordb.upsert", [])) == 1
            (outer,) = by_name["agrag.vectordb.upsert"]
            assert (outer.attributes or {}).get("db.collection.name") == name
            assert (outer.attributes or {}).get("agrag.record_count") == 3
            batches = by_name.get("agrag.vectordb.upsert_batch", [])
            assert len(batches) == 3
            for batch in batches:
                assert batch.parent is not None
                assert batch.parent.span_id == outer.context.span_id
                assert (batch.attributes or {}).get("db.system.name") == "weaviate"
                assert (batch.attributes or {}).get("db.collection.name") == name
                assert (batch.attributes or {}).get("agrag.batch_size") == 1

            hits = await store.search(name, [1.0, 0.0, 0.0, 0.0], limit=2)
            assert len(hits) >= 1
            assert hits[0].payload["text"] == "a"

            spans = list(exporter.get_finished_spans())
            by_name = _by_name(spans)
            assert len(by_name.get("agrag.vectordb.search", [])) == 1
            (search_span,) = by_name["agrag.vectordb.search"]
            assert (search_span.attributes or {}).get("db.system.name") == "weaviate"
            assert (search_span.attributes or {}).get("db.collection.name") == name
            assert (search_span.attributes or {}).get("agrag.limit") == 2

            for span in spans:
                assert span.status.status_code is not StatusCode.ERROR

            _write_span_tree(_span_tree_path(), spans)
            await store.delete_collection(name)
        finally:
            await store.close()
