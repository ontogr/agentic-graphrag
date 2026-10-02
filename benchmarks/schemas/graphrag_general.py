"""Graph schemas for the GraphRAG-Bench corpora: general prose and oncology guidelines.

Each corpus runs in its own graph, so each has its own schema. ``NOVEL`` fits the
Project Gutenberg texts, which are mostly not fiction (a hygiene primer, a magazine,
a play, a diary, essays). ``MEDICAL`` fits the NCCN patient guideline booklets.

Every entity type carries a ``description`` property, because agrag embeds an entity
as "name: description" only when that property exists.
"""

from itertools import product

from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType


_DESCRIPTION = {"description": "str"}


def _entity(label: str, text: str, **extra: str) -> EntityType:
    return EntityType(
        label=label, description=text, properties={**_DESCRIPTION, **extra}
    )


_NOVEL_LABELS = [
    "Person",
    "Group",
    "Place",
    "Object",
    "Concept",
    "Work",
    "Event",
    "Quantity",
    "Date",
]


def _pairs(sources: list[str], targets: list[str]) -> list[tuple[str, str]]:
    return list(product(sources, targets))


_ACTORS = ["Person", "Group"]
_THINGS = ["Object", "Concept", "Work", "Event", "Place"]

NOVEL = GraphSchema(
    name="graphrag-novel",
    version="1",
    entities=[
        _entity(
            "Person",
            "A named person, or a person named by role (the dean, the narrator, "
            "the boy).",
        ),
        _entity("Group", "A family, class, order, institution, company or people."),
        _entity(
            "Place", "A named or described location, building, region or body of water."
        ),
        _entity(
            "Object",
            "A physical thing: a machine, instrument, tool, organ, animal, plant or "
            "material.",
        ),
        _entity(
            "Concept",
            "An idea, practice, topic, substance, condition, habit or rule the text "
            "discusses.",
        ),
        _entity("Work", "A book, article, play, letter, song, law or other document."),
        _entity(
            "Event",
            "A named or narrated occurrence: a trip, meeting, battle or lesson.",
        ),
        _entity(
            "Quantity",
            "A stated number, amount of money, measure or price.",
            value="str",
            unit="str",
        ),
        _entity("Date", "A stated date, year, season or time period."),
    ],
    relations=[
        RelationType(
            label="PART_OF",
            description="One thing is a part, member or section of another.",
            patterns=[
                ("Object", "Object"),
                ("Object", "Person"),
                ("Place", "Place"),
                ("Concept", "Concept"),
                ("Work", "Work"),
                ("Group", "Group"),
                ("Event", "Event"),
            ],
        ),
        RelationType(
            label="LOCATED_IN",
            description="Something is in or near a place.",
            patterns=_pairs(_ACTORS + ["Object", "Event", "Place"], ["Place"]),
        ),
        RelationType(
            label="MEMBER_OF",
            description="A person or group belongs to a group.",
            patterns=[("Person", "Group"), ("Group", "Group")],
        ),
        RelationType(
            label="CREATED_BY",
            description=(
                "A work, object or idea is written, made, published or produced by "
                "someone."
            ),
            patterns=_pairs(["Work", "Object", "Concept", "Event"], _ACTORS),
        ),
        RelationType(
            label="CAUSES",
            description="One thing brings about, harms or results in another.",
            patterns=_pairs(["Concept", "Object", "Event"], ["Concept", "Event"]),
        ),
        RelationType(
            label="USES",
            description="A person, group or thing uses, needs or consumes another.",
            patterns=_pairs(_ACTORS + ["Object"], ["Object", "Concept"]),
        ),
        RelationType(
            label="INTERACTS_WITH",
            description=(
                "People or groups meet, write to, marry, pay, help or oppose each "
                "other."
            ),
            patterns=_pairs(_ACTORS, _ACTORS),
        ),
        RelationType(
            label="TRAVELS_TO",
            description="A person or group goes to a place.",
            patterns=_pairs(_ACTORS, ["Place"]),
        ),
        RelationType(
            label="OWNS",
            description="A person or group owns, holds or gives an object or place.",
            patterns=_pairs(_ACTORS, ["Object", "Place"]),
        ),
        RelationType(
            label="ALSO_KNOWN_AS",
            description="Two names refer to the same thing.",
            patterns=[(label, label) for label in _NOVEL_LABELS[:7]],
        ),
        RelationType(
            label="OCCURRED_AT",
            description="An event took place at a place or time.",
            patterns=[("Event", "Place"), ("Event", "Date")],
        ),
        RelationType(
            label="DESCRIBES",
            description="A work or passage describes or teaches about a thing.",
            patterns=_pairs(
                ["Work"], ["Person", "Place", "Object", "Concept", "Event"]
            ),
        ),
        RelationType(
            label="HAS_QUANTITY",
            description="Something has, costs or measures a stated quantity.",
            patterns=_pairs(
                ["Person", "Group", "Object", "Concept", "Event", "Place"], ["Quantity"]
            ),
        ),
        RelationType(
            label="RELATED_TO",
            description="Any other stated link between two things.",
            patterns=_pairs(_NOVEL_LABELS, _NOVEL_LABELS),
        ),
    ],
)

