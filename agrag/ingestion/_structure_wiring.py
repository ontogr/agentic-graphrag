"""Writes the structure nodes of one ``add`` call to the graph store."""

from uuid import UUID

from agrag.common.data_models.graph_record import UpsertResult
from agrag.common.data_models.structure import (
    FIGURE_LABEL,
    SECTION_LABEL,
    SOURCE_LABEL,
    TABLE_LABEL,
)
from agrag.graphdb.base import GraphStore
from agrag.ingestion._structure import StructureRecords


async def write_structure_nodes(
    graph_store: GraphStore,
    structure: StructureRecords,
    *,
    pending_job_id: UUID | None,
) -> list[UpsertResult]:
    """Upsert the section, table, figure and source nodes that have records.

    Args:
        graph_store: The store to write to.
        structure: The structure records of the call.
        pending_job_id: The job that owns the writes.

    Returns:
        One result for each label that had records, in the order of the labels.
        A failed write raises, so the caller decides how to record it.
    """
    results: list[UpsertResult] = []
    for label, records in (
        (SECTION_LABEL, structure.sections),
        (TABLE_LABEL, structure.tables),
        (FIGURE_LABEL, structure.figures),
        (SOURCE_LABEL, structure.sources),
    ):
        if records:
            results.append(
                await graph_store.upsert_nodes(
                    label, records, pending_job_id=pending_job_id
                )
            )
    return results
