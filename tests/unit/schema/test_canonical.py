"""Tests for the canonical dump and the load round trip."""

import random

import pytest

from agrag.common.data_models.default_schema import DEFAULT_SCHEMA
from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)
from agrag.common.data_models.presets import LEGAL, OPERATIONS
from agrag.schema import dump_schema, load_schema


def _random_schema(seed: int) -> GraphSchema:
    """Build a deterministic schema that exercises hierarchy and properties."""
    rng = random.Random(seed)
    labels = [f"Type{i}" for i in range(rng.randint(1, 8))]
    entities = []
    for index, label in enumerate(labels):
        parents = rng.sample(labels[:index], k=rng.randint(0, min(2, index)))
        properties = {
            f"prop{j}": PropertySpec(
                type=rng.choice(["string", "integer", "date"]),
                required=rng.random() < 0.5,
            )
            for j in range(rng.randint(0, 3))
        }
        entities.append(
            EntityType(
                label=label,
                description=rng.choice(["", "A thing."]),
                parents=parents,
                properties=properties,
            )
        )
    relations = []
    for number in range(rng.randint(0, 4)):
        pairs = {
            (rng.choice(labels), rng.choice(labels)) for _ in range(rng.randint(1, 3))
        }
        relations.append(
            RelationType(label=f"REL_{number}", description="", patterns=sorted(pairs))
        )
    return GraphSchema(
        name=f"schema-{seed}", version=str(seed), entities=entities, relations=relations
    )


class TestDumpSchema:
    """The canonical dump round-trips through load_schema."""

    @pytest.mark.parametrize("seed", range(40))
    def test_load_of_dump_equals_the_schema(self, seed):
        """Loading a dump returns an equal schema for many shapes."""
        schema = _random_schema(seed)

        assert load_schema(dump_schema(schema)) == schema

    @pytest.mark.parametrize("seed", range(10))
    def test_dump_is_stable(self, seed):
        """Dumping a loaded dump gives back the same dict."""
        dumped = dump_schema(_random_schema(seed))

        assert dump_schema(load_schema(dumped)) == dumped

    def test_shorthand_and_canonical_forms_load_equal(self):
        """A shorthand source and its canonical dump load to equal schemas."""
        short = load_schema(
            {
                "name": "t",
                "entities": {
                    "Vendor": {"description": "A seller.", "parents": "Org"},
                    "Org": None,
                },
                "relations": ["Vendor-SELLS_TO->Org"],
            }
        )
        full = load_schema(dump_schema(short))

        assert full == short


_SHIPPED = {
    "default": DEFAULT_SCHEMA,
    "operations": OPERATIONS.apply(DEFAULT_SCHEMA),
    "legal": LEGAL.apply(DEFAULT_SCHEMA),
}


class TestShippedSchemas:
    """The shipped schema names load to their canonical schemas."""

    @pytest.mark.parametrize("name", ["default", "operations", "legal"])
    def test_shipped_schema_survives_a_dump_and_load(self, name):
        """Dumping a shipped schema and loading it gives an equal schema."""
        schema = _SHIPPED[name]

        assert load_schema(dump_schema(schema)) == schema

    @pytest.mark.parametrize("name", ["default", "operations", "legal"])
    def test_shipped_name_loads_its_schema(self, name):
        """Loading a shipped name gives the schema built for that name."""
        assert load_schema(name) == _SHIPPED[name]
