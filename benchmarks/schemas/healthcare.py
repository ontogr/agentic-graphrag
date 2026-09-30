"""Graph schema for the Healthcare benchmark corpus: StatPearls and medical textbooks.

The corpus is the retrieval closure of the selected HealthBench prompts: small,
independent passages from StatPearls articles and 18 textbooks. Patient groups and
doses are their own entities, because advice depends on who the patient is and one
drug has different doses for different groups.

Every entity type carries a ``description`` property, because agrag embeds an entity
as "name: description" only when that property exists.
"""

from itertools import product

from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType


def _entity(label: str, text: str, **extra: str) -> EntityType:
    return EntityType(
        label=label, description=text, properties={"description": "str", **extra}
    )


_ALL = [
    "Condition",
    "Symptom",
    "Drug",
    "Dosing",
    "Test",
    "Procedure",
    "Anatomy",
    "Organism",
    "Population",
    "RiskFactor",
    "Recommendation",
]

HEALTHCARE = GraphSchema(
    name="healthcare",
    version="1",
    entities=[
        _entity(
            "Condition",
            "A disease, syndrome, injury or clinical state, including subtypes.",
        ),
        _entity(
            "Symptom",
            "A sign, symptom, complication, side effect or red-flag finding.",
        ),
        _entity(
            "Drug",
            "A medicine, vaccine, supplement or drug class.",
        ),
        _entity(
            "Dosing",
            "One stated dose: amount, unit, frequency and route, for one group. Name "
            "it "
            "with the drug and the group, for example 'ibuprofen 10 mg/kg every 6 "
            "hours "
            "in children'.",
            amount="str",
            unit="str",
            frequency="str",
            route="str",
        ),
        _entity(
            "Test",
            "A lab test, imaging study, score or screening exam, with any threshold "
            "stated.",
        ),
        _entity(
            "Procedure",
            "A surgery, intervention or other clinician-performed treatment.",
        ),
        _entity("Anatomy", "A body part, organ, tissue or system."),
        _entity("Organism", "A bacterium, virus, parasite, fungus or vector."),
        _entity(
            "Population",
            "A patient group or context: an age group, pregnancy, kidney function "
            "band, "
            "immune status, region or setting.",
        ),
        _entity(
            "RiskFactor",
            "An exposure, habit, trait or condition that raises the risk of a disease.",
        ),
        _entity(
            "Recommendation",
            "A stated piece of clinical advice or guideline, such as when to seek "
            "urgent "
            "care or which option is first line.",
            strength="str",
        ),
    ],
    relations=[
        RelationType(
            label="SUBTYPE_OF",
            description="One condition, organism or drug is a subtype of another.",
            patterns=[
                ("Condition", "Condition"),
                ("Organism", "Organism"),
                ("Drug", "Drug"),
            ],
        ),
        RelationType(
            label="PART_OF",
            description="A body part is part of another.",
            patterns=[("Anatomy", "Anatomy")],
        ),
        RelationType(
            label="AFFECTS",
            description="A condition affects a body part.",
            patterns=[("Condition", "Anatomy")],
        ),
        RelationType(
            label="CAUSES",
            description="A condition leads to a symptom or another condition.",
            patterns=[("Condition", "Symptom"), ("Condition", "Condition")],
        ),
        RelationType(
            label="CAUSED_BY_ORGANISM",
            description="An organism causes a condition.",
            patterns=[("Condition", "Organism")],
        ),
        RelationType(
            label="HAS_SYMPTOM",
            description="A condition presents with a symptom or sign.",
            patterns=[("Condition", "Symptom")],
        ),
        RelationType(
            label="DIAGNOSED_BY",
            description="A test or procedure finds or confirms a condition.",
            patterns=[("Condition", "Test"), ("Condition", "Procedure")],
        ),
        RelationType(
            label="MONITORED_BY",
            description="A test tracks a condition or the effect of a drug.",
            patterns=[("Condition", "Test"), ("Drug", "Test")],
        ),
        RelationType(
            label="TREATS",
            description="A drug or procedure treats a condition or symptom.",
            patterns=[
                ("Drug", "Condition"),
                ("Drug", "Symptom"),
                ("Procedure", "Condition"),
                ("Procedure", "Symptom"),
            ],
        ),
        RelationType(
            label="PREVENTS",
            description="A drug, vaccine or procedure prevents a condition.",
            patterns=[("Drug", "Condition"), ("Procedure", "Condition")],
        ),
        RelationType(
            label="RISK_FACTOR_FOR",
            description=(
                "A risk factor or patient group has a higher risk of a condition."
            ),
            patterns=[("RiskFactor", "Condition"), ("Population", "Condition")],
        ),
        RelationType(
            label="CONTRAINDICATED_IN",
            description=(
                "A drug or procedure must be avoided in a condition or patient group."
            ),
            patterns=[
                ("Drug", "Condition"),
                ("Drug", "Population"),
                ("Procedure", "Condition"),
                ("Procedure", "Population"),
            ],
        ),
        RelationType(
            label="INTERACTS_WITH",
            description="Two drugs interact.",
            patterns=[("Drug", "Drug")],
        ),
        RelationType(
            label="HAS_ADVERSE_EFFECT",
            description="A drug or procedure can cause a symptom as a side effect.",
            patterns=[("Drug", "Symptom"), ("Procedure", "Symptom")],
        ),
        RelationType(
            label="HAS_DOSING",
            description="A drug has a stated dose.",
            patterns=[("Drug", "Dosing")],
        ),
        RelationType(
            label="APPLIES_TO",
            description=(
                "A dose or recommendation holds for a patient group, condition or "
                "symptom."
            ),
            patterns=[
                ("Dosing", "Population"),
                ("Dosing", "Condition"),
                ("Recommendation", "Population"),
                ("Recommendation", "Condition"),
                ("Recommendation", "Symptom"),
            ],
        ),
        RelationType(
            label="RECOMMENDS",
            description="A recommendation advises a drug, test or procedure.",
            patterns=[
                ("Recommendation", "Drug"),
                ("Recommendation", "Test"),
                ("Recommendation", "Procedure"),
            ],
        ),
        RelationType(
            label="RELATED_TO",
            description="Any other stated link between two things.",
            patterns=list(product(_ALL, _ALL)),
        ),
    ],
)
