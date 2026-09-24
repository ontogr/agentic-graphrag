"""Removes the Neo4j schema objects that integration tests create per label.

Tests give every node label and relationship type a unique suffix so that they
can share one database. Deleting a test's nodes leaves its uniqueness
constraints and indexes behind, and the store re-checks every label already in
the database each time a graph opens. Tests call ``drop_schema_for`` in their
teardown so a long run does not slow down as it goes.
"""

from agrag.cypher.entities import is_safe_identifier, validate_identifier
from agrag.graphdb.base import GraphStore


async def drop_schema_for(store: GraphStore, *names: str) -> None:
    """Drop safely named constraints and indexes for the given labels or types.

    Only safely named objects whose label or relationship type is in ``names``
    are touched. Missing objects are ignored, so the call is safe in a
    ``finally`` block.

    Args:
        store: A connected graph store.
        *names: Node labels or relationship types the test created.
    """
    for name in names:
        safe = validate_identifier(name)
        for kind, query in (
            (
                "CONSTRAINT",
                "SHOW CONSTRAINTS YIELD name, labelsOrTypes "
                "WHERE $name IN labelsOrTypes RETURN name",
            ),
            (
                "INDEX",
                "SHOW INDEXES YIELD name, labelsOrTypes, owningConstraint "
                "WHERE $name IN labelsOrTypes AND owningConstraint IS NULL RETURN name",
            ),
        ):
            rows = await store.execute_read(query, {"name": safe})
            for row in rows:
                object_name = row["name"]
                if not isinstance(object_name, str):
                    continue
                if not is_safe_identifier(object_name):
                    continue
                await store.execute_write(f"DROP {kind} {object_name} IF EXISTS")
