"""Shared fixtures for the schema format tests."""

from pathlib import Path

import pytest

from agrag.common.data_models.graph_schema import (
    Cardinality,
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def company_schema() -> GraphSchema:
    """A schema that uses every element the formats map.

    It has a parent, a required property, an enum property, a date property,
    a symmetric relation and a relation with a limit of one per source.
    The email property has a description.
    """
    return GraphSchema(
        name="company",
        version="2",
        entities=[
            EntityType(
                label="Company",
                description="A for-profit organization.",
                parents=["Organization"],
                properties={
                    "status": PropertySpec(
                        type="string", required=True, enum=["active", "dissolved"]
                    )
                },
            ),
            EntityType(label="Organization", description="A company or institution."),
            EntityType(
                label="Person",
                description="A named individual.",
                properties={
                    "born": PropertySpec(type="date"),
                    "email": PropertySpec(
                        type="string", required=True, description="Work email address."
                    ),
                },
            ),
        ],
        relations=[
            RelationType(
                label="COLLEAGUE_OF",
                description="Two people work together.",
                patterns=[("Person", "Person")],
                symmetric=True,
            ),
            RelationType(
                label="WORKS_FOR",
                description="A person is employed by an organization.",
                patterns=[("Person", "Organization")],
                cardinality=Cardinality(max_per_source=1),
            ),
        ],
    )
