"""Tests for fetch_relation_edges weight and pagination."""

from unittest.mock import AsyncMock

from agrag.ingestion.community import fetch_relation_edges


class TestFetchRelationEdges:
    """fetch_relation_edges weight and pagination."""

    async def test_weight_attestation_and_fallback(self) -> None:
        """Weight is len(source_chunk_ids); an unattested relation weighs 0.0."""
        mock_store = AsyncMock()
        mock_store.execute_read.return_value = [
            {
                "source_id": "a",
                "target_id": "b",
                "source_chunk_ids": ["x", "y"],
                "rel_type": "KNOWS",
                "rel_id": "r1",
            },
            {
                "source_id": "c",
                "target_id": "d",
                "source_chunk_ids": [],
                "rel_type": "KNOWS",
                "rel_id": "r2",
            },
        ]
        edges = await fetch_relation_edges(mock_store, page_size=10)
        assert edges[0][2] == 2.0
        assert edges[1][2] == 0.0

    async def test_pagination(self) -> None:
        """Pagination loops until fewer than page_size.

        The next page's cursor resumes from the last row's full keyset,
        not just (source_id, target_id).
        """
        mock_store = AsyncMock()
        mock_store.execute_read.side_effect = [
            [
                {
                    "source_id": str(i),
                    "target_id": str(i + 1),
                    "source_chunk_ids": ["x"],
                    "rel_type": "KNOWS",
                    "rel_id": f"r{i}",
                }
                for i in range(5)
            ],
            [
                {
                    "source_id": "done",
                    "target_id": "done2",
                    "source_chunk_ids": ["y"],
                    "rel_type": "KNOWS",
                    "rel_id": "r5",
                }
            ],
        ]
        edges = await fetch_relation_edges(mock_store, page_size=5)
        assert len(edges) == 6
        assert mock_store.execute_read.call_count == 2
        second_call_params = mock_store.execute_read.call_args_list[1].args[1]
        assert second_call_params["last_a"] == "4"
        assert second_call_params["last_b"] == "5"
        assert second_call_params["last_type"] == "KNOWS"
        assert second_call_params["last_rel_id"] == "r4"

    async def test_use_cursor_false_uses_skip_pagination(self) -> None:
        """use_cursor=False pages via SKIP and still computes weights."""
        mock_store = AsyncMock()
        mock_store.execute_read.side_effect = [
            [
                {
                    "source_id": str(i),
                    "target_id": str(i + 1),
                    "source_chunk_ids": ["x"],
                    "rel_type": "KNOWS",
                }
                for i in range(5)
            ],
            [
                {
                    "source_id": "done",
                    "target_id": "done2",
                    "source_chunk_ids": [],
                    "rel_type": "KNOWS",
                }
            ],
        ]
        edges = await fetch_relation_edges(mock_store, page_size=5, use_cursor=False)
        assert len(edges) == 6
        assert edges[-1] == ("done", "done2", 0.0, "KNOWS")
        assert mock_store.execute_read.call_count == 2
        first_call_params = mock_store.execute_read.call_args_list[0].args[1]
        assert first_call_params == {"skip": 0, "limit": 5}
        second_call_params = mock_store.execute_read.call_args_list[1].args[1]
        assert second_call_params == {"skip": 5, "limit": 5}

    async def test_use_cursor_false_stops_on_empty_page(self) -> None:
        """SKIP pagination stops once a page returns no rows."""
        mock_store = AsyncMock()
        mock_store.execute_read.return_value = []
        edges = await fetch_relation_edges(mock_store, page_size=5, use_cursor=False)
        assert edges == []
        assert mock_store.execute_read.call_count == 1

    async def test_pagination_resumes_past_shared_endpoint_group(self) -> None:
        """A page boundary inside a same-(a,b) group still yields every row.

        Regression test: the cursor used to advance only by
        (source_id, target_id), so a page ending mid-group silently
        excluded the remaining parallel relations between that pair.
        """
        mock_store = AsyncMock()
        mock_store.execute_read.side_effect = [
            [
                {
                    "source_id": "a",
                    "target_id": "b",
                    "source_chunk_ids": ["x"],
                    "rel_type": "KNOWS",
                    "rel_id": "r1",
                }
            ],
            [
                {
                    "source_id": "a",
                    "target_id": "b",
                    "source_chunk_ids": ["y"],
                    "rel_type": "WORKS_WITH",
                    "rel_id": "r2",
                }
            ],
            [],
        ]
        edges = await fetch_relation_edges(mock_store, page_size=1)
        assert len(edges) == 2
        second_call_params = mock_store.execute_read.call_args_list[1].args[1]
        assert second_call_params["last_a"] == "a"
        assert second_call_params["last_b"] == "b"
        assert second_call_params["last_type"] == "KNOWS"
        assert second_call_params["last_rel_id"] == "r1"
