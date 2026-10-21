"""Search reports an unavailable index instead of a false empty result."""

from unittest.mock import AsyncMock

from agrag.common.data_models.evidence import (
    EvidenceSearchMode,
    EvidenceSearchStatus,
    IndexState,
)
from agrag.evidence.search import search_evidence
from agrag.graphdb.base import GraphStore


class TestIndexReadiness:
    """Index state gates evidence search."""

    async def test_semantic_search_reports_missing_index(self) -> None:
        """A missing vector index does not appear as a no-match result."""
        store = AsyncMock(spec=GraphStore)
        store.execute_read.return_value = []

        result = await search_evidence(
            store,
            AsyncMock(),
            "search phrase",
            mode=EvidenceSearchMode.SEMANTIC,
            limit=5,
            scope=frozenset({"doc://one"}),
        )

        assert result.status is EvidenceSearchStatus.INDEX_NOT_READY
        assert result.index_state is IndexState.NOT_READY
        assert result.hits == []
