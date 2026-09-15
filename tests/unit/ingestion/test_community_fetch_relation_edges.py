"""Tests for fetch_relation_edges weight and pagination."""

from unittest.mock import AsyncMock

from agrag.ingestion.community import fetch_relation_edges


class TestFetchRelationEdges:
    """fetch_relation_edges weight and pagination."""

    async def test_weight_attestation_and_fallback(self) -> None:
        """Weight is len(source_chunk_ids) or 1.0."""
        mock_store = AsyncMock()
        mock_store.execute_read.return_value = [
            {"source_id": "a", "target_id": "b", "source_chunk_ids": ["x", "y"]},
            {"source_id": "c", "target_id": "d", "source_chunk_ids": []},
        ]
        edges = await fetch_relation_edges(mock_store, page_size=10)
        assert edges[0][2] == 2.0
        assert edges[1][2] == 1.0

    async def test_pagination(self) -> None:
        """Pagination loops until fewer than page_size."""
        mock_store = AsyncMock()
        mock_store.execute_read.side_effect = [
            [
                {
                    "source_id": str(i),
                    "target_id": str(i + 1),
                    "source_chunk_ids": ["x"],
                }
                for i in range(5)
            ],
            [{"source_id": "done", "target_id": "done2", "source_chunk_ids": ["y"]}],
        ]
        edges = await fetch_relation_edges(mock_store, page_size=5)
        assert len(edges) == 6
        assert mock_store.execute_read.call_count == 2
