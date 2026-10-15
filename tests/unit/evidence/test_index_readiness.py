"""Discovery reports an unavailable index instead of a false empty result."""

from unittest.mock import AsyncMock

from agrag.common.data_models.evidence import (
    DiscoveryMode,
    DiscoveryStatus,
    IndexState,
)
from agrag.evidence.discover import discover
from agrag.graphdb.base import GraphStore


class TestIndexReadiness:
    """Index state gates evidence discovery."""

    async def test_semantic_discovery_reports_missing_index(self) -> None:
        """A missing vector index does not appear as a no-match result."""
        store = AsyncMock(spec=GraphStore)
        store.execute_read.return_value = []

        result = await discover(
            store,
            AsyncMock(),
            "search phrase",
            mode=DiscoveryMode.SEMANTIC,
            limit=5,
            scope=frozenset({"doc://one"}),
        )

        assert result.status is DiscoveryStatus.INDEX_NOT_READY
        assert result.index_state is IndexState.NOT_READY
        assert result.hits == []
