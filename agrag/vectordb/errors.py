"""Errors that the vector-store layer raises."""


class VectorStoreError(Exception):
    """The base class for every vector-store error."""


class VectorStoreMissingExtraError(VectorStoreError):
    """A vector store exists, but its package extra is not installed.

    Attributes:
        extra: The name of the package extra to install.
    """

    def __init__(self, extra: str) -> None:
        """Bind the missing extra's name to the error."""
        super().__init__(
            f"needs the {extra!r} extra: pip install 'agentic-graphrag[{extra}]'"
        )
        self.extra = extra


class CollectionDimensionMismatchError(VectorStoreError):
    """A collection already exists with a different embedding dimension.

    Attributes:
        expected: The dimension the collection was created with.
        actual: The dimension the caller requested.
    """

    def __init__(self, *, expected: int, actual: int) -> None:
        """Bind the expected and actual dimensions to the error."""
        super().__init__(
            f"collection expects dimension {expected}, but {actual} was requested"
        )
        self.expected = expected
        self.actual = actual


__all__ = [
    "CollectionDimensionMismatchError",
    "VectorStoreError",
    "VectorStoreMissingExtraError",
]
