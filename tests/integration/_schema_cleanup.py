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
    safe_names = {validate_identifier(name) for name in names}
    if not safe_names:
        return

    constraints = await store.execute_read(
        "SHOW CONSTRAINTS YIELD name, labelsOrTypes RETURN name, labelsOrTypes"
    )
    for row in constraints:
        labels_or_types = row["labelsOrTypes"]
        if not isinstance(labels_or_types, list):
            continue
        if not safe_names.intersection(labels_or_types):
            continue
        object_name = row["name"]
        if isinstance(object_name, str) and is_safe_identifier(object_name):
            await store.execute_write(f"DROP CONSTRAINT {object_name} IF EXISTS")

    indexes = await store.execute_read(
        "SHOW INDEXES YIELD name, labelsOrTypes, owningConstraint "
        "RETURN name, labelsOrTypes, owningConstraint"
    )
    for row in indexes:
        if row["owningConstraint"] is not None:
            continue
        labels_or_types = row["labelsOrTypes"]
        if not isinstance(labels_or_types, list):
            continue
        if not safe_names.intersection(labels_or_types):
            continue
        object_name = row["name"]
        if isinstance(object_name, str) and is_safe_identifier(object_name):
            await store.execute_write(f"DROP INDEX {object_name} IF EXISTS")
