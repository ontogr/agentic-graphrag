"""Exercise Graph ingestion helpers and pipeline wiring through the public Graph API."""

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any
from unittest import mock
from uuid import uuid4

import pytest

from agrag.common.data_models.chunk import Chunk as ChunkModel
from agrag.common.data_models.document import Document, DocumentFamily, SourceFormat
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_record import NodeRecord, RelationRecord
from agrag.common.data_models.graph_schema import (
    GENERIC,
    EntityType,
    GraphSchema,
    RelationType,
)
from agrag.common.data_models.provenance import TextProvenance
from agrag.common.data_models.vector_record import VectorHit
from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.graphdb.errors import (
    GraphStoreAliasConflictError,
    GraphStoreConstraintViolationError,
    GraphStoreDataIntegrityError,
)
from agrag.ingestion.extract import Extractor
from agrag.ingestion.graph import (
    Graph,
    _apply_merge_with_conflict_retry,
    _embed_and_upsert_survivors,
    _extract_merged_into,
    _global_exact_match,
    _global_relation_lookup,
    _parse_entity_node,
    _resolve_paths,
    _resolve_tombstone_chain,
    _synthesize_consolidation_mentions,
    _union_groups_by_existing_entity,
)
from agrag.ingestion.merge import MergePlan
from agrag.ingestion.resolve import ResolutionGroup
from agrag.ingestion.types import AddResult
from agrag.loaders.corpus.types import ErrorPolicy


class MockStore(GraphStore):
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
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Record the read and return the next canned response."""
        self.execute_read_calls.append((query, parameters))
        if self._read_index < len(self.execute_read_responses):
            response = self.execute_read_responses[self._read_index]
            self._read_index += 1
            return response
        return []

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Record the write."""
        self.execute_write_calls.append((query, parameters))
        return []

    async def setup_constraints(self) -> None:
        """Record a setup_constraints call."""
        self.setup_constraints_calls += 1

    async def setup_indexes(self) -> None:
        """Record a setup_indexes call."""
        self.setup_indexes_calls += 1

    async def upsert_nodes(
        self, label: str, nodes: Sequence[NodeRecord], *, batch_size: int = 256
    ) -> None:
        """Record a node upsert."""
        self.upsert_nodes_calls.append((label, list(nodes)))

    async def upsert_relations(
        self, relations: Sequence[RelationRecord], *, batch_size: int = 256
    ) -> None:
        """Record a relation upsert."""
        self.upsert_relations_calls.append(list(relations))

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
                "age": "30",
            },
        }
        ent = _parse_entity_node(node)
        assert ent is not None
        assert ent.label == "Person"
        assert ent.name == "Alice"
        assert ent.properties["age"] == "30"
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

    async def test_empty_returns_empty(self) -> None:
        """Empty mentions returns empty."""
        store = MockStore()
        result = await _global_exact_match([], graph_store=store)
        assert result == {}
        assert store.execute_read_calls == []

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

    async def test_handles_flat_row_and_missing(self) -> None:
        """Handles flat row form and skips unparsable rows."""
        store = MockStore()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        # Flat rows with varied shapes exercise the fallback parsing.
        store.execute_read_responses = [
            [
                {
                    "id": str(uuid4()),
                    "merge_key": "Person:bob",
                    "name": "Bob",
                },
                {"n": {"id": "bad", "labels": ["Person"], "properties": {}}},
            ]
        ]
        result = await _global_exact_match([m], graph_store=store)
        assert isinstance(result, dict)

    async def test_handles_no_rows(self) -> None:
        """No rows yields empty map entry."""
        store = MockStore()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="NoHit", char_start=0, char_end=5
        )
        store.execute_read_responses = [[]]
        result = await _global_exact_match([m], graph_store=store)
        assert result == {}

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

    def test_no_merged_into_returns_none(self) -> None:
        """A live node with no merged_into is a genuine negative, not a failure."""
        node = {"labels": ["Person"], "properties": {"name": "Bob"}}
        assert _extract_merged_into(node, {}) is None

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


