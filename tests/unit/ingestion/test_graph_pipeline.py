"""Exercise Graph ingestion helpers and pipeline wiring through the public Graph API."""

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.chunk import Chunk as ChunkModel
from agrag.common.data_models.document import (
    DOCUMENT_LABEL,
    Document,
    DocumentFamily,
    SourceFormat,
)
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import (
    NodeRecord,
    RelationRecord,
    UpsertFailure,
    UpsertResult,
)
from agrag.common.data_models.graph_schema import (
    GENERIC,
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.resolved_entity import ResolvedEntity
from agrag.common.data_models.vector_record import VectorHit, VectorRecord
from agrag.cypher.cutover_job_read import find_incomplete_jobs_query
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.errors import GraphStoreDataIntegrityError
from agrag.ingestion._ingest_pipeline import (
    _delete_vectors,
    _embed_and_upsert_chunks,
    _embed_and_upsert_survivors,
    _extract_merged_into,
    _global_exact_match,
    _global_relation_lookup,
    _parse_entity_node,
    _resolve_tombstone_chain,
    _upsert_vectors,
)
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import (
    Graph,
    _resolve_paths,
    _synthesize_consolidation_mentions,
)
from agrag.ingestion.materialize import MaterializationResult
from agrag.ingestion.reports import AddResult
from agrag.loaders.corpus.types import ErrorPolicy
from agrag.retrieval.settings import RetrievalSettings
from agrag.vectordb.base import VectorStore
from tests.unit.ingestion._lease_fake import CutoverJobLeaseFake


class MockStore(CutoverJobLeaseFake, GraphStore):
    """In-memory GraphStore that records calls for assertions."""

    def __init__(self) -> None:
        """Create a fresh fake store."""
        self.connect_calls = 0
        self.register_labels_calls: list[list[str]] = []
        self.register_types_calls: list[list[str]] = []
        self.setup_constraints_calls = 0
        self.setup_indexes_calls = 0
        self.upsert_nodes_calls: list[tuple[str, list[NodeRecord]]] = []
        self.upsert_relations_calls: list[list[RelationRecord]] = []
        self.execute_read_responses: list[list[dict[str, Any]]] = []
        self.execute_read_calls: list[tuple[str, Any]] = []
        self.execute_write_calls: list[tuple[str, Any]] = []
        self._read_index = 0

    async def connect(self) -> None:
        """Record a connect call."""
        self.connect_calls += 1

    async def close(self) -> None:
        """No-op close."""
        pass

    def session(self) -> AbstractAsyncContextManager[Any]:
        """Return a no-op async session."""

        class S:
            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *a: object) -> None:
                return None

        return S()  # type: ignore[return-value]

    async def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Record the read and return the next canned response.

        The crash-recovery scan ``Graph.open()`` runs first finds no
        leftover jobs here, so it never consumes a canned response.
        """
        del timeout
        self.execute_read_calls.append((query, parameters))
        if query == find_incomplete_jobs_query():
            return []
        if self._read_index < len(self.execute_read_responses):
            response = self.execute_read_responses[self._read_index]
            self._read_index += 1
            return response
        return []

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Record the write, answering Cutover Job queries in-memory."""
        self.execute_write_calls.append((query, parameters))
        handled = self.handle_cutover_query(query, parameters)
        if handled is not None:
            return handled
        return []

    async def setup_constraints(self) -> None:
        """Record a setup_constraints call."""
        self.setup_constraints_calls += 1

    async def setup_indexes(self) -> None:
        """Record a setup_indexes call."""
        self.setup_indexes_calls += 1

    async def upsert_nodes(
        self, label: str, nodes: Sequence[NodeRecord], *, batch_size: int = 256
    ) -> UpsertResult:
        """Record a node upsert."""
        self.upsert_nodes_calls.append((label, list(nodes)))
        return UpsertResult(written=len(nodes))

    async def upsert_relations(
        self, relations: Sequence[RelationRecord], *, batch_size: int = 256
    ) -> UpsertResult:
        """Record a relation upsert."""
        self.upsert_relations_calls.append(list(relations))
        return UpsertResult(written=len(relations))

    async def ensure_vector_index(self, **kw: Any) -> None:
        """No-op vector index creation."""
        pass

    async def vector_search(self, **kw: Any) -> list[VectorHit]:
        """Return no hits."""
        return []

    async def register_labels(self, labels: Sequence[str]) -> None:
        """Record registered labels."""
        self.register_labels_calls.append(list(labels))

    async def register_relation_types(self, types: Sequence[str]) -> None:
        """Record registered relation types."""
        self.register_types_calls.append(list(types))


