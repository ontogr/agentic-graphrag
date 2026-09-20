"""Tests for the community_context enrichment helper."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agrag.common.data_models.community import Community
from agrag.common.data_models.entity import Entity
from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.community_context import (
    community_context,
    expand_with_communities,
)
from agrag.retrieval.filters import SearchFilters


class TestCommunityContext:
    """community_context ranks by overlap and caps at top_k."""

    async def test_empty_short_circuit(self) -> None:
        """Empty entity_ids short-circuits with no store call."""
        mock_store = AsyncMock()
        res = await community_context([], graph_store=mock_store)
        assert res == []
        mock_store.execute_read.assert_not_called()

    async def test_zero_top_k_returns_empty_without_querying(self) -> None:
        """top_k=0 returns no results and never queries the store."""
        mock_store = AsyncMock()
        res = await community_context([uuid4()], graph_store=mock_store, top_k=0)
        assert res == []
        mock_store.execute_read.assert_not_called()

    async def test_negative_top_k_returns_empty_without_querying(self) -> None:
        """A negative top_k returns no results and never queries the store.

        Regression test: a negative top_k reached Neo4j as a negative LIMIT,
        which rejects the query.
        """
        mock_store = AsyncMock()
        res = await community_context([uuid4()], graph_store=mock_store, top_k=-1)
        assert res == []
        mock_store.execute_read.assert_not_called()

    async def test_top_k_capping(self) -> None:
        """top_k limits returned communities."""
        mock_store = AsyncMock()
        c1, c2 = uuid4(), uuid4()
        rows = [
            {
                "c": {
                    "id": str(c1),
                    "title": "T1",
                    "summary": "S1",
                    "rating": 5,
                    "rating_explanation": "e",
                },
                "overlap": 5,
            },
            {
                "c": {
                    "id": str(c2),
                    "title": "T2",
                    "summary": "S2",
                    "rating": 5,
                    "rating_explanation": "e",
                },
                "overlap": 3,
            },
            {
                "c": {
                    "id": str(uuid4()),
                    "title": "T3",
                    "summary": "S3",
                    "rating": 5,
                    "rating_explanation": "e",
                },
                "overlap": 1,
            },
        ]
        mock_store.execute_read.return_value = rows
        res = await community_context([uuid4()], graph_store=mock_store, top_k=2)
        assert len(res) == 2
        assert res[0].score == 5

    async def test_overlap_ranking_and_parse(self) -> None:
        """Highest overlap first and parsable nodes."""
        mock_store = AsyncMock()
        cid = uuid4()
        mock_store.execute_read.return_value = [
            {
                "c": {
                    "id": str(cid),
                    "title": "T",
                    "summary": "S",
                    "rating": 5,
                    "rating_explanation": "e",
                },
                "overlap": 2,
            }
        ]
        res = await community_context([uuid4()], graph_store=mock_store, top_k=3)
        assert len(res) == 1
        assert isinstance(res[0].item, Community)

    async def test_unparsable_rows_are_skipped(self) -> None:
        """A row that fails to parse into a Community is skipped, not raised."""
        mock_store = AsyncMock()
        cid = uuid4()
        mock_store.execute_read.return_value = [
            {
                "c": {"id": "not-a-uuid", "title": "Bad", "summary": "", "rating": 0},
                "overlap": 9,
            },
            {
                "c": {
                    "id": str(cid),
                    "title": "Good",
                    "summary": "S",
                    "rating": 5,
                    "rating_explanation": "e",
                },
                "overlap": 2,
            },
        ]
        res = await community_context([uuid4()], graph_store=mock_store, top_k=5)
        assert len(res) == 1
        assert res[0].item.title == "Good"

    async def test_rows_missing_overlap_are_skipped(self) -> None:
        """A row without an overlap score does not stop later valid results."""
        entity_id = uuid4()
        community_id = uuid4()
        mock_store = AsyncMock()
        mock_store.execute_read.return_value = [
            {"c": {"id": str(community_id), "title": "Missing score"}},
            {
                "c": {"id": str(community_id), "title": "Valid"},
                "overlap": 2,
            },
        ]

        results = await community_context([entity_id], graph_store=mock_store)

        assert len(results) == 1
        assert results[0].item.title == "Valid"

    async def test_document_scoped_filters_reach_the_query(self) -> None:
        """document_ids/properties filters constrain the community node.

        Regression test: community expansion used to ignore filters
        entirely, so a document- or property-scoped search could enrich
        results with a community report drawn from outside that scope.
        """
        mock_store = AsyncMock()
        mock_store.execute_read.return_value = []
        filters = SearchFilters(document_ids=["doc-1"], properties={"tenant": "a"})

        await community_context(
            [uuid4()], graph_store=mock_store, top_k=2, filters=filters
        )

        query, params = mock_store.execute_read.call_args.args
        assert "WHERE" in query
        assert params["filter_document_id"] == ["doc-1"]
        assert params["filter_tenant"] == "a"

    async def test_label_filters_are_not_applied_to_communities(self) -> None:
        """A labels-only filter does not suppress community enrichment.

        Community nodes never carry an entity label, so passing labels
        through to_cypher_where would always exclude every community.
        """
        mock_store = AsyncMock()
        mock_store.execute_read.return_value = []
        filters = SearchFilters(labels=["Person"])

        await community_context(
            [uuid4()], graph_store=mock_store, top_k=2, filters=filters
        )

        query, _params = mock_store.execute_read.call_args.args
        assert "WHERE" not in query


class TestExpandWithCommunities:
    """expand_with_communities fuses overlapping reports into a result list."""

    async def test_expand_with_communities_fuses_community_results_into_fused_list(
        self,
    ) -> None:
        """Non-empty community results are fused into the caller's list."""
        entity = Entity(id=uuid4(), label="Person", name="Alice")
        fused = [SearchResult(item=entity, score=1.0, method="entity")]
        community = Community(
            id=uuid4(),
            title="T",
            summary="S",
            rating=5.0,
            rating_explanation="because",
        )

        with patch(
            "agrag.retrieval.community_context.community_context",
            AsyncMock(
                return_value=[
                    SearchResult(item=community, score=5.0, method="community")
                ]
            ),
        ):
            results = await expand_with_communities(
                fused,
                [entity.id],
                graph_store=AsyncMock(),
                top_k=3,
                filters=None,
                rrf_k=60,
            )

        assert any(result.item.id == community.id for result in results)
        assert any(result.item.id == entity.id for result in results)

    async def test_expand_with_communities_respects_top_k(self) -> None:
        """The caller's top_k reaches the community lookup."""
        with patch(
            "agrag.retrieval.community_context.community_context",
            AsyncMock(return_value=[]),
        ) as lookup:
            await expand_with_communities(
                [],
                [uuid4()],
                graph_store=AsyncMock(),
                top_k=2,
                filters=None,
                rrf_k=60,
            )

        assert lookup.call_args.kwargs["top_k"] == 2

    async def test_expand_with_communities_passes_filters_through(self) -> None:
        """The caller's scope reaches the community lookup unchanged."""
        filters = SearchFilters(document_ids=["doc-1"])
        with patch(
            "agrag.retrieval.community_context.community_context",
            AsyncMock(return_value=[]),
        ) as lookup:
            await expand_with_communities(
                [],
                [uuid4()],
                graph_store=AsyncMock(),
                top_k=3,
                filters=filters,
                rrf_k=60,
            )

        assert lookup.call_args.kwargs["filters"] is filters

    async def test_expand_with_communities_failure_keeps_fused_results(self) -> None:
        """A community lookup failure returns the fused list unchanged."""
        entity = Entity(id=uuid4(), label="Person", name="Alice")
        fused = [SearchResult(item=entity, score=1.0, method="entity")]

        with patch(
            "agrag.retrieval.community_context.community_context",
            AsyncMock(side_effect=RuntimeError("community store unavailable")),
        ):
            results = await expand_with_communities(
                fused,
                [entity.id],
                graph_store=AsyncMock(),
                top_k=3,
                filters=None,
                rrf_k=60,
            )

        assert results == fused