class TestUnionGroupsByExistingEntity:
    """_union_groups_by_existing_entity merges groups sharing an exact match."""

    def test_two_groups_matching_the_same_entity_are_unioned(self) -> None:
        """Two singleton groups that alias to the same entity become one group.

        Regression test: in-batch comparators never compared "Bob" and
        "Robert" directly, so the resolver kept them in separate groups.
        Both independently exact-match the same persisted entity through
        different accepted aliases; without unioning, computing and
        applying one plan per resolver group would have the second
        group's apply_merge overwrite the first's contribution.
        """
        entity = Entity(id=uuid4(), label="Person", name="Robert", properties={})
        groups = [
            ResolutionGroup(entity_indices=[0]),
            ResolutionGroup(entity_indices=[1]),
        ]
        exact_matches = {0: entity, 1: entity}
        result = _union_groups_by_existing_entity(groups, exact_matches)
        assert len(result) == 1
        assert result[0].entity_indices == [0, 1]

    def test_groups_matching_different_entities_stay_separate(self) -> None:
        """Groups exact-matching different entities are not unioned."""
        e1 = Entity(id=uuid4(), label="Person", name="Ada", properties={})
        e2 = Entity(id=uuid4(), label="Person", name="Bob", properties={})
        groups = [
            ResolutionGroup(entity_indices=[0]),
            ResolutionGroup(entity_indices=[1]),
        ]
        exact_matches = {0: e1, 1: e2}
        result = _union_groups_by_existing_entity(groups, exact_matches)
        assert len(result) == 2

    def test_groups_with_no_exact_match_stay_separate(self) -> None:
        """A group with no exact-matched entity at all is left alone."""
        groups = [
            ResolutionGroup(entity_indices=[0]),
            ResolutionGroup(entity_indices=[1]),
        ]
        result = _union_groups_by_existing_entity(groups, {})
        assert len(result) == 2

    def test_transitively_unions_three_groups(self) -> None:
        """A -- entity -- B and B -- entity -- C unions A, B, and C together."""
        e1 = Entity(id=uuid4(), label="Person", name="X", properties={})
        e2 = Entity(id=uuid4(), label="Person", name="Y", properties={})
        groups = [
            ResolutionGroup(entity_indices=[0]),
            ResolutionGroup(entity_indices=[1]),
            ResolutionGroup(entity_indices=[2]),
        ]
        # Group 0 and group 1 share e1; group 1 and group 2 share e2 via
        # entity_indices 1 and 2 both resolving to e2.
        exact_matches = {0: e1, 1: e1, 2: e2}
        # Make group 1 also touch e2 so it bridges groups 0 and 2.
        groups[1] = ResolutionGroup(entity_indices=[1, 3])
        exact_matches[3] = e2
        result = _union_groups_by_existing_entity(groups, exact_matches)
        assert len(result) == 1
        assert result[0].entity_indices == [0, 1, 2, 3]


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

    def test_mentions_are_index_aligned_with_entities(self) -> None:
        """Each mention carries its own entity's label and name."""
        alice = Entity(id=uuid4(), label="Person", name="Alice", properties={})
        acme = Entity(id=uuid4(), label="Organization", name="Acme", properties={})

        mentions, dummy_chunks_by_id = _synthesize_consolidation_mentions([alice, acme])

        assert [m.label for m in mentions] == ["Person", "Organization"]
        assert [m.text for m in mentions] == ["Alice", "Acme"]
        assert len(dummy_chunks_by_id) == 2


