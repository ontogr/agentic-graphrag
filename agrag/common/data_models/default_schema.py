"""The default schema: nine entity types and eight typed relations."""

from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    RelationType,
)


_ACTORS = ("Person", "Organization")

DEFAULT_SCHEMA = GraphSchema(
    name="default",
    version="1",
    entities=[
        EntityType(label="Person", description="A person, living, dead, or fictional."),
        EntityType(
            label="Organization",
            description="An organization such as a company, school, NGO, or club.",
        ),
        EntityType(
            label="Location",
            description="A place with a somewhat fixed, physical extension.",
        ),
        EntityType(
            label="Event",
            description=(
                "A happening at a set time and place, such as a concert or lecture."
            ),
        ),
        EntityType(
            label="Product",
            description=(
                "A material or service produced or provided by an organization."
            ),
        ),
        EntityType(
            label="Software",
            description="A computer program or software application.",
        ),
        EntityType(
            label="Publication",
            description=(
                "A written or published work such as a book, report, or article."
            ),
        ),
        EntityType(
            label="Dataset",
            description="A structured body of information about one or more topics.",
        ),
        EntityType(
            label="Project",
            description=(
                "A planned, typically collaborative effort to achieve a particular aim."
            ),
        ),
    ],
    relations=[
        RelationType(
            label="WORKS_FOR",
            description="A person is employed by, or works for, an organization.",
            patterns=[("Person", "Organization")],
        ),
        RelationType(
            label="PART_OF",
            description="The source is a part of the target it belongs to.",
            patterns=[
                ("Organization", "Organization"),
                ("Project", "Project"),
                ("Software", "Software"),
                ("Publication", "Publication"),
            ],
        ),
        RelationType(
            label="LOCATED_IN",
            description="The source is physically situated in the target place.",
            patterns=[
                ("Organization", "Location"),
                ("Event", "Location"),
                ("Project", "Location"),
            ],
        ),
        RelationType(
            label="OWNS",
            description="The source is the owner of the target.",
            patterns=[
                (source, target)
                for source in _ACTORS
                for target in ("Software", "Dataset", "Project")
            ],
        ),
        RelationType(
            label="AUTHORED",
            description="The source is primarily responsible for creating the target.",
            patterns=[
                (source, target)
                for source in _ACTORS
                for target in ("Publication", "Software", "Dataset")
            ],
        ),
        RelationType(
            label="PARTICIPATED_IN",
            description="The source took part in the target event or project.",
            patterns=[
                (source, target)
                for source in _ACTORS
                for target in ("Event", "Project")
            ],
        ),
        RelationType(
            label="DEPENDS_ON",
            description=(
                "The source software requires the target software or dataset to run."
            ),
            patterns=[("Software", "Software"), ("Software", "Dataset")],
        ),
        RelationType(
            label="SUPPLIES",
            description="The source provides or sells the target product or service.",
            patterns=[("Organization", "Product")],
        ),
    ],
)
