"""Writes the structure nodes of one ``add`` call to the graph store."""

import asyncio
from uuid import UUID

from agrag.common.data_models.graph_record import NodeRecord, UpsertResult
from agrag.common.data_models.structure import (
    FIGURE_LABEL,
    SECTION_LABEL,
    SOURCE_LABEL,
    TABLE_LABEL,
)
from agrag.graphdb.base import GraphStore
from agrag.ingestion._structure import StructureRecords


async def write_structure_node_labels(
    graph_store: GraphStore,
    structure: StructureRecords,
    *,
    pending_job_id: UUID | None,
) -> list[UpsertResult]:
    """Upsert the section, table, figure and source nodes that have records.

    Only node writes run here, one per label that has records. The structure
    edges (``HAS_CHILD``, ``PART_OF``, ``HAS_DOCUMENT``) travel with the other
    relation records through the pipeline's relation writes instead.

    Args:
        graph_store: The store to write to.
        structure: The structure records of the call.
        pending_job_id: The job that owns the writes.

    Returns:
        One result for each label that had records, in the order of the labels.
        A failed write raises, so the caller decides how to record it.
    """
    pending: list[tuple[str, list[NodeRecord]]] = [
        (label, records)
        for label, records in (
            (SECTION_LABEL, structure.sections),
            (TABLE_LABEL, structure.tables),
            (FIGURE_LABEL, structure.figures),
            (SOURCE_LABEL, structure.sources),
        )
        if records
    ]
    outcomes = await asyncio.gather(
        *(
            graph_store.upsert_nodes(label, records, pending_job_id=pending_job_id)
            for label, records in pending
        ),
        return_exceptions=True,
    )
    results: list[UpsertResult] = []
    for outcome in outcomes:
        if isinstance(outcome, BaseException):
            raise outcome
        results.append(outcome)
    return results