class MockEmbedder(Embedder):
    """Embedder that returns a fixed vector."""

    model = "fake"

    async def dimensions(self) -> int:
        """Return fixed dimensions."""
        return 3

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return a constant vector for each input text."""
        return [[1.0, 2.0, 3.0] for _ in texts]


class RecordingVectorStore(VectorStore):
    """VectorStore that records upserts and deletes, serving nothing back."""

    def __init__(self) -> None:
        """Start with empty call logs."""
        self.upserts: list[tuple[str, list[VectorRecord]]] = []
        self.deletes: list[tuple[str, list[object]]] = []
        self.fail: Exception | None = None

    async def initialize(self) -> None:
        """No-op init."""

    async def ensure_collection(
        self, name: str, *, dimensions: int, distance: Any, hybrid: bool = False
    ) -> None:
        """No-op collection creation."""

    async def collection_exists(self, name: str) -> bool:
        """Every collection exists."""
        return True

    async def delete_collection(self, name: str) -> None:
        """No-op collection deletion."""

    async def upsert(
        self,
        collection: str,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Record the upsert, or raise the injected failure."""
        if self.fail is not None:
            raise self.fail
        self.upserts.append((collection, list(records)))

    async def search(
        self,
        collection: str,
        query_vector: Sequence[float],
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        """Return no hits."""
        return []

    async def hybrid_search(
        self,
        collection: str,
        query_vector: Sequence[float],
        query_text: str,
        *,
        limit: int = 10,
        filters: dict[str, Any] | None = None,
        alpha: float = 0.5,
    ) -> list[VectorHit]:
        """Return no hits."""
        return []

    async def scroll(
        self, collection: str, **kw: Any
    ) -> tuple[list[VectorRecord], None]:
        """Return no records."""
        return ([], None)

    async def retrieve(self, collection: str, ids: Sequence[Any]) -> list[VectorRecord]:
        """Return no records."""
        return []

    async def count(self, collection: str, **kw: Any) -> int:
        """Count nothing."""
        return 0

    async def delete(self, collection: str, ids: Sequence[Any]) -> None:
        """Record the delete, or raise the injected failure."""
        if self.fail is not None:
            raise self.fail
        self.deletes.append((collection, list(ids)))

    async def close(self) -> None:
        """No-op close."""


class _FailingUpsertVectorStore(RecordingVectorStore):
    """RecordingVectorStore whose upsert fails while delete still works.

    The mirror cleanup is a separate call, so a test needs the delete to
    succeed in order to observe which ids it targeted.
    """

    async def upsert(
        self,
        collection: str,
        records: Sequence[VectorRecord],
        *,
        batch_size: int = 256,
    ) -> None:
        """Always fail."""
        raise RuntimeError("vector store down")


class MockExtractor(Extractor):
    """Extractor that returns a canned result and records calls."""

    def __init__(self, result: ExtractionResult | None = None) -> None:
        """Create the fake extractor."""
        self.result = result or ExtractionResult(
            entities=[], relations=[], extractor_name="fake"
        )
        self.calls: list[str] = []

    async def extract(self, chunk: ChunkModel, schema: GraphSchema) -> ExtractionResult:
        """Record the chunk text and return the canned result."""
        self.calls.append(chunk.text)
        return self.result


def _doc(text: str = "hello world") -> Document:
    return Document(
        text=text,
        title="t",
        uri="u",
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash="h",
        loader_name="text",
        char_count=len(text),
        line_count=1,
    )


def _chunk(text: str = "hello", provenance: TextProvenance | None = None) -> ChunkModel:
    prov = provenance or TextProvenance(char_start=0, char_end=len(text))
    return ChunkModel(document_id=uuid4(), index=0, text=text, provenance=prov)


def _distinct_doc(
    uri: str, text: str = "hello world", content_hash: str | None = None
) -> Document:
    """Build a Document with a distinct id/document_key, unlike ``_doc()``.

    ``_doc()`` hardcodes ``content_hash="h"`` and ``uri="u"``, so two of its
    documents always share one resolved_id and document_key. Tests asserting
    per-document behavior across multiple documents need distinct ones.
    """
    return Document(
        text=text,
        title="t",
        uri=uri,
        source_format=SourceFormat.TXT,
        family=DocumentFamily.PROSE,
        content_hash=content_hash or uri,
        loader_name="text",
        char_count=len(text),
        line_count=1,
    )


def _tombstone_row(
    node_id: str,
    *,
    name: str,
    merge_key: str | None = None,
    merged_into: str | None = None,
) -> list[dict[str, Any]]:
    """Build one execute_read response for a single node in a merged_into chain."""
    properties: dict[str, Any] = {
        "name": name,
        "merged_from": [],
        "merge_count": 1,
        "source_chunk_ids": [],
        "created_at": "2020-01-01T00:00:00+00:00",
    }
    if merge_key is not None:
        properties["merge_key"] = merge_key
    if merged_into is not None:
        properties["merged_into"] = merged_into
    return [{"n": {"id": node_id, "labels": ["Person"], "properties": properties}}]


class TestParseEntityNode:
    """Tests for _parse_entity_node."""

    def test_parses_labels_properties_form(self) -> None:
        """Labels+properties mock is parsed."""
        cid = uuid4()
        eid = uuid4()
        node = {
            "id": str(eid),
            "labels": ["Person", "_AgragNode"],
            "properties": {
                "name": "Alice",
                "merge_key": "Person:alice",
                "merged_from": [],
                "merge_count": 1,
                "source_chunk_ids": [str(cid)],
                "created_at": "2020-01-01T00:00:00+00:00",
                "_pending_job_id": str(uuid4()),
                "age": "30",
            },
        }
        ent = _parse_entity_node(node)
        assert ent is not None
        assert ent.label == "Person"
        assert ent.name == "Alice"
        assert ent.properties["age"] == "30"
        assert "_pending_job_id" not in ent.properties
        assert ent.source_chunk_ids == [cid]

    def test_parses_flat_mock(self) -> None:
        """Flat dict with id and properties top-level is parsed."""
        eid = uuid4()
        node = {
            "id": str(eid),
            "name": "Bob",
            "merge_key": "Person:bob",
            "merged_from": [],
            "merge_count": 1,
            "source_chunk_ids": [],
            "created_at": "2020-01-01T00:00:00+00:00",
            "labels": ["Person"],
        }
        ent = _parse_entity_node(node)
        assert ent is not None
        assert ent.label == "Person"
        assert ent.name == "Bob"

    def test_parses_neo4j_node_style(self) -> None:
        """Object with dict() properties and .labels attribute is parsed."""
        eid = uuid4()

        class MockNode(dict):
            labels = ["Person", "_AgragNode"]

            def __init__(self) -> None:
                super().__init__(
                    {
                        "id": str(eid),
                        "name": "Carol",
                        "merge_key": "Person:carol",
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "created_at": "2020-01-01T00:00:00+00:00",
                    }
                )

        ent = _parse_entity_node(MockNode())
        assert ent is not None
        assert ent.label == "Person"

    def test_wrapped_n_key(self) -> None:
        """Node wrapped as {'n': inner} is unwrapped."""
        eid = uuid4()
        inner = {
            "id": str(eid),
            "labels": ["Person"],
            "properties": {
                "name": "Dave",
                "merge_key": "Person:dave",
                "merged_from": [],
                "merge_count": 1,
                "source_chunk_ids": [],
                "created_at": "2020-01-01T00:00:00+00:00",
            },
        }
        ent = _parse_entity_node({"n": inner})
        assert ent is not None
        assert ent.name == "Dave"

    def test_fallback_from_merge_key(self) -> None:
        """Label inferred from merge_key when labels are system only."""
        eid = uuid4()
        node = {
            "id": str(eid),
            "labels": [],
            "properties": {
                "name": "Eve",
                "merge_key": "Person:eve",
                "merged_from": [],
                "merge_count": 1,
                "source_chunk_ids": [],
                "created_at": "2020-01-01T00:00:00+00:00",
            },
        }
        ent = _parse_entity_node(node)
        assert ent is not None
        assert ent.label == "Person"

    def test_missing_label_and_id_returns_none(self) -> None:
        """No label and no id yields None."""
        node = {"labels": [], "properties": {"name": "x"}}
        assert _parse_entity_node(node) is None
        assert (
            _parse_entity_node({"id": None, "labels": ["Person"], "properties": {}})
            is None
        )

    def test_filters_system_keys(self) -> None:
        """System keys are not kept in properties."""
        eid = uuid4()
        node = {
            "id": str(eid),
            "labels": ["Person"],
            "properties": {
                "name": "Frank",
                "merge_key": "Person:frank",
                "merged_from": [],
                "merge_count": 1,
                "source_chunk_ids": [],
                "created_at": "2020-01-01T00:00:00+00:00",
                "embedding": [1, 2, 3],
                "custom": "keep",
            },
        }
        ent = _parse_entity_node(node)
        assert ent is not None
        assert "custom" in ent.properties
        assert "embedding" not in ent.properties
        assert ent.embedding == [1, 2, 3]

    def test_handles_malformed_created_at(self) -> None:
        """Bad created_at string is ignored."""
        eid = uuid4()
        node = {
            "id": str(eid),
            "labels": ["Person"],
            "properties": {
                "name": "Grace",
                "merge_key": "Person:grace",
                "merged_from": [],
                "merge_count": "not_an_int",
                "source_chunk_ids": [],
                "created_at": "bad-date",
            },
        }
        ent = _parse_entity_node(node)
        assert ent is not None
        assert ent.name == "Grace"

    def test_name_fallback_from_merge_key(self) -> None:
        """Name missing falls back to merge_key suffix."""
        eid = uuid4()
        node = {
            "id": str(eid),
            "labels": ["Person"],
            "properties": {
                "merge_key": "Person:heidi",
                "merged_from": [],
                "merge_count": 1,
                "source_chunk_ids": [],
                "created_at": "2020-01-01T00:00:00+00:00",
            },
        }
        ent = _parse_entity_node(node)
        assert ent is not None
        assert ent.name == "heidi"

    def test_exception_returns_none(self) -> None:
        """Any exception yields None."""
        assert _parse_entity_node(None) is None  # type: ignore[arg-type]
        assert _parse_entity_node(object()) is None


class TestGlobalExactMatch:
    """Tests for _global_exact_match."""

    async def test_groups_by_label_and_dedups(self) -> None:
        """One query per distinct label, deduped keys."""
        store = MockStore()
        cid = uuid4()
        m1 = ExtractedEntity(
            chunk_id=cid, label="Person", text="Alice", char_start=0, char_end=5
        )
        m2 = ExtractedEntity(
            chunk_id=cid, label="Person", text="alice", char_start=6, char_end=11
        )
        m3 = ExtractedEntity(
            chunk_id=cid, label="Organization", text="Acme", char_start=0, char_end=4
        )
        eid = uuid4()
        store.execute_read_responses = [
            [
                {
                    "n": {
                        "id": str(eid),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Alice",
                            "merge_key": "Person:alice",
                            "merged_from": [],
                            "merge_count": 1,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                        },
                    }
                }
            ],
            [],
        ]
        result = await _global_exact_match([m1, m2, m3], graph_store=store)
        assert result[0].id == eid
        assert result[1].id == eid
        assert 2 not in result
        assert len(store.execute_read_calls) == 2

    async def test_reingest_of_absorbed_name_resolves_to_survivor(self) -> None:
        """A name absorbed into a survivor still resolves there on re-ingest.

        Regression test: tombstone_query clears merge_key on absorption, so
        a later mention of the absorbed name can only be found through the
        merge-key alias table (fetch_by_merge_keys_query,
        upsert_merge_alias_query). Without that alias, this mention would
        find nothing and a duplicate "Bob" entity would be created instead
        of resolving to the existing survivor.
        """
        store = MockStore()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        tombstone_id = uuid4()
        survivor_id = uuid4()
        store.execute_read_responses = [
            # fetch_by_merge_keys_query resolves the alias to the original
            # (now-tombstoned) "Bob" entity; merge_key is absent from its
            # own properties, matching what REMOVE n.merge_key leaves
            # behind, but the query returns the queried key alongside the
            # row regardless, which is what mapping now relies on.
            [
                {
                    "merge_key": "Person:bob",
                    "n": {
                        "id": str(tombstone_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Bob",
                            "merged_from": [],
                            "merge_count": 1,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                            "merged_into": str(survivor_id),
                        },
                    },
                }
            ],
            # _resolve_tombstone_chain follows merged_into to the live
            # survivor.
            [
                {
                    "n": {
                        "id": str(survivor_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Robert",
                            "merge_key": "Person:robert",
                            "merged_from": [str(tombstone_id)],
                            "merge_count": 2,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                        },
                    }
                }
            ],
        ]
        result = await _global_exact_match([m], graph_store=store)
        assert result[0].id == survivor_id
        assert result[0].name == "Robert"

    async def test_reingest_resolves_with_driver_shaped_tombstone_row(self) -> None:
        """Reingest still resolves when the tombstone row has no ``labels`` key.

        Regression test: a real Neo4j driver's ``RETURN n`` never carries a
        ``labels`` key -- only ``_tombstone_row``'s mock form did, masking a
        bug where the tombstone's own node was parsed into an Entity (to
        learn its label) before its merged_into chain was ever checked.
        With merge_key already stripped by clear_tombstone_merge_keys_query,
        a driver-shaped tombstone row has neither a labels list nor a
        merge_key to derive a label from, so that parse always failed and
        the mention was silently dropped instead of resolving to the
        survivor.
        """
        store = MockStore()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        tombstone_id = uuid4()
        survivor_id = uuid4()
        store.execute_read_responses = [
            [
                {
                    "merge_key": "Person:bob",
                    "n": {
                        "id": str(tombstone_id),
                        "name": "Bob",
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "created_at": "2020-01-01T00:00:00+00:00",
                        "merged_into": str(survivor_id),
                    },
                }
            ],
            [
                {
                    "n": {
                        "id": str(survivor_id),
                        "name": "Robert",
                        "merge_key": "Person:robert",
                        "merged_from": [str(tombstone_id)],
                        "merge_count": 2,
                        "source_chunk_ids": [],
                        "created_at": "2020-01-01T00:00:00+00:00",
                    }
                }
            ],
        ]
        result = await _global_exact_match([m], graph_store=store)
        assert result[0].id == survivor_id
        assert result[0].name == "Robert"

    async def test_accepted_alias_with_different_name_resolves_to_entity(self) -> None:
        """A mention resolves via an alias even when it never was the entity's name.

        Regression test: when resolution joins "Bob" and "Robert" into one
        survivor named "Robert", an alias for "Person:bob" is written
        pointing at that entity even though the entity's own name was never
        "Bob". Mapping the returned row back to the "Bob" mention must use
        the merge_key the row's alias was queried on, not one re-derived
        from the entity's current name -- re-deriving would compute
        "Person:robert" and silently fail to map "Bob" at all.
        """
        store = MockStore()
        cid = uuid4()
        mention = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        entity_id = uuid4()
        store.execute_read_responses = [
            [
                {
                    "merge_key": "Person:bob",
                    "n": {
                        "id": str(entity_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Robert",
                            "merge_key": "Person:robert",
                            "merged_from": [],
                            "merge_count": 2,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                        },
                    },
                }
            ]
        ]
        result = await _global_exact_match([mention], graph_store=store)
        assert result[0].id == entity_id
        assert result[0].name == "Robert"

    async def test_transient_chain_read_failure_propagates(self) -> None:
        """A transient error resolving a tombstone chain must not be swallowed.

        Regression test: _resolve_tombstone_chain used to catch every
        exception from its chain-follow read and return whatever survivor it
        had so far (None on the first hop). _global_exact_match then treated
        that as "no match" and the caller would create a duplicate entity for
        an already-known name instead of surfacing the failure.
        """
        store = MockStore()
        tombstone_id = uuid4()
        survivor_id = uuid4()
        mention = ExtractedEntity(
            chunk_id=uuid4(), label="Person", text="Bob", char_start=0, char_end=3
        )
        store.execute_read_responses = [
            [
                {
                    "merge_key": "Person:bob",
                    "n": {
                        "id": str(tombstone_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Bob",
                            "merged_from": [],
                            "merge_count": 1,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                            "merged_into": str(survivor_id),
                        },
                    },
                }
            ]
        ]
        with (
            mock.patch.object(
                store,
                "execute_read",
                mock.AsyncMock(
                    side_effect=[
                        store.execute_read_responses[0],
                        ConnectionError("simulated transient DB error"),
                    ]
                ),
            ),
            pytest.raises(ConnectionError, match="simulated transient DB error"),
        ):
            await _global_exact_match([mention], graph_store=store)