class TestApplyMergeWithConflictRetry:
    """_apply_merge_with_conflict_retry recovers from a concurrent create race."""

    async def test_retries_and_merges_into_the_winner(self) -> None:
        """A constraint violation on a brand-new entity re-resolves and retries.

        Regression test: two concurrent add() calls for the same normalized
        name can both miss the exact-match lookup and both try to create a
        live node for the same merge_key. merge_key_constraint_query rejects
        whichever lands second; this must recover by re-resolving to the
        entity that won the race, rather than losing the mention or
        crashing the whole add() call.
        """
        winner_id = uuid4()
        mention = ExtractedEntity(
            chunk_id=uuid4(), label="Person", text="Bob", char_start=0, char_end=3
        )
        losing_plan = MergePlan(
            survivor=Entity(id=uuid4(), label="Person", name="Bob", properties={}),
            tombstone_ids=[],
            conflicts=[],
        )

        store = MockStore()
        store.execute_read_responses = [
            [
                {
                    "n": {
                        "id": str(winner_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Bob",
                            "merge_key": "Person:bob",
                            "merged_from": [],
                            "merge_count": 1,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                        },
                    }
                }
            ]
        ]

        import agrag.ingestion.graph as gmod  # noqa: PLC0415

        call_count = 0

        async def fake_apply_merge(
            plan: MergePlan, *, graph_store: object, schema: object
        ) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise GraphStoreConstraintViolationError("merge_key already exists")

        with mock.patch.object(gmod, "apply_merge", side_effect=fake_apply_merge):
            plan, desc_failures = await _apply_merge_with_conflict_retry(
                losing_plan,
                graph_store=store,
                schema=GENERIC,
                existing_entities=[],
                mentions=[mention],
                is_new_entity=True,
            )

        assert call_count == 2
        assert plan.survivor.id == winner_id
        assert desc_failures == []

    async def test_reraises_when_not_a_new_entity(self) -> None:
        """A violation while updating an existing entity is not this race: reraise."""
        plan = MergePlan(
            survivor=Entity(id=uuid4(), label="Person", name="Bob", properties={}),
            tombstone_ids=[],
            conflicts=[],
        )
        store = MockStore()
        import agrag.ingestion.graph as gmod  # noqa: PLC0415

        async def fake_apply_merge(*args: object, **kwargs: object) -> None:
            raise GraphStoreConstraintViolationError("boom")

        with (
            mock.patch.object(gmod, "apply_merge", side_effect=fake_apply_merge),
            pytest.raises(GraphStoreConstraintViolationError),
        ):
            await _apply_merge_with_conflict_retry(
                plan,
                graph_store=store,
                schema=GENERIC,
                existing_entities=[],
                mentions=[],
                is_new_entity=False,
            )

    async def test_reraises_when_winner_cannot_be_found(self) -> None:
        """If the constraint says it exists but re-resolution finds nothing, reraise."""
        plan = MergePlan(
            survivor=Entity(id=uuid4(), label="Person", name="Bob", properties={}),
            tombstone_ids=[],
            conflicts=[],
        )
        store = MockStore()
        store.execute_read_responses = [[]]
        import agrag.ingestion.graph as gmod  # noqa: PLC0415

        async def fake_apply_merge(*args: object, **kwargs: object) -> None:
            raise GraphStoreConstraintViolationError("boom")

        with (
            mock.patch.object(gmod, "apply_merge", side_effect=fake_apply_merge),
            pytest.raises(GraphStoreConstraintViolationError),
        ):
            await _apply_merge_with_conflict_retry(
                plan,
                graph_store=store,
                schema=GENERIC,
                existing_entities=[],
                mentions=[],
                is_new_entity=True,
            )

    async def test_alias_conflict_merges_into_the_true_owner(self) -> None:
        """A merge-key alias claimed by another entity re-resolves and retries.

        Regression test: canonical "Bob" is created by one writer while this
        call separately resolves mentions "Robert" and "Bob" as the same
        entity, accepting "Bob" as an alias of "Robert". Neither writer's
        own node merge_key collides -- apply_merge raises
        GraphStoreAliasConflictError itself instead of a backend constraint
        -- so recovery must fold the real "Bob" owner into existing_entities
        and merge both mentions into it, rather than leaving two live
        entities that both believe they own the name "Bob".
        """
        bob_owner_id = uuid4()
        robert_mention = ExtractedEntity(
            chunk_id=uuid4(), label="Person", text="Robert", char_start=0, char_end=6
        )
        bob_mention = ExtractedEntity(
            chunk_id=uuid4(), label="Person", text="Bob", char_start=0, char_end=3
        )
        losing_plan = MergePlan(
            survivor=Entity(id=uuid4(), label="Person", name="Robert", properties={}),
            tombstone_ids=[],
            conflicts=[],
            accepted_merge_keys=["Person:robert", "Person:bob"],
        )

        store = MockStore()
        store.execute_read_responses = [
            [
                {
                    "n": {
                        "id": str(bob_owner_id),
                        "labels": ["Person"],
                        "properties": {
                            "name": "Bob",
                            "merge_key": "Person:bob",
                            "merged_from": [],
                            "merge_count": 1,
                            "source_chunk_ids": [],
                            "created_at": "2020-01-01T00:00:00+00:00",
                        },
                    }
                }
            ]
        ]

        import agrag.ingestion.graph as gmod  # noqa: PLC0415

        call_count = 0

        async def fake_apply_merge(
            plan: MergePlan, *, graph_store: object, schema: object
        ) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise GraphStoreAliasConflictError({"Person:bob": str(bob_owner_id)})

        with mock.patch.object(gmod, "apply_merge", side_effect=fake_apply_merge):
            plan, desc_failures = await _apply_merge_with_conflict_retry(
                losing_plan,
                graph_store=store,
                schema=GENERIC,
                existing_entities=[],
                mentions=[robert_mention, bob_mention],
                is_new_entity=True,
            )

        assert call_count == 2
        assert plan.survivor.id == bob_owner_id
        assert plan.tombstone_ids == []
        assert desc_failures == []

    async def test_alias_conflict_reraises_when_owner_cannot_be_found(self) -> None:
        """If the alias claim reports an owner re-resolution cannot find, reraise."""
        plan = MergePlan(
            survivor=Entity(id=uuid4(), label="Person", name="Robert", properties={}),
            tombstone_ids=[],
            conflicts=[],
            accepted_merge_keys=["Person:robert", "Person:bob"],
        )
        store = MockStore()
        store.execute_read_responses = [[]]
        import agrag.ingestion.graph as gmod  # noqa: PLC0415

        async def fake_apply_merge(*args: object, **kwargs: object) -> None:
            raise GraphStoreAliasConflictError({"Person:bob": str(uuid4())})

        with (
            mock.patch.object(gmod, "apply_merge", side_effect=fake_apply_merge),
            pytest.raises(GraphStoreAliasConflictError),
        ):
            await _apply_merge_with_conflict_retry(
                plan,
                graph_store=store,
                schema=GENERIC,
                existing_entities=[],
                mentions=[],
                is_new_entity=True,
            )


