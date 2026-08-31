"""Errors that the graph-store layer raises."""


class GraphStoreError(Exception):
    """The base class for every graph-store error."""


class GraphStoreMissingExtraError(GraphStoreError):
    """A graph store exists, but its package extra is not installed.

    Attributes:
        extra: The name of the package extra to install.
    """

    def __init__(self, extra: str) -> None:
        """Bind the missing extra's name to the error."""
        super().__init__(
            f"needs the {extra!r} extra: pip install 'agentic-graphrag[{extra}]'"
        )
        self.extra = extra


class GraphStoreConstraintViolationError(GraphStoreError):
    """A write violated a uniqueness constraint the backend enforces.

    Raised instead of letting the backend's own driver exception propagate,
    so callers can recognize this specific case -- for example, two
    concurrent writers both missing an exact-match lookup and racing to
    create the same ``merge_key`` -- and recover by re-resolving to
    whichever write landed first, rather than treating it as a fatal error.
    """


class GraphStoreDataIntegrityError(GraphStoreError):
    """A read found the graph store in a state its own invariants forbid.

    Raised when persisted data cannot be trusted at face value -- for
    example a ``merged_into`` tombstone chain that cycles, points at a
    missing node, or runs past its expected bound without reaching a live
    node. Returning the last-seen data in these cases would let a caller
    silently act on a tombstone instead of the entity it was absorbed into.
    """


__all__ = [
    "GraphStoreConstraintViolationError",
    "GraphStoreDataIntegrityError",
    "GraphStoreError",
    "GraphStoreMissingExtraError",
]
