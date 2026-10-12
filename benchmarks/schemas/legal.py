"""Graph schema for the Legal benchmark corpus.

Covers privacy policies, ANDAs, commercial contracts and merger agreements in one
schema. Clause kinds are a general legal list, not the labels of CUAD, MAUD or
ContractNLI.
"""

from agrag.common.data_models.graph_schema import (
    EntityType,
    GraphSchema,
    PropertySpec,
    RelationType,
)


_CLAUSE_KINDS = [
    "GoverningLaw",
    "TermAndRenewal",
    "Termination",
    "Payment",
    "IntellectualProperty",
    "Confidentiality",
    "ExclusivityAndNonCompete",
    "Liability",
    "Assignment",
    "DisputeResolution",
    "RepresentationsAndWarranties",
    "Definitions",
]

LEGAL = GraphSchema(
    name="legal",
    version="1",
    entities=[
        EntityType(
            label="Agreement",
            description="A contract, policy or other legal document as a whole.",
            properties={
                "agreement_type": PropertySpec(type="string"),
                "effective_date": PropertySpec(type="string"),
            },
        ),
        EntityType(
            label="Party",
            description=(
                "A person or organization named in the document, under its legal name "
                "or a role word such as Company, Parent, Licensor or Receiving Party."
            ),
            properties={"role": PropertySpec(type="string")},
        ),
        EntityType(
            label="DefinedTerm",
            description="A capitalized term the document defines, with its meaning.",
            properties={"description": PropertySpec(type="string")},
        ),
        EntityType(
            label="Clause",
            description="A numbered section or provision with one legal purpose.",
            properties={
                "section_ref": PropertySpec(type="string"),
                "description": PropertySpec(type="string"),
                "kind": PropertySpec(type="string", enum=_CLAUSE_KINDS),
            },
        ),
        EntityType(
            label="Obligation",
            description="What a party must, must not or may do, and on what condition.",
            properties={
                "kind": PropertySpec(type="string"),
                "description": PropertySpec(type="string"),
            },
        ),
        EntityType(
            label="MonetaryAmount",
            description="A stated sum of money, fee, cap or threshold.",
            properties={
                "amount_text": PropertySpec(type="string"),
                "value": PropertySpec(type="float"),
                "currency": PropertySpec(type="string"),
            },
        ),
        EntityType(
            label="TimePeriod",
            description="A stated duration, term, deadline or notice period.",
            properties={"anchor_event": PropertySpec(type="string")},
        ),
        EntityType(
            label="LegalReference",
            description=(
                "A statute, regulation, exhibit, schedule or other agreement that the "
                "document cites but does not contain."
            ),
            properties={"reference_kind": PropertySpec(type="string")},
        ),
        EntityType(
            label="Jurisdiction", description="A state, country or court venue."
        ),
        EntityType(
            label="DataCategory",
            description="A kind of personal data a privacy policy names.",
            properties={"sensitive": PropertySpec(type="boolean")},
        ),
        EntityType(
            label="Purpose",
            description="A stated reason for which data or a right is used.",
        ),
    ],
    relations=[
        RelationType(
            label="PARTY_TO",
            description="A party is bound by an agreement.",
            patterns=[("Party", "Agreement")],
        ),
        RelationType(
            label="GOVERNED_BY",
            description="An agreement names the law or venue that governs it.",
            patterns=[("Agreement", "Jurisdiction")],
        ),
        RelationType(
            label="CONTAINS_CLAUSE",
            description="An agreement contains a clause.",
            patterns=[("Agreement", "Clause")],
        ),
        RelationType(
            label="DEFINES",
            description="A clause defines a term.",
            patterns=[("Clause", "DefinedTerm")],
        ),
        RelationType(
            label="USES_TERM",
            description="A clause relies on a defined term.",
            patterns=[("Clause", "DefinedTerm")],
        ),
        RelationType(
            label="REFERS_TO",
            description="A clause points to another section or article.",
            patterns=[("Clause", "Clause")],
        ),
        RelationType(
            label="IMPOSES",
            description="A clause creates an obligation.",
            patterns=[("Clause", "Obligation")],
        ),
        RelationType(
            label="OBLIGATED_PARTY",
            description="The party that bears an obligation.",
            patterns=[("Obligation", "Party")],
        ),
        RelationType(
            label="OWED_TO",
            description="The party that benefits from an obligation.",
            patterns=[("Obligation", "Party")],
        ),
        RelationType(
            label="HAS_AMOUNT",
            description="An obligation carries a sum of money.",
            patterns=[("Obligation", "MonetaryAmount")],
        ),
        RelationType(
            label="HAS_PERIOD",
            description="A clause or obligation carries a duration or deadline.",
            patterns=[("Clause", "TimePeriod"), ("Obligation", "TimePeriod")],
        ),
        RelationType(
            label="CITES",
            description="A clause cites an outside statute, exhibit or agreement.",
            patterns=[("Clause", "LegalReference")],
        ),
        RelationType(
            label="COLLECTS",
            description="A party collects a kind of personal data.",
            patterns=[("Party", "DataCategory")],
        ),
        RelationType(
            label="USED_FOR",
            description="A kind of data is used for a purpose.",
            patterns=[("DataCategory", "Purpose")],
        ),
        RelationType(
            label="SHARED_WITH",
            description="A kind of data is shared with a party.",
            patterns=[("DataCategory", "Party")],
        ),
        RelationType(
            label="RETAINED_FOR",
            description="A kind of data is kept for a period.",
            patterns=[("DataCategory", "TimePeriod")],
        ),
    ],
)
