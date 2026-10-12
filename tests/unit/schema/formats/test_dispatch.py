"""Tests for reading Pydantic classes through ``load_schema``."""

import pytest
from pydantic import BaseModel

from agrag.schema import SchemaLoadError, load_schema


class Gadget(BaseModel):
    """A small device."""

    serial: str


class TestLoadSchemaDispatch:
    """``load_schema`` reads Pydantic classes and keeps its other rules."""

    def test_pydantic_class_list_loads(self) -> None:
        """A list of Pydantic classes gives a schema named custom."""
        schema = load_schema([Gadget])

        assert schema.name == "custom"
        assert schema.entities[0].label == "Gadget"
        assert schema.entities[0].properties["serial"].required is True

    def test_single_class_loads(self) -> None:
        """One class, not in a list, also loads."""
        assert load_schema(Gadget).entities[0].label == "Gadget"

    def test_class_schema_can_be_extended(self) -> None:
        """A schema read from classes works as the base of ``extends``."""
        extended = load_schema({"entities": ["Vendor"]}, extends=[Gadget])

        assert {e.label for e in extended.entities} == {"Gadget", "Vendor"}

    def test_list_of_labels_still_loads(self) -> None:
        """A list of strings is still a list of labels."""
        assert load_schema(["Person"]).entities[0].label == "Person"

    def test_invalid_class_schema_raises_the_loader_error(self) -> None:
        """A reserved label fails with the same error as any other source."""

        class Chunk(BaseModel):
            """A reserved name."""

        with pytest.raises(SchemaLoadError):
            load_schema([Chunk])
