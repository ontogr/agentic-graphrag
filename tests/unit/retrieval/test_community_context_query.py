"""Tests for the community_context enrichment helper."""

from unittest.mock import AsyncMock
from uuid import uuid4

from agrag.common.data_models.community import Community
from agrag.retrieval.community_context import community_context
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
