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


class GraphStoreAliasConflictError(GraphStoreConstraintViolationError):
    """A merge-key alias a merge tried to claim already names another entity.

    Unlike the base class, this is not surfaced by the backend's own
    uniqueness constraint -- claiming an already-owned alias is a silent
    no-op at the database level (see ``upsert_merge_alias_query``) -- so
    ``apply_merge`` detects it itself from the claim's own return rows and
    raises this instead. For example, one writer creates a canonical entity
    named "Bob" while a concurrent writer separately resolves "Bob" as an
    accepted alias of a different canonical entity named "Robert": neither
    writer's own node merge_key collides, so recovery must come from here,
    not from a constraint violation.

    Attributes:
        conflicts: Every accepted merge_key this claim found already owned,
            mapped to the entity id that owns it.
    """

    def __init__(self, conflicts: dict[str, str]) -> None:
        """Bind the conflicting merge_key -> owning-entity-id map."""
        super().__init__(
            f"merge_key alias already claimed by another entity: {conflicts}"
        )
        self.conflicts = conflicts


class GraphStoreDataIntegrityError(GraphStoreError):
    """A read found the graph store in a state its own invariants forbid.

    Raised when persisted data cannot be trusted at face value -- for
    example a ``merged_into`` tombstone chain that cycles, points at a
    missing node, or runs past its expected bound without reaching a live
    node. Returning the last-seen data in these cases would let a caller
    silently act on a tombstone instead of the entity it was absorbed into.
    """


__all__ = [
    "GraphStoreAliasConflictError",
    "GraphStoreConstraintViolationError",
    "GraphStoreDataIntegrityError",
    "GraphStoreError",
    "GraphStoreMissingExtraError",
]