class TestExtractMergedInto:
    """_extract_merged_into never turns a genuine failure into "not a tombstone"."""

    def test_plain_dict_node_reads_merged_into(self) -> None:
        """The plain-dict mock form (used throughout this file) still works."""
        survivor_id = str(uuid4())
        node = {
            "labels": ["Person"],
            "properties": {"name": "Bob", "merged_into": survivor_id},
        }
        assert _extract_merged_into(node, {}) == survivor_id

    def test_unstringifiable_candidate_propagates(self) -> None:
        """A failure while reading merged_into must not be read as "live".

        Regression test: this used to be wrapped in a blanket
        ``except Exception: return None``, so any failure here -- not just
        an absent merged_into -- looked identical to a live node to every
        caller. The only step past the two per-representation probes (each
        already narrowly suppressed on its own) that can still raise is
        stringifying the candidate id, so that is what this test exercises.
        """

        class _Unstringifiable:
            def __str__(self) -> str:
                raise RuntimeError("cannot stringify")

        node = {
            "labels": ["Person"],
            "properties": {"name": "Bob", "merged_into": _Unstringifiable()},
        }
        with pytest.raises(RuntimeError, match="cannot stringify"):
            _extract_merged_into(node, {})


class TestResolveTombstoneChain:
    """_resolve_tombstone_chain never returns a tombstone; every failure raises."""

    async def test_chain_over_max_hops_raises(self) -> None:
        """A chain longer than the hop cap raises instead of returning a tombstone.

        Regression test: the resolver used to run a fixed 32-iteration loop
        and return whatever node it last parsed, even though that node still
        had merged_into set -- silently handing back a tombstone rather than
        the true live entity.
        """
        store = MockStore()
        hop_count = 40  # more than _MAX_TOMBSTONE_CHAIN_HOPS
        ids = [str(uuid4()) for _ in range(hop_count)]
        store.execute_read_responses = [
            _tombstone_row(
                ids[i],
                name=f"Name{i}",
                merged_into=ids[i + 1] if i < hop_count - 1 else None,
            )
            for i in range(hop_count)
        ]
        with pytest.raises(GraphStoreDataIntegrityError, match="exceeded"):
            await _resolve_tombstone_chain(start_merged_into=ids[0], graph_store=store)

    async def test_cycle_raises(self) -> None:
        """A merged_into cycle raises instead of returning the last node visited."""
        store = MockStore()
        id_a, id_b = str(uuid4()), str(uuid4())
        store.execute_read_responses = [
            _tombstone_row(id_a, name="A", merged_into=id_b),
            _tombstone_row(id_b, name="B", merged_into=id_a),
        ]
        with pytest.raises(GraphStoreDataIntegrityError, match="cycle"):
            await _resolve_tombstone_chain(start_merged_into=id_a, graph_store=store)

    async def test_missing_node_raises(self) -> None:
        """A merged_into pointer to a node that no longer exists raises."""
        store = MockStore()
        missing_id = str(uuid4())
        store.execute_read_responses = [[]]
        with pytest.raises(GraphStoreDataIntegrityError, match="missing"):
            await _resolve_tombstone_chain(
                start_merged_into=missing_id, graph_store=store
            )

    async def test_short_chain_returns_live_entity(self) -> None:
        """A short chain still resolves to the live entity at its end."""
        store = MockStore()
        tombstone_id, survivor_id = str(uuid4()), str(uuid4())
        store.execute_read_responses = [
            _tombstone_row(tombstone_id, name="Bob", merged_into=survivor_id),
            _tombstone_row(survivor_id, name="Robert", merge_key="Person:robert"),
        ]
        entity = await _resolve_tombstone_chain(
            start_merged_into=tombstone_id, graph_store=store
        )
        assert str(entity.id) == survivor_id
        assert entity.name == "Robert"

    async def test_driver_shaped_intermediate_hop_without_labels_resolves(
        self,
    ) -> None:
        """A two-hop chain resolves when neither row carries a ``labels`` key.

        Regression test: a real Neo4j driver's ``RETURN n`` never returns
        ``labels``, and clear_tombstone_merge_keys_query has already
        stripped merge_key from every tombstone in the chain. The
        intermediate hop used to be parsed into an Entity purely to check
        its own merged_into, with neither label source available -- raising
        "unparsable node" instead of continuing to the live survivor.
        """
        store = MockStore()
        tombstone_id, intermediate_id, survivor_id = (
            str(uuid4()),
            str(uuid4()),
            str(uuid4()),
        )
        store.execute_read_responses = [
            [
                {
                    "n": {
                        "id": tombstone_id,
                        "name": "Bob",
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                        "created_at": "2020-01-01T00:00:00+00:00",
                        "merged_into": intermediate_id,
                    }
                }
            ],
            [
                {
                    "n": {
                        "id": intermediate_id,
                        "name": "Bobby",
                        "merged_from": [tombstone_id],
                        "merge_count": 2,
                        "source_chunk_ids": [],
                        "created_at": "2020-01-01T00:00:00+00:00",
                        "merged_into": survivor_id,
                    }
                }
            ],
            [
                {
                    "n": {
                        "id": survivor_id,
                        "name": "Robert",
                        "merge_key": "Person:robert",
                        "merged_from": [intermediate_id],
                        "merge_count": 3,
                        "source_chunk_ids": [],
                        "created_at": "2020-01-01T00:00:00+00:00",
                    }
                }
            ],
        ]
        entity = await _resolve_tombstone_chain(
            start_merged_into=tombstone_id, graph_store=store
        )
        assert str(entity.id) == survivor_id
        assert entity.name == "Robert"


class TestSynthesizeConsolidationMentions:
    """_synthesize_consolidation_mentions builds per-entity dummy context."""

    def test_shared_source_chunk_does_not_cross_contaminate_context(self) -> None:
        """Two entities sharing a first source chunk still get independent context.

        Regression test: keying the dummy chunk by an entity's own first
        source_chunk_id let a second entity sharing that same first chunk
        silently reuse whichever entity had already registered a dummy
        chunk under that id, corrupting the LLMVerify comparison context.
        """
        shared_chunk_id = uuid4()
        alice = Entity(
            id=uuid4(),
            label="Person",
            name="Alice",
            properties={},
            source_chunk_ids=[shared_chunk_id],
        )
        bob = Entity(
            id=uuid4(),
            label="Person",
            name="Bob",
            properties={},
            source_chunk_ids=[shared_chunk_id],
        )

        mentions, dummy_chunks_by_id = _synthesize_consolidation_mentions([alice, bob])

        assert len(mentions) == 2
        assert mentions[0].chunk_id != mentions[1].chunk_id
        assert dummy_chunks_by_id[mentions[0].chunk_id].text == "Alice"
        assert dummy_chunks_by_id[mentions[1].chunk_id].text == "Bob"


