"""Index methods for in-memory graph stores that hold no indexes."""

from collections.abc import Sequence

from agrag.common.data_models.index_record import IndexInfo, SearchCall


class NoIndexesMixin:
    """Reports an empty index list, so index-readiness waits return at once."""

    async def list_indexes(self, *, timeout: float | None = None) -> list[IndexInfo]:
        """Return no indexes."""
        del timeout
        return []

    async def ensure_unique_constraint(
        self, *, label: str, properties: Sequence[str]
    ) -> None:
        """Accept the constraint; the fake enforces none."""
        del label, properties

    async def fulltext_search_call(
        self, *, label: str, properties: Sequence[str]
    ) -> SearchCall:
        """Return a placeholder search fragment."""
        del label, properties
        return SearchCall("CALL fulltext() YIELD node, score")

    async def vector_search_call(
        self, *, label: str, vector_property: str
    ) -> SearchCall:
        """Return a placeholder search fragment."""
        del label, vector_property
        return SearchCall("CALL vector() YIELD node, score")