MEDICAL = GraphSchema(
    name="graphrag-medical",
    version="1",
    entities=[
        _entity("Cancer", "A cancer, tumor or related disease and its named subtypes."),
        _entity(
            "Anatomy",
            "A body part, organ, tissue layer or cell type.",
        ),
        _entity("Test", "An imaging study, lab test or screening exam."),
        _entity(
            "Procedure", "A surgery, biopsy or other procedure done by a clinician."
        ),
        _entity(
            "Treatment",
            "A drug, chemotherapy, radiation, immunotherapy or other therapy.",
            treatment_kind="str",
        ),
        _entity(
            "RiskFactor", "An exposure, trait, habit or condition that raises risk."
        ),
        _entity("Symptom", "A sign, symptom or side effect."),
        _entity("Stage", "A stage, grade or TNM category of a cancer.", system="str"),
        _entity("Biomarker", "A gene, protein or molecular marker tested for."),
        _entity(
            "Recommendation",
            "A guideline statement such as 'NCCN recommends' or 'is recommended', "
            "with what it advises.",
            strength="str",
        ),
        _entity("FollowUp", "A follow-up visit, schedule or surveillance plan."),
        _entity(
            "GuideRef",
            "A cross-reference such as 'See Guide 1' or a named table or list.",
        ),
        _entity(
            "Specialist", "A doctor or care role, such as an oncologist or radiologist."
        ),
    ],
    relations=[
        RelationType(
            label="SUBTYPE_OF",
            description="A cancer is a subtype of another cancer.",
            patterns=[("Cancer", "Cancer")],
        ),
        RelationType(
            label="ARISES_IN",
            description="A cancer starts in or spreads to a body part or cell type.",
            patterns=[("Cancer", "Anatomy")],
        ),
        RelationType(
            label="PART_OF",
            description="A body part or cell type is part of another.",
            patterns=[("Anatomy", "Anatomy")],
        ),
        RelationType(
            label="HAS_SYMPTOM",
            description="A cancer causes a sign or symptom.",
            patterns=[("Cancer", "Symptom")],
        ),
        RelationType(
            label="HAS_RISK_FACTOR",
            description="A risk factor raises the risk of a cancer.",
            patterns=[("Cancer", "RiskFactor")],
        ),
        RelationType(
            label="DIAGNOSED_BY",
            description="A test or procedure finds or confirms a cancer.",
            patterns=[("Cancer", "Test"), ("Cancer", "Procedure")],
        ),
        RelationType(
            label="STAGED_AS",
            description="A cancer is classified in a stage.",
            patterns=[("Cancer", "Stage")],
        ),
        RelationType(
            label="HAS_BIOMARKER",
            description="A cancer is linked to a biomarker.",
            patterns=[("Cancer", "Biomarker")],
        ),
        RelationType(
            label="TESTS_FOR",
            description="A test looks for a biomarker.",
            patterns=[("Test", "Biomarker")],
        ),
        RelationType(
            label="TREATED_BY",
            description="A cancer or stage is treated with a therapy or procedure.",
            patterns=[
                ("Cancer", "Treatment"),
                ("Cancer", "Procedure"),
                ("Stage", "Treatment"),
                ("Stage", "Procedure"),
            ],
        ),
        RelationType(
            label="HAS_SIDE_EFFECT",
            description="A therapy or procedure causes a symptom.",
            patterns=[("Treatment", "Symptom"), ("Procedure", "Symptom")],
        ),
        RelationType(
            label="RECOMMENDS",
            description=(
                "A recommendation advises a test, procedure, therapy or follow-up."
            ),
            patterns=[
                ("Recommendation", "Test"),
                ("Recommendation", "Procedure"),
                ("Recommendation", "Treatment"),
                ("Recommendation", "FollowUp"),
            ],
        ),
        RelationType(
            label="APPLIES_TO",
            description="A recommendation or follow-up applies to a cancer or stage.",
            patterns=[
                ("Recommendation", "Cancer"),
                ("Recommendation", "Stage"),
                ("FollowUp", "Cancer"),
            ],
        ),
        RelationType(
            label="FOLLOWED_BY",
            description="A therapy or procedure is followed by a follow-up.",
            patterns=[("Treatment", "FollowUp"), ("Procedure", "FollowUp")],
        ),
        RelationType(
            label="PERFORMED_BY",
            description="A specialist performs a test, procedure or therapy.",
            patterns=[
                ("Test", "Specialist"),
                ("Procedure", "Specialist"),
                ("Treatment", "Specialist"),
            ],
        ),
        RelationType(
            label="SEE_GUIDE",
            description="A cancer or recommendation points to a cross-reference.",
            patterns=[("Cancer", "GuideRef"), ("Recommendation", "GuideRef")],
        ),
    ],
)
