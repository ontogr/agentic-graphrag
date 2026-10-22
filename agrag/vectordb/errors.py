"""Errors exposed by external vector indexes."""


class VectorStoreError(Exception):
    """An external vector index operation failed."""


class VectorStoreMissingExtraError(VectorStoreError):
    """The selected vector store's optional client is not installed."""

    def __init__(self, name: str) -> None:
        """Describe the extra needed for the selected store."""
        self.extra = name
        super().__init__(
            f"needs the {name!r} extra: pip install 'agentic-graphrag[{name}]'"
        )


class CollectionMismatchError(VectorStoreError):
    """An existing collection has incompatible dimensions or distance."""


class VectorPlacementError(VectorStoreError):
    """The requested vector placement disagrees with the graph's recorded placement."""
