"""Errors that the embedding layer raises."""


class EmbeddingError(Exception):
    """The base class for every embedding error."""


class EmbeddingMissingExtraError(EmbeddingError):
    """An embedder exists, but its package extra is not installed.

    Attributes:
        extra: The name of the package extra to install.
    """

    def __init__(self, extra: str) -> None:
        """Bind the missing extra's name to the error."""
        super().__init__(
            f"needs the {extra!r} extra: pip install 'agentic-graphrag[{extra}]'"
        )
        self.extra = extra


class EmbeddingDimensionMismatchError(EmbeddingError):
    """A stored collection or index expects a different embedding dimension.

    Attributes:
        expected: The dimension the collection or index was created with.
        actual: The dimension the embedder actually produces.
    """

    def __init__(self, *, expected: int, actual: int) -> None:
        """Bind the expected and actual dimensions to the error."""
        super().__init__(f"expected dimension {expected}, embedder produces {actual}")
        self.expected = expected
        self.actual = actual
