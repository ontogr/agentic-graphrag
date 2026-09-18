"""Tests for delete_all_communities batching."""

from unittest.mock import AsyncMock

from agrag.ingestion.community import delete_all_communities


class TestDeleteAllCommunities:
    """delete_all_communities batches until fewer than batch_size."""

    async def test_loops_multi_batch(self) -> None:
        """More than one batch when first batch is full."""
        mock_store = AsyncMock()
        mock_store.execute_write.side_effect = [[{"deleted": 1000}], [{"deleted": 500}]]
        await delete_all_communities(mock_store, batch_size=1000)
        assert mock_store.execute_write.call_count == 2

    async def test_stops_on_first_short_batch(self) -> None:
        """Stops immediately when first batch fewer than batch_size."""
        mock_store = AsyncMock()
        mock_store.execute_write.return_value = [{"deleted": 3}]
        await delete_all_communities(mock_store, batch_size=1000)
        assert mock_store.execute_write.call_count == 1
