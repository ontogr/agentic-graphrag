"""Preset schema fragments that add entity types to a base schema."""

from pydantic import BaseModel, ConfigDict

from agrag.common.data_models.graph_schema import EntityType, GraphSchema


class Preset(BaseModel):
    """A curated set of entity types to add to a base schema.

    A preset adds entity types. It never adds a relation, changes a pattern or
    changes a description.

    Attributes:
        name: A short, unique name, such as ``"operations"``.
        entities: The entity types the preset adds.
        widenings: Always empty in this release.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    entities: list[EntityType]
    widenings: tuple[()] = ()

    def apply(self, base: GraphSchema) -> GraphSchema:
        """Return a new schema with this preset's entity types appended.

        Args:
            base: The schema to extend.

        Returns:
            A new schema named ``"<base name>+<preset name>"`` with the base
            version and relations.

        Raises:
            ValueError: The base already declares a preset entity label.
        """
        declared = {entity.label for entity in base.entities}
        for entity in self.entities:
            if entity.label in declared:
                raise ValueError(
                    f"Schema '{base.name}' already declares '{entity.label}'; "
                    f"preset '{self.name}' only adds new entity types. Apply "
                    "each preset once, to a schema without these types."
                )

        return GraphSchema(
            name=f"{base.name}+{self.name}",
            version=base.version,
            entities=[
                *[entity.model_copy(deep=True) for entity in base.entities],
                *[entity.model_copy(deep=True) for entity in self.entities],
            ],
            relations=[relation.model_copy(deep=True) for relation in base.relations],
        )


OPERATIONS = Preset(
    name="operations",
    entities=[
        EntityType(
            label="Facility",
            description=(
                "A place, equipment, or service that supports a specific function."
            ),
        ),
        EntityType(
            label="Service",
            description=(
                "A service provided by an organization, such as delivery or printing."
            ),
        ),
        EntityType(
            label="Occupation",
            description=(
                "A profession, which may need long training or a formal qualification."
            ),
        ),
    ],
)
"""Operations types: facilities, services and occupations."""

LEGAL = Preset(
    name="legal",
    entities=[
        EntityType(
            label="Contract",
            description=(
                "An agreement with a lawful object, made by two or more parties."
            ),
        ),
        EntityType(
            label="Regulation",
            description="A rule with legal force, issued by a legislative body.",
        ),
    ],
)
"""Legal types: contracts and regulations."""