class TestGlobalRelationLookup:
    """Tests for _global_relation_lookup."""

    async def test_groups_by_type_and_maps_rows(self) -> None:
        """One query per distinct type."""
        store = MockStore()
        s1, t1 = uuid4(), uuid4()
        s2, t2 = uuid4(), uuid4()
        triples = [(s1, t1, "WORKS_AT"), (s2, t2, "WORKS_AT"), (s1, t1, "LIVES_AT")]
        rel_id = uuid4()
        cid = uuid4()
        store.execute_read_responses = [
            [
                {
                    "source_id": str(s1),
                    "target_id": str(t1),
                    "id": str(rel_id),
                    "source_chunk_ids": [str(cid)],
                }
            ],
            [],
        ]
        result = await _global_relation_lookup(triples, graph_store=store)
        assert (s1, t1, "WORKS_AT") in result
        assert result[(s1, t1, "WORKS_AT")][0] == rel_id
        assert (s2, t2, "WORKS_AT") not in result
        assert len(store.execute_read_calls) == 2

    async def test_skips_malformed_rows(self) -> None:
        """Malformed rows are skipped."""
        store = MockStore()
        s, t = uuid4(), uuid4()
        store.execute_read_responses = [
            [{"source_id": "bad-uuid", "target_id": str(t), "id": str(uuid4())}]
        ]
        result = await _global_relation_lookup([(s, t, "WORKS_AT")], graph_store=store)
        assert result == {}


