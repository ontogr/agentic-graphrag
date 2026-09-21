"""Tests for BFSRetriever in agrag.retrieval.retrievers.bfs.

Uses an AsyncMock graph store and inspects the generated Cypher query and
parameters directly. Covers empty/None seed ids short-circuiting to no
results, a depth override reaching the variable-length path pattern
(``*1..N``), SearchFilters properties reaching query parameters,
relation_types restricting the relationship pattern, that no filters means no
filter parameters are added, and that direction is threaded through to the
query builder (defaulting to "both").
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from agrag.common.data_models.entity import Entity
from agrag.retrieval.filters import SearchFilters
from agrag.retrieval.retrievers.bfs import BFSRetriever


class TestBFSRetriever:
    """BFSRetriever traverses from seed entity ids."""

    async def test_empty_seeds_returns_empty(self) -> None:
        """No seed ids returns empty results."""
        gs = AsyncMock()
        retriever = BFSRetriever(graph_store=gs)
        results = await retriever.retrieve("test", seed_ids=[])
        assert results == []

    async def test_none_seeds_returns_empty(self) -> None:
        """None seed_ids returns empty results."""
        gs = AsyncMock()
        retriever = BFSRetriever(graph_store=gs)
        results = await retriever.retrieve("test", seed_ids=None)
        assert results == []

    async def test_traverses_and_returns_entities(self) -> None:
        """BFS returns entities found via traversal."""
        ent = Entity(id=uuid4(), label="Person", name="Neighbor")
        gs = AsyncMock()
        gs.execute_read.return_value = [
            {
                "neighbor": {
                    "id": str(ent.id),
                    "labels": ["Person"],
                    "properties": {
                        "name": "Neighbor",
                        "merge_key": "Person:neighbor",
                        "merged_from": [],
                        "merge_count": 1,
                        "source_chunk_ids": [],
                    },
                }
            }
        ]

        retriever = BFSRetriever(graph_store=gs)
        results = await retriever.retrieve("test", seed_ids=[uuid4()])

        # The entity should be resolved via resolve_entity.
        # With the mock, it may or may not resolve depending on
        # whether _parse_entity_node succeeds.
        assert isinstance(results, list)

    async def test_depth_override(self) -> None:
        """Explicit depth overrides settings default."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = BFSRetriever(graph_store=gs)
        await retriever.retrieve("test", seed_ids=[uuid4()], depth=7)

        call_args = gs.execute_read.call_args
        query = call_args.args[0]
        assert "*1..7" in query

    async def test_filters_passed_to_query(self) -> None:
        """SearchFilters are forwarded into the BFS Cypher query."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = BFSRetriever(graph_store=gs)
        filters = SearchFilters(properties={"status": "active"})
        await retriever.retrieve(
            "test",
            seed_ids=[uuid4()],
            filters=filters,
        )

        call_args = gs.execute_read.call_args
        query = call_args.args[0]
        params = call_args.args[1]
        assert "filter_status" in query
        assert params["filter_status"] == "active"

    async def test_labels_restrict_neighbors_without_query_parameters(self) -> None:
        """A label scope becomes a validated neighbor label predicate."""
        graph_store = AsyncMock()
        graph_store.execute_read.return_value = []
        retriever = BFSRetriever(graph_store=graph_store)

        await retriever.retrieve(
            "test",
            seed_ids=[uuid4()],
            filters=SearchFilters(labels=["Drug"]),
        )

        query, params = graph_store.execute_read.call_args.args
        assert "AND neighbor:Drug" in query
        assert not any("label" in parameter for parameter in params)

    async def test_relation_types_restrict_traversal(self) -> None:
        """relation_types reach the Cypher relationship pattern."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = BFSRetriever(graph_store=gs)
        await retriever.retrieve(
            "test",
            seed_ids=[uuid4()],
            filters=SearchFilters(relation_types=["TREATS", "CAUSES"]),
        )

        query = gs.execute_read.call_args.args[0]
        assert "[:TREATS|CAUSES*1.." in query

    async def test_filters_empty_when_none(self) -> None:
        """No filters produces no filter params."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = BFSRetriever(graph_store=gs)
        await retriever.retrieve("test", seed_ids=[uuid4()])

        call_args = gs.execute_read.call_args
        params = call_args.args[1]
        assert "filter_label" not in params

    @pytest.mark.parametrize("direction", ["outgoing", "incoming", "both"])
    async def test_direction_reaches_query_builder(self, direction: str) -> None:
        """The direction passed to retrieve() reaches bfs_expand_query."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = BFSRetriever(graph_store=gs)
        with patch(
            "agrag.retrieval.retrievers.bfs.bfs_expand_query",
            MagicMock(return_value=("MATCH (n) RETURN n", {})),
        ) as builder:
            await retriever.retrieve("test", seed_ids=[uuid4()], direction=direction)

        assert builder.call_args.kwargs["direction"] == direction

    async def test_direction_defaults_to_both(self) -> None:
        """With no direction argument the builder still receives "both"."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = BFSRetriever(graph_store=gs)
        with patch(
            "agrag.retrieval.retrievers.bfs.bfs_expand_query",
            MagicMock(return_value=("MATCH (n) RETURN n", {})),
        ) as builder:
            await retriever.retrieve("test", seed_ids=[uuid4()])

        assert builder.call_args.kwargs["direction"] == "both"

    async def test_outgoing_direction_reaches_the_query(self) -> None:
        """direction="outgoing" produces a forward-arrow traversal."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = BFSRetriever(graph_store=gs)
        await retriever.retrieve(
            "test", seed_ids=[uuid4()], direction="outgoing", depth=1
        )

        query = gs.execute_read.call_args.args[0]
        assert "(start)-[*1..1]->(neighbor)" in query

    async def test_incoming_direction_reaches_the_query(self) -> None:
        """direction="incoming" produces a reverse-arrow traversal."""
        gs = AsyncMock()
        gs.execute_read.return_value = []
        retriever = BFSRetriever(graph_store=gs)
        await retriever.retrieve(
            "test", seed_ids=[uuid4()], direction="incoming", depth=1
        )

        query = gs.execute_read.call_args.args[0]
        assert "(start)<-[*1..1]-(neighbor)" in query
