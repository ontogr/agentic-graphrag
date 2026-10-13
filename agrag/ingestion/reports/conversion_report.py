"""The report returned by Graph.convert_candidates."""

from pydantic import BaseModel, Field

from agrag.common.data_models.stage_failure import StageFailure


class ConversionReport(BaseModel):
    """What a candidate conversion did.

    Attributes:
        converted_entities: Entity candidates converted in place.
        folded: Entity candidates folded into an existing exact-name owner.
        created_relations: Relation candidates written as edges.
        set_properties: Property candidates written on their entities.
        skipped: Candidate ids that were not converted and their reason.
        failures: Post-commit vector mirror or embedding failures.
    """

    converted_entities: int = 0
    folded: int = 0
    created_relations: int = 0
    set_properties: int = 0
    skipped: dict[str, str] = Field(default_factory=dict)
    failures: list[StageFailure] = Field(default_factory=list)
