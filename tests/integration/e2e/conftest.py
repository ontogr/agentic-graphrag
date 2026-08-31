"""Module-scoped fixtures for the e2e suite.

These fixtures are shared across every test function in the suite so the
extraction model and Neo4j connection are each set up once. The fixtures
provide a small purpose-built schema and a record of the e2e directory's
existence for marker/auto-mark tests.
"""

import pytest

from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType


@pytest.fixture(scope="module")
def e2e_schema() -> GraphSchema:
    """Return a small purpose-built schema for e2e tests."""
    return GraphSchema(
        name="e2e",
        version="1",
        entities=[
            EntityType(label="Person", description="A person."),
            EntityType(label="Organization", description="An organization."),
        ],
        relations=[
            RelationType(
                label="WORKS_AT",
                description="A person works at an organization.",
                patterns=[("Person", "Organization")],
            ),
        ],
    )