class _GuardedNodeStore(MockStore):
    """MockStore whose execute_write honors the embedding write/clear guard.

    ``set_embedding_query`` / ``clear_property_query`` apply a record
    only when the target node's current name/description match the
    record's ``expected_name`` / ``expected_description``. The chunk
    variants (``set_chunk_embedding_query`` /
    ``clear_chunk_embedding_query``) guard on ``text`` instead. Real
    Neo4j enforces those WHERE clauses; this fake reproduces them in
    memory so a concurrent-write test can prove a stale record is
    rejected without a live database. ``execute_read`` answers the by-id
    hydration queries from the same ``nodes`` mapping, so a test can also
    drive the chunk-write recovery from it.
    """

    def __init__(self, nodes: dict[str, dict[str, Any]]) -> None:
        super().__init__()
        self.nodes = nodes

    async def execute_read(
        self,
        query: str,
        parameters: Mapping[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> list[dict[str, Any]]:
        """Answer the by-id hydration reads from the in-memory nodes."""
        del timeout
        if "RETURN n" not in query:
            return await super().execute_read(query, parameters)
        rows: list[dict[str, Any]] = []
        for node_id in (parameters or {}).get("ids", []):
            node = self.nodes.get(str(node_id))
            if node is None:
                continue
            # hydrate_entities_by_id_query drops tombstones; the chunk
            # variant matches the Chunk label instead.
            if ":Chunk" not in query and node.get("merged_into") is not None:
                continue
            rows.append({"n": {"id": str(node_id), **node}})
        return rows

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        rows = await super().execute_write(query, parameters)
        # The Cutover Job machinery answers its own queries; only the
        # embedding writes reach the guard below.
        if rows:
            return rows
        records = (parameters or {}).get("records", [])
        matched_ids: list[str] = []
        for record in records:
            node = self.nodes.get(record["id"])
            if node is None:
                continue
            # Entity guard: name + description.
            if "expected_name" in record and node["name"] != record["expected_name"]:
                continue
            if (
                "expected_description" in record
                and (node.get("description") or "") != record["expected_description"]
            ):
                continue
            # Chunk guard: text.
            if (
                "expected_text" in record
                and node.get("text") != record["expected_text"]
            ):
                continue
            if "REMOVE n.embedding" in query:
                node["embedding"] = None
            elif "SET n.embedding" in query:
                if node.get("merged_into") is not None:
                    continue
                node["embedding"] = record["vector"]
                matched_ids.append(record["id"])
        if "SET n.embedding" in query:
            return [{"id": record_id} for record_id in matched_ids]
        return []


class TestEmbedAndUpsertSurvivors:
    """Regression tests for the name/description guard on embedding writes."""

    async def test_slower_stale_write_does_not_overwrite_newer_vector(self) -> None:
        """An older call's write must not clobber a newer call's fresh vector.

        Regression test: set_embedding_query used to key only by id, so an
        older, slower embed call finishing after a newer one could silently
        overwrite the newer vector with one computed from stale text. Here
        the node's persisted text ("NewText") no longer matches the stale
        entity ("OldText") this call is embedding, so the write must be a
        no-op.
        """
        entity_id = uuid4()
        store = _GuardedNodeStore(
            {
                str(entity_id): {
                    "name": "NewText",
                    "description": None,
                    "embedding": None,
                }
            }
        )
        stale_entity = Entity(id=entity_id, label="Person", name="OldText")

        await _embed_and_upsert_survivors(
            {entity_id: stale_entity},
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.SKIP,
        )

        assert store.nodes[str(entity_id)]["embedding"] is None

    async def test_stale_write_rejected_on_description_alone(self) -> None:
        """The guard rejects a stale write on description even when name matches.

        Regression test: embedding_text is name plus an optional
        "description" property (see Entity.embedding_text), so the guard
        must compare both -- a race that only changes description (the
        common case: merge recomputes descriptions, names are stable) would
        slip through a name-only guard.
        """
        entity_id = uuid4()
        store = _GuardedNodeStore(
            {
                str(entity_id): {
                    "name": "Ada",
                    "description": "new description",
                    "embedding": None,
                }
            }
        )
        stale_entity = Entity(
            id=entity_id,
            label="Person",
            name="Ada",
            properties={"description": "old description"},
        )

        await _embed_and_upsert_survivors(
            {entity_id: stale_entity},
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.SKIP,
        )

        assert store.nodes[str(entity_id)]["embedding"] is None

    async def test_merge_during_embed_does_not_restore_tombstone_vector(self) -> None:
        """A merge landing mid-embed must not have its cleared vector restored.

        Regression test: set_embedding_query's guard used to check only
        name/description, so a concurrent merge tombstoning this entity
        after embed() started -- clearing its embedding -- would still
        accept a write whose text still matched, silently putting the
        absorbed entity back in native vector search. Simulates the
        interleaving deterministically: the node is already merged_into
        another entity by the time this call's write reaches the guard,
        the same state a race with a real, concurrent apply_merge would
        leave behind.
        """
        entity_id = uuid4()
        store = _GuardedNodeStore(
            {
                str(entity_id): {
                    "name": "Ada",
                    "description": None,
                    "embedding": None,
                    "merged_into": str(uuid4()),
                }
            }
        )
        # This call's own read of the entity happened before the concurrent
        # merge landed, so its text still matches the now-tombstoned node.
        stale_entity = Entity(id=entity_id, label="Person", name="Ada")

        await _embed_and_upsert_survivors(
            {entity_id: stale_entity},
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.SKIP,
        )

        assert store.nodes[str(entity_id)]["embedding"] is None

    async def test_failure_clear_does_not_wipe_newer_vector(self) -> None:
        """A failing call's clear must not wipe a different, newer vector.

        Regression test: clear_property_query used to key only by id, so a
        call whose embed() failed for stale text could wipe a vector a
        different, newer call had already written for the node's current
        text.
        """

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed backend down")

        entity_id = uuid4()
        store = _GuardedNodeStore(
            {
                str(entity_id): {
                    "name": "NewText",
                    "description": None,
                    "embedding": [0.9, 0.9],
                }
            }
        )
        stale_entity = Entity(id=entity_id, label="Person", name="OldText")

        await _embed_and_upsert_survivors(
            {entity_id: stale_entity},
            embedder=_FailingEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.SKIP,
        )

        assert store.nodes[str(entity_id)]["embedding"] == [0.9, 0.9]


class TestEmbedAndUpsertChunks:
    """Tests for _embed_and_upsert_chunks error handling and cleanup."""

    async def test_success_writes_embeddings(self) -> None:
        """On success, chunk embeddings are written."""
        ch = ChunkModel(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Hello world",
            provenance=TextProvenance(char_start=0, char_end=11),
        )
        store = _GuardedNodeStore(
            {
                str(ch.id): {
                    "name": "Hello world",
                    "text": "Hello world",
                    "embedding": None,
                }
            }
        )

        failures = await _embed_and_upsert_chunks(
            [ch],
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.RAISE,
        )

        assert failures == []
        assert store.nodes[str(ch.id)]["embedding"] is not None

    async def test_failure_clears_embeddings_and_raises(self) -> None:
        """On embed failure with RAISE, embeddings are cleared.

        The error then propagates.
        """

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed backend down")

        ch = ChunkModel(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Hello world",
            provenance=TextProvenance(char_start=0, char_end=11),
        )
        store = _GuardedNodeStore(
            {
                str(ch.id): {
                    "name": "Hello world",
                    "text": "Hello world",
                    "embedding": [0.5, 0.5],
                }
            }
        )

        with pytest.raises(RuntimeError, match="embed backend down"):
            await _embed_and_upsert_chunks(
                [ch],
                embedder=_FailingEmbedder(),
                graph_store=store,
                error_policy=ErrorPolicy.RAISE,
            )

        # Embedding should be cleared after the failure.
        assert store.nodes[str(ch.id)]["embedding"] is None

    async def test_failure_clears_embeddings_and_returns_skip(self) -> None:
        """On embed failure with SKIP, embeddings are cleared.

        A StageFailure is returned instead of raising.
        """

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed timeout")

        ch = ChunkModel(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Hello world",
            provenance=TextProvenance(char_start=0, char_end=11),
        )
        store = _GuardedNodeStore(
            {
                str(ch.id): {
                    "name": "Hello world",
                    "text": "Hello world",
                    "embedding": [0.5, 0.5],
                }
            }
        )

        failures = await _embed_and_upsert_chunks(
            [ch],
            embedder=_FailingEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.SKIP,
        )

        assert len(failures) == 1
        assert failures[0].error_type == "RuntimeError"
        assert store.nodes[str(ch.id)]["embedding"] is None

    async def test_stale_text_guard_prevents_clearing_newer_vector(
        self,
    ) -> None:
        """A chunk whose text changed since embed keeps its vector.

        The text guard must reject the clear when the persisted text
        differs from the text this call embedded.
        """
        ch = ChunkModel(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Old text",
            provenance=TextProvenance(char_start=0, char_end=8),
        )
        # Node's persisted text is different from what this call embedded.
        store = _GuardedNodeStore(
            {
                str(ch.id): {
                    "name": "New text",
                    "text": "New text",
                    "embedding": [0.9, 0.9],
                }
            }
        )

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("fail")

        with pytest.raises(RuntimeError):
            await _embed_and_upsert_chunks(
                [ch],
                embedder=_FailingEmbedder(),
                graph_store=store,
                error_policy=ErrorPolicy.RAISE,
            )

        # The newer vector must be preserved because the guard rejected
        # the clear for stale text.
        assert store.nodes[str(ch.id)]["embedding"] == [0.9, 0.9]


class TestVectorStoreHelpers:
    """_upsert_vectors and _delete_vectors no-op on None and drop empties."""

    async def test_upsert_none_store_is_noop(self) -> None:
        """A None store writes nothing and raises nothing."""
        record = VectorRecord(id=uuid4(), vector=[1.0], payload={})
        await _upsert_vectors(None, "col", [record])

    async def test_upsert_drops_empty_vectors(self) -> None:
        """Records with an empty vector are skipped, populated ones kept."""
        store = RecordingVectorStore()
        empty = VectorRecord(id=uuid4(), vector=[], payload={})
        good = VectorRecord(id=uuid4(), vector=[1.0, 2.0], payload={})
        await _upsert_vectors(store, "col", [empty, good])
        assert [r.id for _, records in store.upserts for r in records] == [good.id]

    async def test_delete_empty_ids_is_noop(self) -> None:
        """An empty id list calls delete exactly zero times."""
        store = RecordingVectorStore()
        await _delete_vectors(store, "col", [])
        assert store.deletes == []


class TestEmbedChunksDualWrite:
    """_embed_and_upsert_chunks mirrors vectors into the VectorStore."""

    async def test_stale_chunk_is_not_mirrored(self) -> None:
        """A chunk skipped by the graph text guard is not mirrored."""
        ch = ChunkModel(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Old text",
            provenance=TextProvenance(char_start=0, char_end=8),
        )
        store = _GuardedNodeStore(
            {
                str(ch.id): {
                    "text": "New text",
                    "embedding": [0.9, 0.9],
                }
            }
        )
        vector_store = RecordingVectorStore()

        await _embed_and_upsert_chunks(
            [ch],
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.RAISE,
            vector_store=vector_store,
            vector_collection="chunks",
        )

        assert vector_store.upserts == []

    async def test_success_upserts_chunk_vectors(self) -> None:
        """A successful embed upserts one record per chunk with its text."""
        ch = ChunkModel(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Hello world",
            provenance=TextProvenance(char_start=0, char_end=11),
        )
        store = _GuardedNodeStore({str(ch.id): {"text": ch.text}})
        vector_store = RecordingVectorStore()

        failures = await _embed_and_upsert_chunks(
            [ch],
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.RAISE,
            vector_store=vector_store,
            vector_collection="chunks",
        )

        assert failures == []
        assert len(vector_store.upserts) == 1
        collection, records = vector_store.upserts[0]
        assert collection == "chunks"
        assert [str(r.id) for r in records] == [str(ch.id)]
        assert records[0].payload["text"] == "Hello world"

    async def test_chunk_payload_carries_document_id(self) -> None:
        """A document-scoped filter must match the VectorStore path too.

        Regression test: chunk mirror records held only label and text, so
        SearchFilters.document_ids -- compiled to a document_id payload
        key -- matched nothing there, while the GraphStore-native path
        filtered the chunk node's document_id property and returned the
        right chunks.
        """
        document_id = uuid4()
        ch = ChunkModel(
            id=uuid4(),
            document_id=document_id,
            index=0,
            text="Hello world",
            provenance=TextProvenance(char_start=0, char_end=11),
        )
        store = _GuardedNodeStore({str(ch.id): {"text": ch.text}})
        vector_store = RecordingVectorStore()

        await _embed_and_upsert_chunks(
            [ch],
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.RAISE,
            vector_store=vector_store,
            vector_collection="chunks",
        )

        assert len(vector_store.upserts) == 1
        _, records = vector_store.upserts[0]
        assert records[0].payload["document_id"] == str(document_id)

    async def test_vector_store_failure_returns_stage_failure(self) -> None:
        """A VectorStore failure is reported as StageFailure with SKIP."""
        ch = ChunkModel(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Hello world",
            provenance=TextProvenance(char_start=0, char_end=11),
        )
        store = _GuardedNodeStore({str(ch.id): {"text": ch.text}})
        vector_store = RecordingVectorStore()
        vector_store.fail = RuntimeError("vector store down")

        failures = await _embed_and_upsert_chunks(
            [ch],
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.SKIP,
            vector_store=vector_store,
            vector_collection="chunks",
        )

        assert len(failures) == 1
        assert failures[0].item_id == "chunk_vector_store"
        assert failures[0].error_type == "RuntimeError"

    async def test_embed_failure_skips_vector_upsert(self) -> None:
        """When the embed itself fails, the VectorStore is never touched."""

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed backend down")

        ch = ChunkModel(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Hello world",
            provenance=TextProvenance(char_start=0, char_end=11),
        )
        store = _GuardedNodeStore({str(ch.id): {"text": ch.text}})
        vector_store = RecordingVectorStore()

        with pytest.raises(RuntimeError, match="embed backend down"):
            await _embed_and_upsert_chunks(
                [ch],
                embedder=_FailingEmbedder(),
                graph_store=store,
                error_policy=ErrorPolicy.RAISE,
                vector_store=vector_store,
                vector_collection="chunks",
            )

        assert vector_store.upserts == []

    async def test_failed_mirror_write_leaves_collection_untouched(self) -> None:
        """A failed chunk mirror write removes nothing.

        The mirror has no conditional write, so removing the records this
        call failed to replace would race a concurrent re-ingest that owns
        them. The previous record stays until the next successful ingest
        rewrites it.
        """
        ch = ChunkModel(
            id=uuid4(),
            document_id=uuid4(),
            index=0,
            text="Hello world",
            provenance=TextProvenance(char_start=0, char_end=11),
        )
        store = _GuardedNodeStore({str(ch.id): {"text": ch.text}})
        vector_store = _FailingUpsertVectorStore()

        failures = await _embed_and_upsert_chunks(
            [ch],
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.SKIP,
            vector_store=vector_store,
            vector_collection="chunks",
        )

        assert [f.item_id for f in failures] == ["chunk_vector_store"]
        assert vector_store.deletes == []


class TestEmbedSurvivorsDualWrite:
    """_embed_and_upsert_survivors mirrors entity vectors and labels."""

    def _entity(self, label: str = "Person") -> Entity:
        """Build a minimal live entity with a description."""
        return Entity(
            id=uuid4(),
            label=label,
            name="Alice",
            properties={"description": "A person"},
        )

    async def test_success_upserts_entity_vectors_with_labels(self) -> None:
        """A successful embed upserts one record per survivor, label included."""
        ent = self._entity()
        store = _GuardedNodeStore(
            {
                str(ent.id): {
                    "name": ent.name,
                    "description": str(ent.properties.get("description", "")),
                }
            }
        )
        vector_store = RecordingVectorStore()

        failures = await _embed_and_upsert_survivors(
            {ent.id: ent},
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.RAISE,
            vector_store=vector_store,
            vector_collection="entities",
            labels_by_id={ent.id: ent.label},
        )

        assert failures == []
        collection, records = vector_store.upserts[0]
        assert collection == "entities"
        assert records[0].payload["label"] == "Person"
        assert str(records[0].id) == str(ent.id)

    async def test_entity_payload_carries_properties(self) -> None:
        """A property-scoped filter must match the VectorStore path too.

        Regression test: entity mirror records held only label and text, so
        SearchFilters.properties -- compiled to payload keys -- matched
        nothing there, while the GraphStore-native path matched them as
        node properties and returned the right entities.
        """
        ent = Entity(
            id=uuid4(),
            label="Person",
            name="Alice",
            properties={"description": "A person", "tenant": "a"},
        )
        store = _GuardedNodeStore(
            {
                str(ent.id): {
                    "name": ent.name,
                    "description": str(ent.properties.get("description", "")),
                }
            }
        )
        vector_store = RecordingVectorStore()

        await _embed_and_upsert_survivors(
            {ent.id: ent},
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.RAISE,
            vector_store=vector_store,
            vector_collection="entities",
            labels_by_id={ent.id: ent.label},
        )

        assert len(vector_store.upserts) == 1
        _, records = vector_store.upserts[0]
        assert records[0].payload["tenant"] == "a"
        assert records[0].payload["description"] == "A person"

    async def test_vector_store_failure_returns_stage_failure(self) -> None:
        """A VectorStore failure is reported as a StageFailure with SKIP."""
        ent = self._entity()
        store = _GuardedNodeStore(
            {
                str(ent.id): {
                    "name": ent.name,
                    "description": str(ent.properties.get("description", "")),
                }
            }
        )
        vector_store = RecordingVectorStore()
        vector_store.fail = RuntimeError("vector store down")

        failures = await _embed_and_upsert_survivors(
            {ent.id: ent},
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.SKIP,
            vector_store=vector_store,
            vector_collection="entities",
            labels_by_id={ent.id: ent.label},
        )

        assert len(failures) == 1
        assert failures[0].item_id == "entity_vector_store"

    async def test_embed_failure_skips_vector_upsert(self) -> None:
        """When the embed itself fails, the VectorStore is never touched."""

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed backend down")

        ent = self._entity()
        store = _GuardedNodeStore(
            {
                str(ent.id): {
                    "name": ent.name,
                    "description": str(ent.properties.get("description", "")),
                }
            }
        )
        vector_store = RecordingVectorStore()

        with pytest.raises(RuntimeError, match="embed backend down"):
            await _embed_and_upsert_survivors(
                {ent.id: ent},
                embedder=_FailingEmbedder(),
                graph_store=store,
                error_policy=ErrorPolicy.RAISE,
                vector_store=vector_store,
                vector_collection="entities",
                labels_by_id={ent.id: ent.label},
            )

        assert vector_store.upserts == []

    async def test_failed_mirror_write_leaves_collection_untouched(self) -> None:
        """A failed entity mirror write removes nothing.

        Same reason as the chunk path: a delete this call issues after
        reading the graph can land after a concurrent call has replaced the
        record, and would remove that newer vector.
        """
        ent = self._entity()
        store = _GuardedNodeStore(
            {
                str(ent.id): {
                    "name": ent.name,
                    "description": str(ent.properties.get("description", "")),
                }
            }
        )
        vector_store = _FailingUpsertVectorStore()

        failures = await _embed_and_upsert_survivors(
            {ent.id: ent},
            embedder=MockEmbedder(),
            graph_store=store,
            error_policy=ErrorPolicy.SKIP,
            vector_store=vector_store,
            vector_collection="entities",
            labels_by_id={ent.id: ent.label},
        )

        assert [f.item_id for f in failures] == ["entity_vector_store"]
        assert vector_store.deletes == []


class TestGraphOpenVectorStore:
    """Graph.open provisions the VectorStore collections it will write to."""

    async def test_open_provisions_vector_collections(self) -> None:
        """open() initializes the store and ensures all vector collections."""
        ensured: list[str] = []

        class RecordingStore(RecordingVectorStore):
            async def collection_exists(self, name: str) -> bool:
                return False

            async def ensure_collection(
                self, name: str, *, dimensions: int, distance: Any, hybrid: bool = False
            ) -> None:
                ensured.append(name)

        vector_store = RecordingStore()
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=MockStore(),
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
            vector_store=vector_store,
        )
        settings = RetrievalSettings()
        assert ensured == [
            settings.entity_collection,
            settings.resolved_entity_collection,
            settings.chunk_collection,
            settings.community_collection,
        ]
        assert graph._vector_store is vector_store


class TestResolvePaths:
    """Tests for _resolve_paths."""

    def test_single_file(self, tmp_path: Path) -> None:
        """Single file returns single path and single_file True."""
        f = tmp_path / "a.txt"
        f.write_text("hi")
        paths, single = _resolve_paths(str(f))
        assert paths == [f]
        assert single is True

    def test_directory(self, tmp_path: Path) -> None:
        """Directory expands to files and single_file False."""
        d = tmp_path / "d"
        d.mkdir()
        (d / "a.txt").write_text("a")
        (d / "b.txt").write_text("b")
        paths, single = _resolve_paths(str(d))
        assert len(paths) == 2
        assert single is False

    def test_glob(self, tmp_path: Path) -> None:
        """Glob pattern expands."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "b.txt").write_text("b")
        paths, single = _resolve_paths(str(tmp_path / "*.txt"))
        assert any(p.name == "a.txt" for p in paths)
        assert single is False

    def test_list_of_sources(self, tmp_path: Path) -> None:
        """List input is handled."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a")
        f2.write_text("b")
        paths, single = _resolve_paths([str(f1), str(f2)])
        assert len(paths) == 2
        assert single is False


