"""Removes the Neo4j schema objects that integration tests create per label.

Tests give every node label and relationship type a unique suffix so that they
can share one database. Deleting a test's nodes leaves its uniqueness
constraints and indexes behind, and the store re-checks every label already in
the database each time a graph opens. Tests call ``drop_schema_for`` in their
teardown so a long run does not slow down as it goes.
"""

from agrag.cypher.entities import validate_identifier
from agrag.graphdb.base import GraphStore


async def drop_schema_for(store: GraphStore, *names: str) -> None:
    """Drop every constraint and index defined on the given labels or types.

    Only objects whose label or relationship type is in ``names`` are touched.
    Missing objects are ignored, so the call is safe in a ``finally`` block.

    Args:
        store: A connected graph store.
        *names: Node labels or relationship types the test created.
    """
    for name in names:
        safe = validate_identifier(name)
        for kind, listing in (
            ("CONSTRAINT", "SHOW CONSTRAINTS YIELD name, labelsOrTypes"),
            ("INDEX", "SHOW INDEXES YIELD name, labelsOrTypes"),
        ):
            rows = await store.execute_read(
                f"{listing} WHERE $name IN labelsOrTypes RETURN name", {"name": safe}
            )
            for row in rows:
                object_name = validate_identifier(row["name"])
                await store.execute_write(f"DROP {kind} {object_name} IF EXISTS")