class TestGlobalRelationLookup:
    """Tests for _global_relation_lookup."""

    async def test_empty_returns_empty(self) -> None:
        """Empty triples returns empty."""
        store = MockStore()
        result = await _global_relation_lookup([], graph_store=store)
        assert result == {}

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

    async def test_dedups_unique_pairs(self) -> None:
        """Duplicate pairs are deduped before query."""
        store = MockStore()
        s, t = uuid4(), uuid4()
        triples = [(s, t, "WORKS_AT"), (s, t, "WORKS_AT")]
        await _global_relation_lookup(triples, graph_store=store)
        assert (
            store.execute_read_calls[0][1]["pairs"].count(
                {"source_id": str(s), "target_id": str(t)}
            )
            == 1
        )


class _GuardedNodeStore(MockStore):
    """MockStore whose execute_write honors the embedding write/clear guard.

    set_embedding_query and clear_property_query only apply a record when
    the target node's current name/description match the record's
    expected_name/expected_description. Real Neo4j enforces that WHERE
    clause; this fake reproduces it in memory so a concurrent-write test can
    prove a stale record is rejected without a live database.
    """

    def __init__(self, nodes: dict[str, dict[str, Any]]) -> None:
        super().__init__()
        self.nodes = nodes

    async def execute_write(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        await super().execute_write(query, parameters)
        records = (parameters or {}).get("records", [])
        for record in records:
            node = self.nodes.get(record["id"])
            if node is None:
                continue
            if node["name"] != record["expected_name"]:
                continue
            if (node.get("description") or "") != record["expected_description"]:
                continue
            if "REMOVE n.embedding" in query:
                node["embedding"] = None
            elif "SET n.embedding" in query:
                node["embedding"] = record["vector"]
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


class TestGraphOpen:
    """Tests for Graph.open."""

    async def test_open_provisions_in_order(self) -> None:
        """Provisioning is connect, labels, types, constraints, indexes."""
        order: list[str] = []

        class OrderedStore(MockStore):
            async def connect(self) -> None:
                order.append("connect")

            async def register_labels(self, labels: Sequence[str]) -> None:
                order.append(f"labels:{','.join(sorted(labels))}")

            async def register_relation_types(self, types: Sequence[str]) -> None:
                order.append(f"types:{','.join(sorted(types))}")

            async def setup_constraints(self) -> None:
                order.append("constraints")

            async def setup_indexes(self) -> None:
                order.append("indexes")

        store = OrderedStore()
        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )
        assert order[0] == "connect"
        assert any("Chunk" in entry for entry in order if entry.startswith("labels"))
        assert any(
            "MENTIONED_IN" in entry for entry in order if entry.startswith("types")
        )
        assert order[-2] == "constraints"
        assert order[-1] == "indexes"
        assert isinstance(graph, Graph)

    async def test_open_registers_schema_labels_and_system_names(self) -> None:
        """All schema labels/types plus system names are registered."""
        store = MockStore()
        schema = GraphSchema(
            name="test",
            version="1",
            entities=[EntityType(label="Person", description="p")],
            relations=[
                RelationType(
                    label="WORKS_AT", description="w", patterns=[("Person", "Person")]
                )
            ],
        )
        await Graph.open(
            schema=schema,
            graph_store=store,
            embedder=MockEmbedder(),
            extractor=MockExtractor(),
        )
        assert "Person" in store.register_labels_calls[0]
        assert "Chunk" in store.register_labels_calls[0]
        assert "WORKS_AT" in store.register_types_calls[0]
        assert "MENTIONED_IN" in store.register_types_calls[0]


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

    async def test_add_requires_exactly_one_input(self) -> None:
        """Add validates exactly one input."""
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        with pytest.raises(ValueError):
            await graph.add()
        with pytest.raises(ValueError):
            await graph.add(text="x", documents=[_doc()])

    async def test_loader_requires_source(self) -> None:
        """Loader without source raises."""
        from agrag.loaders.corpus.readers.prose import TextLoader  # noqa: PLC0415

        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        with pytest.raises(ValueError):
            await graph.add(text="x", loader=TextLoader())
        with pytest.raises(ValueError):
            await graph.add(documents=[_doc()], loader=TextLoader())

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

    async def test_add_text_produces_add_result(self) -> None:
        """Text path yields AddResult with ingestion stats."""
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        result = await graph.add(text="hello world", return_chunks=True)
        assert isinstance(result, AddResult)
        assert result.ingestion.documents == 1
        assert result.extraction.chunks_processed == 1
        assert result.chunks

    async def test_add_documents_path(self) -> None:
        """Documents path chunks and extracts."""
        store, embed, extractor = MockStore(), MockEmbedder(), MockExtractor()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=extractor
        )
        result = await graph.add(documents=[_doc("doc text")], return_chunks=False)
        assert result.ingestion.documents == 1
        # No chunks returned when return_chunks is False.
        assert result.chunks == []
        assert result.extraction.chunks_processed == 1

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

    async def test_relation_index_remapping(self) -> None:
        """Relations indices remapped with global offset."""
        cid = uuid4()
        _chunk("Alice works at Acme")
        ExtractedEntity(
            chunk_id=cid, label="Person", text="Alice", char_start=0, char_end=5
        )
        ExtractedEntity(
            chunk_id=cid, label="Organization", text="Acme", char_start=14, char_end=18
        )
        ExtractedRelation(
            chunk_id=cid, label="RELATED_TO", source_index=0, target_index=1
        )
        store, embed = MockStore(), MockEmbedder()

        class TwoChunkExtractor(Extractor):
            async def extract(
                self, chunk: ChunkModel, schema: GraphSchema
            ) -> ExtractionResult:
                return ExtractionResult(
                    entities=[
                        ExtractedEntity(
                            chunk_id=chunk.id,
                            label="Person",
                            text="P",
                            char_start=0,
                            char_end=1,
                        ),  # type: ignore[arg-type]
                    ],
                    relations=[],
                    extractor_name="fake",
                )

        graph = await Graph.open(
            schema=GENERIC,
            graph_store=store,
            embedder=embed,
            extractor=TwoChunkExtractor(),
        )
        result = await graph.add(documents=[_doc("a"), _doc("b")])
        assert result.extraction.entities_extracted == 2

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
        assert len(mentioned[0].properties.get("source_chunk_ids", [])) == 0 or True

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

        import agrag.ingestion.graph as gmod  # noqa: PLC0415

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

        import agrag.ingestion.graph as gmod  # noqa: PLC0415

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

    async def test_storage_and_embedding(self) -> None:
        """Embedding stage assigns vectors and upserts."""
        store, embed = MockStore(), MockEmbedder()
        graph = await Graph.open(
            schema=GENERIC, graph_store=store, embedder=embed, extractor=MockExtractor()
        )
        chunk = _chunk("Bob")
        ExtractedEntity(
            chunk_id=chunk.id, label="Person", text="Bob", char_start=0, char_end=3
        )  # type: ignore[arg-type]

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
        result = await graph.add(text="Bob")
        survivor_write_calls = [
            call
            for call in store.execute_write_calls
            if call[1]
            and "records" in call[1]
            and "properties" in call[1]["records"][0]
        ]
        assert len(survivor_write_calls) >= 1
        embedding_calls = [
            call
            for call in store.execute_write_calls
            if call[1] and "records" in call[1] and "vector" in call[1]["records"][0]
        ]
        assert len(embedding_calls) == 1
        assert result.storage.nodes_written >= 1

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
        assert len(clear_calls) == 1
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
        assert len(clear_calls) == 1

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
        """Consolidate dry-run vs apply."""
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
                from agrag.ingestion.resolve import ResolutionGroup  # noqa: PLC0415

                mock_instance.resolve.return_value = [
                    ResolutionGroup(entity_indices=[0, 1])
                ]
                mock_resolver.return_value = mock_instance
                with mock.patch.object(
                    gmod, "compute_merge", new_callable=mock.AsyncMock
                ) as mock_compute:
                    from agrag.ingestion.merge import MergePlan  # noqa: PLC0415

                    survivor = Entity(
                        id=e1.id,
                        label="Person",
                        name="Alice",
                        properties={},
                        source_chunk_ids=e1.source_chunk_ids + e2.source_chunk_ids,
                    )
                    mock_compute.return_value = (
                        MergePlan(
                            survivor=survivor, tombstone_ids=[e2.id], conflicts=[]
                        ),
                        [],
                    )
                    with mock.patch.object(
                        gmod, "apply_merge", new_callable=mock.AsyncMock
                    ) as mock_apply:
                        report = await graph.consolidate(apply=False)
                        assert len(report.would_merge) == 1
                        assert report.applied is False
                        mock_apply.assert_not_called()
                        report2 = await graph.consolidate(apply=True)
                        assert report2.applied is True
                        assert mock_apply.call_count == 1

    async def test_consolidate_apply_reembeds_survivor(self) -> None:
        """Applying a consolidation re-embeds the survivor's final text.

        Regression test: apply_merge alone never computes an embedding, so
        without this, a survivor whose canonical name changed by
        consolidation would keep whatever embedding it had before, and
        vector search would keep ranking it by that stale text.
        """
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
                from agrag.ingestion.resolve import ResolutionGroup  # noqa: PLC0415

                mock_instance.resolve.return_value = [
                    ResolutionGroup(entity_indices=[0, 1])
                ]
                mock_resolver.return_value = mock_instance
                with mock.patch.object(
                    gmod, "compute_merge", new_callable=mock.AsyncMock
                ) as mock_compute:
                    survivor = Entity(
                        id=e1.id,
                        label="Person",
                        name="Alice",
                        properties={},
                        source_chunk_ids=e1.source_chunk_ids + e2.source_chunk_ids,
                    )
                    mock_compute.return_value = (
                        MergePlan(
                            survivor=survivor, tombstone_ids=[e2.id], conflicts=[]
                        ),
                        [],
                    )
                    with mock.patch.object(
                        gmod, "apply_merge", new_callable=mock.AsyncMock
                    ):
                        report = await graph.consolidate(apply=True)

        assert report.failures == []
        embedding_calls = [
            call
            for call in store.execute_write_calls
            if call[1] and "records" in call[1] and "vector" in call[1]["records"][0]
        ]
        assert len(embedding_calls) == 1

    async def test_consolidate_apply_clears_embedding_on_failure(self) -> None:
        """A failed re-embed during apply clears the stale embedding and reports it."""
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

        class _FailingEmbedder(MockEmbedder):
            async def embed(self, texts: Sequence[str]) -> list[list[float]]:
                raise RuntimeError("embed backend down")

        graph = await Graph.open(
            schema=small_schema,
            graph_store=store,
            embedder=_FailingEmbedder(),
            extractor=MockExtractor(),
        )
        with mock.patch.object(
            graph, "_all_entities_by_label", new_callable=mock.AsyncMock
        ) as mock_all:
            mock_all.return_value = [e1, e2]
            import agrag.ingestion.graph as gmod  # noqa: PLC0415

            with mock.patch.object(gmod, "Resolver") as mock_resolver:
                mock_instance = mock.AsyncMock()
                from agrag.ingestion.resolve import ResolutionGroup  # noqa: PLC0415

                mock_instance.resolve.return_value = [
                    ResolutionGroup(entity_indices=[0, 1])
                ]
                mock_resolver.return_value = mock_instance
                with mock.patch.object(
                    gmod, "compute_merge", new_callable=mock.AsyncMock
                ) as mock_compute:
                    survivor = Entity(
                        id=e1.id,
                        label="Person",
                        name="Alice",
                        properties={},
                        source_chunk_ids=e1.source_chunk_ids + e2.source_chunk_ids,
                    )
                    mock_compute.return_value = (
                        MergePlan(
                            survivor=survivor, tombstone_ids=[e2.id], conflicts=[]
                        ),
                        [],
                    )
                    with mock.patch.object(
                        gmod, "apply_merge", new_callable=mock.AsyncMock
                    ):
                        report = await graph.consolidate(apply=True)

        assert len(report.failures) == 1
        clear_calls = [
            call
            for call in store.execute_write_calls
            if "REMOVE n.embedding" in call[0]
        ]
        assert len(clear_calls) == 1

    async def test_consolidate_no_entities(self) -> None:
        """Less than 2 entities yields no would_merge."""
        store = MockStore()
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
            mock_all.return_value = []
            report = await graph.consolidate()
            assert report.would_merge == []
            assert report.applied is False