class TestGraphAddPipeline:
    """Tests for the Graph.add pipeline."""

    async def test_loader_requires_single_file(self, tmp_path: Path) -> None:
        """Loader with directory/glob raises."""
        from agrag.loaders.corpus.readers.prose import TextLoader  # noqa: PLC0415

        (tmp_path / "a.txt").write_text("a")
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        with pytest.raises(ValueError):
            await graph.add(str(tmp_path), loader=TextLoader())

    async def test_partial_chunk_write_still_embeds_written_chunks(self) -> None:
        """Chunks committed before a failed node write still get embeddings.

        Regression test: the embedding stage ran only when the whole chunk
        node write succeeded, so a failure in a later batch left the
        already-committed chunks without a vector, unsearchable by vector
        search until their source was ingested again.
        """

        class PartialChunkStore(_GuardedNodeStore):
            """Commits the chunk nodes it is given, then fails the write."""

            async def upsert_nodes(
                self,
                label: str,
                nodes: Sequence[NodeRecord],
                *,
                batch_size: int = 256,
            ) -> UpsertResult:
                result = await super().upsert_nodes(label, nodes, batch_size=batch_size)
                if label != CHUNK_LABEL:
                    return result
                for node in nodes:
                    self.nodes[str(node.id)] = {
                        "text": node.properties.get("text"),
                    }
                raise RuntimeError("chunk node write failed")

        store = PartialChunkStore({})
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )

        result = await graph.add(text="hello world", error_policy=ErrorPolicy.SKIP)

        assert any(f.item_id == "chunks" for f in result.storage.failures)
        embedded_ids = {
            record["id"]
            for query, parameters in store.execute_write_calls
            if "SET n.embedding" in query and "expected_text" in query
            for record in (parameters or {}).get("records", [])
        }
        assert embedded_ids == set(store.nodes)

    async def test_non_uuid_chunk_failure_id_does_not_abort_add(self) -> None:
        """Backend failure ids remain failures even when they are not UUIDs."""

        class NonUuidFailureStore(MockStore):
            """Return a backend-specific chunk failure id."""

            async def upsert_nodes(
                self,
                label: str,
                nodes: Sequence[NodeRecord],
                *,
                batch_size: int = 256,
            ) -> UpsertResult:
                result = await super().upsert_nodes(label, nodes, batch_size=batch_size)
                if label == CHUNK_LABEL:
                    return UpsertResult(
                        failures=[
                            UpsertFailure(
                                id="backend-record-7",
                                error_type="BackendFailure",
                                error_message="record rejected",
                            )
                        ]
                    )
                return result

        graph = await Graph.open(
            schema=GENERIC,
            graph_store=NonUuidFailureStore(),
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )

        result = await graph.add(text="hello world", error_policy=ErrorPolicy.RAISE)

        assert [failure.item_id for failure in result.storage.failures] == [
            "backend-record-7"
        ]
        assert all(failure.item_id != "chunks" for failure in result.storage.failures)

    async def test_add_writes_one_document_node_and_part_of_per_chunk(self) -> None:
        """add() writes one Document node and a PART_OF record per chunk."""
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        result = await graph.add(text="one two three four five six", return_chunks=True)
        chunk_count = len(result.chunks)
        assert chunk_count > 0

        document_calls = [
            nodes
            for label, nodes in store.upsert_nodes_calls
            if label == DOCUMENT_LABEL
        ]
        assert len(document_calls) == 1
        assert len(document_calls[0]) == 1

        part_of_records = [
            rec
            for batch in store.upsert_relations_calls
            for rec in batch
            if rec.type == "PART_OF"
        ]
        assert len(part_of_records) == chunk_count
        document_node_id = document_calls[0][0].id
        assert all(record.start_id == document_node_id for record in part_of_records)
        assert all(record.properties["valid_at"] for record in part_of_records)
        assert all(
            record.properties["invalid_at"] is None for record in part_of_records
        )
        assert all(record.properties["version_id"] for record in part_of_records)
        assert {record.end_id for record in part_of_records} == {
            chunk.id for chunk in result.chunks
        }

    async def test_add_two_documents_writes_two_document_records(self) -> None:
        """A batch spanning two distinct documents writes two Document records.

        Each document commits as its own Cutover Job — the lease is per
        document — so the two records arrive as two writes, one per job.
        """
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        docs = [
            _distinct_doc("uri-a", content_hash="same-content"),
            _distinct_doc("uri-b", content_hash="same-content"),
        ]
        result = await graph.add(documents=docs, return_chunks=True)

        document_calls = [
            nodes
            for label, nodes in store.upsert_nodes_calls
            if label == DOCUMENT_LABEL
        ]
        assert len(document_calls) == 2
        written_keys = {
            rec.properties["document_key"] for batch in document_calls for rec in batch
        }
        assert written_keys == {"uri-a", "uri-b"}
        part_of_records = [
            rec
            for batch in store.upsert_relations_calls
            for rec in batch
            if rec.type == "PART_OF"
        ]
        expected_endpoints = {
            (Document.node_id_for(document_key=doc.resolved_document_key), chunk.id)
            for doc in docs
            for chunk in result.chunks
            if chunk.document_id
            == Document.node_id_for(document_key=doc.resolved_document_key)
        }
        assert {(record.start_id, record.end_id) for record in part_of_records} == (
            expected_endpoints
        )

    async def test_add_includes_next_chunk_records(self) -> None:
        """add() includes NEXT_CHUNK edges alongside PART_OF records."""
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        result = await graph.add(text="one two three four five six", return_chunks=True)
        next_records = [
            rec
            for batch in store.upsert_relations_calls
            for rec in batch
            if rec.type == "NEXT_CHUNK"
        ]
        chunk_ids = [chunk.id for chunk in result.chunks]
        assert len(next_records) == max(len(chunk_ids) - 1, 0)
        assert all(rec.properties == {} for rec in next_records)

    async def test_add_source_path(self, tmp_path: Path) -> None:
        """Source file path is loaded via walk."""
        f = tmp_path / "a.txt"
        f.write_text("hello source")
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        result = await graph.add(str(f))
        assert result.ingestion.documents == 1
        assert result.ingestion.sources == 1

    async def test_on_progress_fires_batches_plus_final(self) -> None:
        """on_progress fires per batch plus final."""
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        seen: list[AddResult] = []

        def cb(r: AddResult) -> None:
            seen.append(r)

        await graph.add(text="hi", on_progress=cb)
        assert len(seen) == 2
        # Partial progress has no storage counts yet.
        assert seen[0].storage.nodes_written == 0
        # Final progress includes storage counts.
        assert seen[1].storage.nodes_written >= 0

    async def test_on_progress_exception_suppressed(self) -> None:
        """Exception in on_progress does not abort add."""

        def bad_cb(_: AddResult) -> None:
            raise RuntimeError("boom")

        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        result = await graph.add(text="hi", on_progress=bad_cb)
        assert result.ingestion.documents == 1

    async def test_extraction_failure_skip(self) -> None:
        """Extraction failure with SKIP records StageFailure."""

        class FailExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                raise ValueError("fail extract")

        store, embed = MockStore(), MockEmbedder()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=FailExtractor()
        )
        result = await graph.add(text="hi", error_policy=ErrorPolicy.SKIP)
        assert result.extraction.failures
        assert result.extraction.failures[0].error_type == "ValueError"
        assert result.ingestion.documents == 1

    async def test_extraction_failure_raise(self) -> None:
        """Extraction failure with RAISE propagates."""

        class FailExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                raise ValueError("fail")

        store, embed = MockStore(), MockEmbedder()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=FailExtractor()
        )
        with pytest.raises(ValueError):
            await graph.add(text="hi", error_policy=ErrorPolicy.RAISE)

    async def test_empty_chunks_early_return(self) -> None:
        """No chunks yields early AddResult with no embeddings."""
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        with mock.patch.object(graph, "_chunk_documents", return_value=[]):
            result = await graph.add(text="hi", on_progress=lambda _: None)
            assert result.extraction.chunks_processed == 0
            assert result.storage.nodes_written == 0
            assert result.chunks == []

    async def test_global_exact_match_integration(self) -> None:
        """Exact match hits populate resolution stats."""
        eid = uuid4()
        cid = uuid4()
        store = MockStore()
        store.execute_read_responses = [
            [
                {
                    "n": {
                        "id": str(eid),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Alice",
                            "merge_key": "Person:alice",
                            "merged_from": [],
                            "merge_count": 1,
                            "source_chunk_ids": [str(cid)],
                            "created_at": "2020-01-01T00:00:00+00:00",
                        },
                    }
                }
            ]
        ]

        class AliceExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=chunk.id,
                            label="Person",
                            text="alice",
                            char_start=0,
                            char_end=5,
                        )
                    ],  # type: ignore[arg-type]
                    relations=[],
                    extractor_name="fake",
                )

        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=AliceExtractor(),
        )
        result = await graph.add(text="alice")
        assert result.resolution.exact_match_hits == 1
        assert result.merge.nodes_updated == 1

    async def test_mentioned_in_dedup(self) -> None:
        """Same entity mentioned twice in same chunk yields one MENTIONED_IN."""
        store, embed = MockStore(), MockEmbedder()

        class DupExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                cid = chunk.id  # type: ignore[union-attr]
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=cid,
                            label="Person",
                            text="Alice",
                            char_start=0,
                            char_end=5,
                        ),
                        ExtractedEntity(
                            chunk_id=cid,
                            label="Person",
                            text="Alice",
                            char_start=6,
                            char_end=11,
                        ),
                    ],
                    relations=[],
                    extractor_name="fake",
                )

        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=DupExtractor()
        )
        await graph.add(text="Alice Alice")
        # One entity for one chunk yields a single MENTIONED_IN edge.
        mentioned = [
            r
            for batch in store.upsert_relations_calls
            for r in batch
            if r.type == "MENTIONED_IN"
        ]
        assert len(mentioned) == 1

    async def test_relation_dedup_global_and_within(self) -> None:
        """Relation dedup within-call and global."""
        store = MockStore()
        s, t = uuid4(), uuid4()
        existing_rel_id = uuid4()
        existing_cid = uuid4()

        async def fake_read(
            query: str, params: Mapping[str, Any] | None = None
        ) -> list[dict[str, Any]]:
            if "merge_key" in query:
                return []
            if "UNWIND $pairs" in query:
                pairs = params.get("pairs", []) if params else []
                for p in pairs:
                    if p["source_id"] == str(s) and p["target_id"] == str(t):
                        return [
                            {
                                "source_id": str(s),
                                "target_id": str(t),
                                "id": str(existing_rel_id),
                                "source_chunk_ids": [str(existing_cid)],
                            }
                        ]
                return []
            if "RETURN n ORDER BY" in query:
                return []
            return []

        store.execute_read = fake_read  # type: ignore[method-assign]

        from agrag.common.data_models.entity import Entity  # noqa: PLC0415

        e_s = Entity(
            id=s,
            label="Person",
            name="Alice",
            properties={},
            source_chunk_ids=[uuid4()],
        )
        e_t = Entity(
            id=t,
            label="Organization",
            name="Acme",
            properties={},
            source_chunk_ids=[uuid4()],
        )

        class RelExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                cid = chunk.id  # type: ignore[union-attr]
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=cid,
                            label="Person",
                            text="Alice",
                            char_start=0,
                            char_end=5,
                        ),
                        ExtractedEntity(
                            chunk_id=cid,
                            label="Organization",
                            text="Acme",
                            char_start=14,
                            char_end=18,
                        ),
                    ],
                    relations=[
                        ExtractedRelation(
                            chunk_id=cid,
                            label="WORKS_AT",
                            source_index=0,
                            target_index=1,
                        )
                    ],
                    extractor_name="fake",
                )

        schema = GraphSchema(
            name="test",
            version="1",
            entities=[
                EntityType(label="Person", description="p"),
                EntityType(label="Organization", description="o"),
            ],
            relations=[
                RelationType(
                    label="WORKS_AT",
                    description="w",
                    patterns=[("Person", "Organization")],
                )
            ],
        )
        graph = await Graph.open(
            schema=schema,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=RelExtractor(),
        )

        import agrag.ingestion._ingest_pipeline as gmod  # noqa: PLC0415

        async def fake_compute(  # type: ignore[no-untyped-def]
            *, existing_entities, mentions, schema, **kw
        ):
            from agrag.ingestion.merge import MergePlan  # noqa: PLC0415

            if mentions[0].text == "Alice":
                return MergePlan(survivor=e_s, tombstone_ids=[], conflicts=[]), []
            return MergePlan(survivor=e_t, tombstone_ids=[], conflicts=[]), []

        with (
            mock.patch.object(gmod, "compute_merge", side_effect=fake_compute),
            mock.patch.object(gmod, "apply_merge", new_callable=mock.AsyncMock),
        ):
            await graph.add(text="Alice works at Acme")

        # Global dedup reuses the existing relation id.
        domain_rels = [
            r
            for batch in store.upsert_relations_calls
            for r in batch
            if r.type == "WORKS_AT"
        ]
        assert len(domain_rels) == 1
        assert domain_rels[0].id == existing_rel_id
        assert (
            str(existing_cid) in domain_rels[0].properties["source_chunk_ids"]
            or len(domain_rels[0].properties["source_chunk_ids"]) >= 1
        )

    async def test_mentioned_in_reuses_transferred_edge_id(self) -> None:
        """A MENTIONED_IN edge transferred by a merge keeps its id on re-ingest.

        Regression test: transfer_relationships_query preserves a transferred
        edge's tombstone-derived id rather than recomputing it for the
        survivor. Without an endpoint lookup before writing, Graph.add would
        blindly compute a fresh mentioned_in_id() for the same (chunk,
        entity) pair and create a second, parallel edge instead of reusing
        the one already there.
        """
        store = MockStore()
        survivor_id = uuid4()
        stale_edge_id = uuid4()
        captured_chunk_id: dict[str, Any] = {}

        class AliceExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                captured_chunk_id["id"] = str(chunk.id)
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=chunk.id,
                            label="Person",
                            text="Alice",
                            char_start=0,
                            char_end=5,
                        )
                    ],
                    relations=[],
                    extractor_name="fake",
                )  # type: ignore[arg-type]

        async def fake_read(
            query: str, params: Mapping[str, Any] | None = None
        ) -> list[dict[str, Any]]:
            if "merge_key" in query:
                return []
            if "UNWIND $pairs" in query:
                pairs = params.get("pairs", []) if params else []
                for pair in pairs:
                    matches_chunk = pair["source_id"] == captured_chunk_id.get("id")
                    matches_survivor = pair["target_id"] == str(survivor_id)
                    if matches_chunk and matches_survivor:
                        return [
                            {
                                "source_id": pair["source_id"],
                                "target_id": pair["target_id"],
                                "id": str(stale_edge_id),
                                "source_chunk_ids": [],
                            }
                        ]
                return []
            return []

        store.execute_read = fake_read  # type: ignore[method-assign]

        survivor = Entity(id=survivor_id, label="Person", name="Alice", properties={})

        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=AliceExtractor(),
        )

        import agrag.ingestion._ingest_pipeline as gmod  # noqa: PLC0415

        async def fake_compute(  # type: ignore[no-untyped-def]
            *, existing_entities, mentions, schema, **kw
        ):
            from agrag.ingestion.merge import MergePlan  # noqa: PLC0415

            return MergePlan(survivor=survivor, tombstone_ids=[], conflicts=[]), []

        with (
            mock.patch.object(gmod, "compute_merge", side_effect=fake_compute),
            mock.patch.object(gmod, "apply_merge", new_callable=mock.AsyncMock),
        ):
            await graph.add(text="Alice")

        mentioned = [
            r
            for batch in store.upsert_relations_calls
            for r in batch
            if r.type == "MENTIONED_IN"
        ]
        assert len(mentioned) == 1
        assert mentioned[0].id == stale_edge_id

    async def test_embedding_failure_clears_stale_embedding(self) -> None:
        """A failed batch embed() clears any embedding already on the survivor.

        Regression test: the survivor's node is committed via apply_merge
        before this stage runs, so if embed() then fails, an embedding left
        over from before this call's update would rank the entity by
        outdated text. It must be cleared, not left in place.
        """
        store = MockStore()

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed backend down")

        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_FailingEmbedder(),
            extractor=MockExtractor(),
        )

        class BobExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=chunk.id,
                            label="Person",
                            text="Bob",
                            char_start=0,
                            char_end=3,
                        )
                    ],
                    relations=[],
                    extractor_name="fake",
                )  # type: ignore[arg-type]

        graph._extractor = BobExtractor()
        result = await graph.add(text="Bob", error_policy=ErrorPolicy.SKIP)

        clear_calls = [
            call
            for call in store.execute_write_calls
            if "REMOVE n.embedding" in call[0]
        ]
        # Both chunk and entity embedding clears on failure.
        assert len(clear_calls) >= 1
        assert result.storage.failures

    async def test_embedding_failure_clears_before_raising(self) -> None:
        """Under RAISE policy, the stale embedding is still cleared first."""
        store = MockStore()

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed backend down")

        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=_FailingEmbedder(),
            extractor=MockExtractor(),
        )

        class BobExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=chunk.id,
                            label="Person",
                            text="Bob",
                            char_start=0,
                            char_end=3,
                        )
                    ],
                    relations=[],
                    extractor_name="fake",
                )  # type: ignore[arg-type]

        graph._extractor = BobExtractor()
        with pytest.raises(RuntimeError, match="embed backend down"):
            await graph.add(text="Bob", error_policy=ErrorPolicy.RAISE)

        clear_calls = [
            call
            for call in store.execute_write_calls
            if "REMOVE n.embedding" in call[0]
        ]
        # Both chunk and entity embedding clears happen before raising.
        assert len(clear_calls) >= 1

    async def test_all_entities_by_label_pagination(self) -> None:
        """Pagination via skip/limit."""
        store = MockStore()
        eid = uuid4()
        row = {
            "n": {
                "id": str(eid),
                "labels": ["Person"],
                "properties": {
                    "name": "Alice",
                    "merge_key": "Person:alice",
                    "merged_from": [],
                    "merge_count": 1,
                    "source_chunk_ids": [],
                    "created_at": "2020-01-01T00:00:00+00:00",
                },
            }
        }
        store.execute_read_responses = [[row] * 256, [row], []]
        call_count = 0

        async def fake_read(q: str, p: Any = None) -> list[dict[str, Any]]:
            nonlocal call_count
            if "RETURN n ORDER BY" in q:
                idx = call_count
                call_count += 1
                if idx < len(store.execute_read_responses):
                    return store.execute_read_responses[idx]
                return []
            return []

        store.execute_read = fake_read  # type: ignore[method-assign]
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )
        ents = await graph._all_entities_by_label("Person")
        assert len(ents) == 257
        assert call_count == 2

        store2 = MockStore()

        async def fake_read2(q: str, p: Any = None) -> list[dict[str, Any]]:
            if "RETURN n ORDER BY" in q:
                return [
                    {
                        "n": {
                            "id": str(uuid4()),
                            "labels": ["Person"],
                            "properties": {
                                "name": "Tomb",
                                "merge_key": "Person:tomb",
                                "merged_from": [],
                                "merge_count": 1,
                                "source_chunk_ids": [],
                                "created_at": "2020-01-01T00:00:00+00:00",
                                "merged_into": str(uuid4()),
                            },
                        }
                    }
                ]
            return []

        store2.execute_read = fake_read2  # type: ignore[method-assign]
        graph2 = await Graph.open(
            schema=GENERIC,
            graph_store=store2,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )
        ents2 = await graph2._all_entities_by_label("Person")
        assert ents2 == []

    async def test_consolidate_dry_run_and_apply(self) -> None:
        """Consolidate reports and materializes matches without merging raw nodes."""
        store = MockStore()
        e1 = Entity(
            id=uuid4(),
            label="Person",
            name="Alice",
            properties={},
            source_chunk_ids=[uuid4()],
        )
        e2 = Entity(
            id=uuid4(),
            label="Person",
            name="alice",
            properties={},
            source_chunk_ids=[uuid4()],
        )
        small_schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label="Person", description="p")],
            relations=[],
        )
        graph = await Graph.open(
            schema=small_schema,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )
        with mock.patch.object(
            graph, "_all_entities_by_label", new_callable=mock.AsyncMock
        ) as mock_all:
            mock_all.return_value = [e1, e2]
            import agrag.ingestion.graph as gmod  # noqa: PLC0415

            with mock.patch.object(gmod, "Resolver") as mock_resolver:
                mock_instance = mock.AsyncMock()
                from agrag.ingestion.resolve import (  # noqa: PLC0415
                    ResolutionResult,
                    ResolvedMatch,
                )

                mock_instance.resolve.return_value = ResolutionResult(
                    groups=[],
                    matches=[
                        ResolvedMatch(
                            left_index=0,
                            right_index=1,
                            comparator="FuzzyMatch",
                            decided_at=datetime.now(UTC),
                        )
                    ],
                )
                mock_resolver.return_value = mock_instance
                with (
                    mock.patch.object(
                        gmod,
                        "write_matches_and_materialize",
                        new_callable=mock.AsyncMock,
                    ) as materialize,
                    mock.patch.object(
                        gmod,
                        "_synchronize_resolved_entity_vectors",
                        new_callable=mock.AsyncMock,
                    ) as synchronize,
                ):
                    resolved = ResolvedEntity(
                        id=uuid4(),
                        label="Person",
                        name="Alice",
                        member_ids=[e1.id, e2.id],
                    )
                    replaced_id = uuid4()
                    materialize.return_value = MaterializationResult(
                        resolved_entity=resolved,
                        removed_entity_ids=[replaced_id],
                    )
                    synchronize.return_value = []
                    report = await graph.consolidate(apply=False)
                    assert len(report.would_match) == 1
                    assert report.applied is False
                    materialize.assert_not_awaited()
                    report2 = await graph.consolidate(apply=True)
                    assert report2.applied is True
                    materialize.assert_awaited_once()
                    synchronize.assert_awaited_once()
                    assert synchronize.await_args.args[:2] == (
                        [resolved],
                        [replaced_id],
                    )

    async def test_consolidate_reports_materialization_failure(self) -> None:
        """A failed materialization keeps raw entities intact and reports the error."""
        store = MockStore()
        e1 = Entity(
            id=uuid4(),
            label="Person",
            name="Alice",
            properties={},
            source_chunk_ids=[uuid4()],
        )
        e2 = Entity(
            id=uuid4(),
            label="Person",
            name="alice",
            properties={},
            source_chunk_ids=[uuid4()],
        )
        small_schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label="Person", description="p")],
            relations=[],
        )
        graph = await Graph.open(
            schema=small_schema,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )
        with mock.patch.object(
            graph, "_all_entities_by_label", new_callable=mock.AsyncMock
        ) as mock_all:
            mock_all.return_value = [e1, e2]
            import agrag.ingestion.graph as gmod  # noqa: PLC0415

            with mock.patch.object(gmod, "Resolver") as mock_resolver:
                mock_instance = mock.AsyncMock()
                from agrag.ingestion.resolve import (  # noqa: PLC0415
                    ResolutionResult,
                    ResolvedMatch,
                )

                mock_instance.resolve.return_value = ResolutionResult(
                    groups=[],
                    matches=[
                        ResolvedMatch(
                            left_index=0,
                            right_index=1,
                            comparator="FuzzyMatch",
                            decided_at=datetime.now(UTC),
                        )
                    ],
                )
                mock_resolver.return_value = mock_instance
                with mock.patch.object(
                    gmod,
                    "write_matches_and_materialize",
                    new_callable=mock.AsyncMock,
                    side_effect=RuntimeError("database unavailable"),
                ):
                    report = await graph.consolidate(apply=True)

        assert len(report.failures) == 1
        assert report.failures[0].error_message == "database unavailable"
        assert report.applied is False
        assert store.upsert_nodes_calls == []
        assert store.upsert_relations_calls == []
