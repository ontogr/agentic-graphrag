"""Abstract base class for retrieval methods."""

from abc import ABC, abstractmethod

from agrag.common.data_models.search_result import SearchResult
from agrag.retrieval.filters import SearchFilters


class Retriever(ABC):
    """One retrieval method: given a query, return SearchResults.

    Subclasses own exactly one strategy (dense entity search, chunk
    search, BFS expansion). SearchEngine fans a query out to every
    Retriever a Recipe names and hands the combined output to Fusion.
    """

    name: str

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        *,
        filters: SearchFilters | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Run this retrieval method and return hydrated results."""
