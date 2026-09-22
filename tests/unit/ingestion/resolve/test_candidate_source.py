"""Tests for GraphCandidateSource and exact_match_lookup.

Covers same-label in-batch blocking with exact index sets, the guarantee
that the in-batch path never touches GraphStore.vector_search or
VectorStore.hybrid_search, batch-bounded cost independent of graph size,
both global_candidates_for routing branches, top_k defaults and
passthrough, and exact_match_lookup alias and tombstone-chain behavior.
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.vector_record import VectorHit
from agrag.ingestion.resolve.candidate_source import (
    GraphCandidateSource,
    exact_match_lookup,
)


def _mention(text: str, label: str = "Show") -> ExtractedEntity:
    """Build a mention for candidate-source tests."""
    return ExtractedEntity(
        chunk_id=uuid4(),
        label=label,
        text=text,
        char_start=0,
        char_end=len(text),
    )


def _source(
    *,
    vector_store: AsyncMock | None = None,
    top_k: int = 50,
) -> tuple[GraphCandidateSource, AsyncMock]:
    """Build a source with mocked stores for in-batch tests."""
    graph_store = AsyncMock()
    graph_store.vector_search = AsyncMock()
    source = GraphCandidateSource(
        graph_store=graph_store,
        embedder=MagicMock(),
        vector_store=vector_store,
        top_k=top_k,
    )
    return source, graph_store


class TestGraphCandidateSourceInBatch:
    """candidates_for blocks by label within the batch."""

    async def test_never_proposes_cross_label(self) -> None:
        """Only the same-label mention is proposed."""
        source, _ = _source()
        entities = [
            _mention("Ada", label="Person"),
            _mention("Apple", label="Organization"),
            _mention("Charles", label="Person"),
        ]
        assert await source.candidates_for(0, entities) == [2]

    async def test_proposes_all_same_label(self) -> None:
        """Every other same-label mention is proposed in order."""
        source, _ = _source()
        entities = [
            _mention("Ada", label="Person"),
            _mention("Charles", label="Person"),
            _mention("Grace", label="Person"),
        ]
        assert await source.candidates_for(0, entities) == [1, 2]
        assert await source.candidates_for(1, entities) == [0, 2]

    async def test_excludes_self(self) -> None:
        """A lone mention has no candidates."""
        source, _ = _source()
        assert await source.candidates_for(0, [_mention("Ada")]) == []


class TestInBatchNeverTouchesStores:
    """The in-batch path is pure and never searches a store."""

    async def test_never_calls_vector_search_or_hybrid_search(self) -> None:
        """Neither GraphStore nor VectorStore search runs in-batch."""
        vector_store = AsyncMock()
        vector_store.hybrid_search = AsyncMock()
        source, graph_store = _source(vector_store=vector_store)
        entities = [
            _mention("Ada", label="Person"),
            _mention("Charles", label="Person"),
        ]
        assert await source.candidates_for(0, entities) == [1]
        graph_store.vector_search.assert_not_called()
        vector_store.hybrid_search.assert_not_called()
        graph_store.execute_read.assert_not_called()

    async def test_cost_bounded_by_batch_not_graph_size(self) -> None:
        """Same batch against small and huge graphs makes identical calls."""
        batch = [
            _mention("Ada", label="Person"),
            _mention("Charles", label="Person"),
            _mention("Acme", label="Organization"),
        ]
        small_source, small_store = _source()
        huge_vector_store = AsyncMock()
        huge_vector_store.hybrid_search = AsyncMock()
        huge_source, huge_store = _source(vector_store=huge_vector_store)
        small_results = [await small_source.candidates_for(i, batch) for i in range(3)]
        huge_results = [await huge_source.candidates_for(i, batch) for i in range(3)]
        assert small_results == huge_results == [[1], [0], []]
        assert small_store.method_calls == huge_store.method_calls == []
        small_store.vector_search.assert_not_called()
        huge_store.vector_search.assert_not_called()
        huge_vector_store.hybrid_search.assert_not_called()


class TestGraphCandidateSourceGlobalCandidatesFor:
    """global_candidates_for resolves vector hits into persisted entities."""

    async def test_returns_untruncated_name_for_vector_store_hit(self) -> None:
        """A colon in the real name is not truncated by the VectorStore path.

        Regression: the payload only carries embedding_text under "text", so
        guessing the name by splitting on ":" turned "Star Trek: Voyager"
        into "Star Trek". The fix hydrates the real node by id instead.
        """
        entity_id = uuid4()
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = [
            {
                "n": {
                    "id": str(entity_id),
                    "labels": ["Show", "_AgragNode"],
                    "properties": {"name": "Star Trek: Voyager"},
                }
            }
        ]
        source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=MagicMock(),
            vector_store=AsyncMock(),
            vector_collection="entities",
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=entity_id,
                    score=0.9,
                    payload={"label": "Show", "text": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        assert len(candidates) == 1
        assert candidates[0].name == "Star Trek: Voyager"

    async def test_skips_hits_that_fail_to_hydrate(self) -> None:
        """A hit whose node cannot be hydrated is dropped, not guessed."""
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = []
        source = GraphCandidateSource(
            graph_store=graph_store,
            embedder=MagicMock(),
            vector_store=AsyncMock(),
            vector_collection="entities",
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=uuid4(),
                    score=0.9,
                    payload={"label": "Show", "text": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        assert candidates == []

    async def test_native_path_validates_payload_directly(self) -> None:
        """With no VectorStore, the native payload already has the real name.

        The native path must not be touched by the hydrate-by-id fix, and
        must not issue a graph read to get the name.
        """
        entity_id = uuid4()
        graph_store = AsyncMock()
        source = GraphCandidateSource(
            graph_store=graph_store, embedder=MagicMock(), vector_store=None
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[
                VectorHit(
                    id=entity_id,
                    score=0.9,
                    payload={"name": "Star Trek: Voyager"},
                )
            ],
        ):
            candidates = await source.global_candidates_for(
                _mention("Star Trek: Voyager")
            )

        graph_store.execute_read.assert_not_called()
        assert len(candidates) == 1
        assert candidates[0].name == "Star Trek: Voyager"

    async def test_returns_empty_when_no_hits(self) -> None:
        """No vector hits means no candidates on either branch."""
        graph_store = AsyncMock()
        source = GraphCandidateSource(
            graph_store=graph_store, embedder=MagicMock(), vector_store=None
        )

        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[],
        ):
            assert await source.global_candidates_for(_mention("Ada")) == []

        graph_store.execute_read.assert_not_called()


class TestGraphCandidateSourceTopK:
    """top_k defaults to 50 and reaches vector_search as limit."""

    def test_default_top_k_is_50(self) -> None:
        """A source without top_k searches 50 candidates."""
        source, _ = _source()
        assert source.top_k == 50

    async def test_default_top_k_passes_limit_50(self) -> None:
        """The default top_k is forwarded as the search limit."""
        source, _ = _source()
        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search:
            await source.global_candidates_for(_mention("Ada"))
        assert mock_search.call_args is not None
        assert mock_search.call_args.kwargs["limit"] == 50

    async def test_override_top_k_passes_limit(self) -> None:
        """An explicit top_k is forwarded as the search limit."""
        source, _ = _source(top_k=5)
        assert source.top_k == 5
        with patch(
            "agrag.ingestion.resolve.candidate_source.vector_search",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_search:
            await source.global_candidates_for(_mention("Ada"))
        assert mock_search.call_args is not None
        assert mock_search.call_args.kwargs["limit"] == 5


class TestExactMatchLookup:
    """exact_match_lookup mirrors _global_exact_match behavior."""

    async def test_empty_returns_empty(self) -> None:
        """Empty mentions returns empty."""
        store = AsyncMock()
        result = await exact_match_lookup([], graph_store=store)
        assert result == {}
        store.execute_read.assert_not_called()

    async def test_groups_by_label_and_dedups(self) -> None:
        """One query per distinct label, deduped keys."""
        store = AsyncMock()
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
        store.execute_read.side_effect = [
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
        result = await exact_match_lookup([m1, m2, m3], graph_store=store)
        assert result[0].id == eid
        assert result[1].id == eid
        assert 2 not in result
        assert store.execute_read.call_count == 2

    async def test_handles_flat_row_and_missing(self) -> None:
        """Handles flat row form and skips unparsable rows."""
        store = AsyncMock()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        store.execute_read.side_effect = [
            [
                {
                    "id": str(uuid4()),
                    "merge_key": "Person:bob",
                    "name": "Bob",
                },
                {"n": {"id": "bad", "labels": ["Person"], "properties": {}}},
            ]
        ]
        result = await exact_match_lookup([m], graph_store=store)
        assert isinstance(result, dict)

    async def test_handles_no_rows(self) -> None:
        """No rows yields empty map entry."""
        store = AsyncMock()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="NoHit", char_start=0, char_end=5
        )
        store.execute_read.side_effect = [[]]
        result = await exact_match_lookup([m], graph_store=store)
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
        store = AsyncMock()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        tombstone_id = uuid4()
        survivor_id = uuid4()
        store.execute_read.side_effect = [
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
        result = await exact_match_lookup([m], graph_store=store)
        assert result[0].id == survivor_id
        assert result[0].name == "Robert"

    async def test_reingest_resolves_with_driver_shaped_tombstone_row(
        self,
    ) -> None:
        """Reingest still resolves when the tombstone row has no labels key.

        Regression test: a real Neo4j driver's RETURN n never carries a
        labels key -- only _tombstone_row's mock form did, masking a bug
        where the tombstone's own node was parsed into an Entity (to learn
        its label) before its merged_into chain was ever checked. With
        merge_key already stripped by clear_tombstone_merge_keys_query, a
        driver-shaped tombstone row has neither a labels list nor a
        merge_key to derive a label from, so that parse always failed and
        the mention was silently dropped instead of resolving to the
        survivor.
        """
        store = AsyncMock()
        cid = uuid4()
        m = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        tombstone_id = uuid4()
        survivor_id = uuid4()
        store.execute_read.side_effect = [
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
        result = await exact_match_lookup([m], graph_store=store)
        assert result[0].id == survivor_id
        assert result[0].name == "Robert"

    async def test_accepted_alias_with_different_name_resolves_to_entity(
        self,
    ) -> None:
        """A mention resolves via an alias even when it never was the name.

        Regression test: when resolution joins "Bob" and "Robert" into one
        survivor named "Robert", an alias for "Person:bob" is written
        pointing at that entity even though the entity's own name was never
        "Bob". Mapping the returned row back to the "Bob" mention must use
        the merge_key the row's alias was queried on, not one re-derived
        from the entity's current name -- re-deriving would compute
        "Person:robert" and silently fail to map "Bob" at all.
        """
        store = AsyncMock()
        cid = uuid4()
        mention = ExtractedEntity(
            chunk_id=cid, label="Person", text="Bob", char_start=0, char_end=3
        )
        entity_id = uuid4()
        store.execute_read.side_effect = [
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
        result = await exact_match_lookup([mention], graph_store=store)
        assert result[0].id == entity_id
        assert result[0].name == "Robert"

    async def test_transient_chain_read_failure_propagates(self) -> None:
        """A transient error resolving a tombstone chain must not be missed.

        Regression test: _resolve_tombstone_chain used to catch every
        exception from its chain-follow read and return whatever survivor it
        had so far (None on the first hop). _global_exact_match then treated
        that as "no match" and the caller would create a duplicate entity for
        an already-known name instead of surfacing the failure.
        """
        store = AsyncMock()
        tombstone_id = uuid4()
        survivor_id = uuid4()
        mention = ExtractedEntity(
            chunk_id=uuid4(), label="Person", text="Bob", char_start=0, char_end=3
        )
        first_response = [
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
        store.execute_read.side_effect = [
            first_response,
            ConnectionError("simulated transient DB error"),
        ]
        with pytest.raises(ConnectionError, match="simulated transient DB error"):
            await exact_match_lookup([mention], graph_store=store)
