"""Graph schema for the BEAM long-term memory corpus, one graph per conversation.

Statements are nodes, because a schema relation carries no time or order: a newer
``Fact`` ``SUPERSEDES`` an older one, opposing facts stay linked by ``CONTRADICTS``,
and standing rules (``Instruction``, ``Preference``) point at the topic that triggers
them. A ``Session`` node holds the only clock, one date per session, and message
order comes from the chunk order.

Every entity type carries a ``description`` property, because agrag embeds an entity
as "name: description" only when that property exists.
"""

from itertools import product

from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType


def _entity(label: str, text: str, **extra: str) -> EntityType:
    return EntityType(
        label=label, description=text, properties={"description": "str", **extra}
    )


_WORLD = ["Person", "Place", "Organization", "Tool", "Topic", "Event"]
_STATEMENTS = ["Fact", "Instruction", "Preference"]

MEMORY = GraphSchema(
    name="beam-memory",
    version="1",
    entities=[
        _entity(
            "Person",
            "A person the chat mentions. The person who writes the user messages is "
            "named User unless the chat gives a name.",
        ),
        _entity("Place", "A city, venue, address or other location."),
        _entity("Organization", "A company, team, school or other institution."),
        _entity(
            "Tool",
            "A software tool, app, library, framework, method or formula, with its "
            "version when stated.",
        ),
        _entity("Topic", "A subject, skill, project, problem type or area of work."),
        _entity(
            "Event",
            "A meeting, deadline, milestone or other dated occurrence. Keep the date "
            "as written in the chat.",
            date_text="str",
        ),
        _entity(
            "Measure",
            "A stated number with its unit, such as a score, budget, count, "
            "percentage, duration or version, and what it measures. Put the value in "
            "the name (for example 'licence budget 6,200 USD') so that an updated "
            "number is a separate node and does not overwrite the old one.",
            value="str",
            unit="str",
            measures="str",
        ),
        _entity(
            "Fact",
            "One thing a speaker states about the user's life, plans or progress. "
            "Name it with a full sentence that includes the values, so two different "
            "statements never share a name. Do not merge opposing statements.",
            speaker="str",
        ),
        _entity(
            "Instruction",
            "A standing rule the user gives about how to answer, such as 'always "
            "format dates as MM/DD/YYYY'.",
            speaker="str",
        ),
        _entity(
            "Preference",
            "A stated preference of the user about tools, methods or style.",
            speaker="str",
        ),
        _entity(
            "Session",
            "One conversation session, named by its number and its date anchor.",
            session_number="str",
            session_date="str",
        ),
    ],
    relations=[
        RelationType(
            label="STATED_IN",
            description="A statement, event or number first appears in a session.",
            patterns=[
                (label, "Session") for label in [*_STATEMENTS, "Event", "Measure"]
            ],
        ),
        RelationType(
            label="ABOUT",
            description=(
                "A fact is about a person, place, tool, topic, event or number."
            ),
            patterns=[("Fact", label) for label in [*_WORLD, "Measure"]],
        ),
        RelationType(
            label="SUPERSEDES",
            description=(
                "A newer fact or number replaces an older one about the same thing."
            ),
            patterns=[("Fact", "Fact"), ("Measure", "Measure")],
        ),
        RelationType(
            label="CONTRADICTS",
            description="Two facts cannot both be true. Keep both.",
            patterns=[("Fact", "Fact")],
        ),
        RelationType(
            label="HAS_MEASURE",
            description="Something has a stated number.",
            patterns=[
                (label, "Measure")
                for label in ["Person", "Organization", "Tool", "Topic", "Event"]
            ],
        ),
        RelationType(
            label="APPLIES_WHEN",
            description=(
                "A rule or preference applies when the user asks about a topic."
            ),
            patterns=[("Instruction", "Topic"), ("Preference", "Topic")],
        ),
        RelationType(
            label="PARTICIPATES_IN",
            description="A person or organization takes part in an event.",
            patterns=[("Person", "Event"), ("Organization", "Event")],
        ),
        RelationType(
            label="LOCATED_AT",
            description="An event, person or organization is at a place.",
            patterns=[
                ("Event", "Place"),
                ("Person", "Place"),
                ("Organization", "Place"),
            ],
        ),
        RelationType(
            label="USES",
            description="A person or organization uses a tool.",
            patterns=[("Person", "Tool"), ("Organization", "Tool")],
        ),
        RelationType(
            label="PART_OF",
            description="A topic or event is part of a larger one.",
            patterns=[("Topic", "Topic"), ("Event", "Event")],
        ),
        RelationType(
            label="FOLLOWS",
            description=(
                "An event comes after another event in the order the chat mentions "
                "them."
            ),
            patterns=[("Event", "Event")],
        ),
        RelationType(
            label="RELATED_TO",
            description="Any other stated link between two things.",
            patterns=list(product(_WORLD, _WORLD)),
        ),
    ],
)
