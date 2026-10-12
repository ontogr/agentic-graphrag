"""Tests for the Pydantic class import."""

from datetime import date, datetime
from enum import Enum
from typing import List, Literal

import pytest
from pydantic import BaseModel, Field

from agrag.schema import SchemaLoadError
from agrag.schema.formats import from_pydantic


class Organization(BaseModel):
    """A company or institution."""

    title: str


class Company(Organization):
    """A for-profit organization."""

    status: Literal["active", "dissolved"]


class Person(BaseModel):
    """A named individual."""

    email: str
    born: date | None = None
    nickname: str = ""
    seen_at: datetime | None = None
    tags: list[str] = []
    works_for: Organization | None = Field(
        default=None, description="A person is employed by an organization."
    )
    colleagues: list["Person"] = Field(
        default_factory=list, max_length=50, description="Two people work together."
    )


class Level(Enum):
    """Ticket severity levels for the enum mapping test."""

    LOW = "low"
    HIGH = "high"


class Ticket(BaseModel):
    """A support ticket."""

    level: Level
    owner: Person


def _read(*models: type[BaseModel]):
    return from_pydantic(list(models), name="company")


class TestFromPydantic:
    """Each class is an entity type; fields are properties or relations."""

    def test_class_name_docstring_and_parent(self) -> None:
        """A registered base class becomes a parent and keeps only own fields."""
        result = _read(Organization, Company, Person)

        by_label = {e.label: e for e in result.schema.entities}
        assert by_label["Company"].description == "A for-profit organization."
        assert by_label["Company"].parents == ["Organization"]
        assert list(by_label["Company"].properties) == ["status"]

    def test_property_types_required_and_enum(self) -> None:
        """Defaults decide required, Literal and Enum give enum values."""
        result = _read(Organization, Company, Person, Ticket)

        by_label = {e.label: e for e in result.schema.entities}
        person = by_label["Person"].properties
        assert person["email"].required is True
        assert person["born"].type == "date"
        assert person["born"].required is False
        assert person["nickname"].required is False
        assert by_label["Company"].properties["status"].enum == ["active", "dissolved"]
        assert by_label["Ticket"].properties["level"].enum == ["low", "high"]

    def test_model_fields_become_relations_with_limits(self) -> None:
        """A single-valued field has a limit of one; max_length sets the limit."""
        result = _read(Organization, Company, Person)

        relations = {r.label: r for r in result.schema.relations}
        works_for = relations["WORKS_FOR"]
        assert works_for.patterns == [("Person", "Organization")]
        assert works_for.description == "A person is employed by an organization."
        assert works_for.cardinality.max_per_source == 1
        assert relations["COLLEAGUES"].cardinality.max_per_source == 50

    def test_fields_without_a_property_type_are_dropped_with_a_warning(self) -> None:
        """A list[str] field and a datetime field have no property type."""
        result = _read(Organization, Company, Person)

        assert [(w.code, w.element) for w in result.warnings] == [
            ("property_dropped", "Person.seen_at"),
            ("property_dropped", "Person.tags"),
        ]
        declared = {n for e in result.schema.entities for n in e.properties}
        assert not {"tags", "seen_at"} & declared

    def test_missing_docstring_warns_and_uses_the_label(self) -> None:
        """A class without a docstring gets its name as description."""

        class Bare(BaseModel):
            x: int

        result = from_pydantic([Bare], name="t")

        assert result.schema.entities[0].description == "Bare"
        assert [w.code for w in result.warnings] == ["missing_description"]

    def test_unregistered_model_field_is_dropped_with_a_warning(self) -> None:
        """A field typed as a class outside the list is not a relation."""
        result = _read(Person, Ticket)

        assert ("property_dropped", "Person.works_for") in [
            (w.code, w.element) for w in result.warnings
        ]
        by_label = {entity.label: entity for entity in result.schema.entities}
        assert "works_for" not in by_label["Person"].properties

    def test_boolean_enum_values_use_lowercase_text(self) -> None:
        """Boolean Literal values map to true and false, not True and False."""

        class Switch(BaseModel):
            """A boolean flag."""

            enabled: Literal[True, False]

        result = from_pydantic([Switch], name="t")

        assert result.schema.entities[0].properties["enabled"].enum == [
            "true",
            "false",
        ]

    def test_mixed_enum_values_are_dropped_with_a_warning(self) -> None:
        """A Literal of mixed types has no single property type."""

        class Mixed(BaseModel):
            """A mixed holder."""

            value: Literal[1, "a"]

        result = from_pydantic([Mixed], name="t")

        assert ("property_dropped", "Mixed.value") in [
            (w.code, w.element) for w in result.warnings
        ]
        assert "value" not in result.schema.entities[0].properties

    def test_bare_collection_is_dropped_with_a_warning(self) -> None:
        """A collection without an item type has no schema equivalent."""

        class Bag(BaseModel):
            """A bare holder."""

            items: List

        result = from_pydantic([Bag], name="t")

        assert ("property_dropped", "Bag.items") in [
            (w.code, w.element) for w in result.warnings
        ]
        assert "items" not in result.schema.entities[0].properties

    def test_child_override_replaces_the_parent_field(self) -> None:
        """A child that redeclares a parent field keeps its own mapping."""

        class Status(BaseModel):
            """A base holder."""

            state: str

        class ActiveStatus(Status):
            """A child holder."""

            state: Literal["active"]

        result = from_pydantic([Status, ActiveStatus], name="t")

        by_label = {entity.label: entity for entity in result.schema.entities}
        assert by_label["ActiveStatus"].properties["state"].enum == ["active"]
        assert by_label["Status"].properties["state"].enum is None

    def test_reserved_class_name_raises(self) -> None:
        """A class named like a graph label fails with a schema format error."""

        class Chunk(BaseModel):
            """A reserved name."""

        with pytest.raises(SchemaLoadError):
            from_pydantic([Chunk], name="t")
