"""Build deterministic resolved entities from raw semantic-match components."""

from agrag.common.data_models.entity import Entity
from agrag.common.data_models.graph_schema import GraphSchema
from agrag.common.data_models.resolved_entity import ResolvedEntity, resolved_entity_id
from agrag.ingestion.merge import compute_merge


async def materialize_component(
    members: list[Entity], *, schema: GraphSchema
) -> ResolvedEntity:
    """Build one stable resolved entity from two or more same-label raw entities.

    Raises:
        ValueError: The component has fewer than two members or mixed labels.
    """
    if len(members) < 2:
        raise ValueError("A resolved component requires at least two raw entities.")
    ordered_members = sorted(members, key=lambda entity: str(entity.id))
    plan, _ = await compute_merge(
        existing_entities=ordered_members,
        mentions=[],
        schema=schema,
    )
    member_ids = [entity.id for entity in ordered_members]
    source_chunk_ids = list(
        dict.fromkeys(
            chunk_id
            for entity in ordered_members
            for chunk_id in entity.source_chunk_ids
        )
    )
    return ResolvedEntity(
        id=resolved_entity_id(ordered_members[0].label, member_ids),
        label=ordered_members[0].label,
        name=plan.survivor.name,
        properties=plan.survivor.properties,
        member_ids=member_ids,
        merge_count=sum(entity.merge_count for entity in ordered_members),
        source_chunk_ids=source_chunk_ids,
    )
