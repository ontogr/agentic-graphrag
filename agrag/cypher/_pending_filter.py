"""Pending-visibility filter for Cutover Job writes."""

from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY


def pending_filter_clause(alias: str, job_id_param: str | None = None) -> str:
    """Return a WHERE fragment controlling an alias's pending visibility.

    Args:
        alias: The Cypher node or relationship alias the filter applies
            to.
        job_id_param: The parameter name holding the in-flight Cutover
            Job's id, or None for committed-only. The job-scoped form
            lets a pipeline step see its own job's writes while still
            excluding every other in-flight job's; a null parameter
            reduces it to committed-only, which is what every caller
            outside a job passes.

    Returns:
        A ``WHERE`` fragment: ``alias._pending_job_id IS NULL``
        committed-only, or
        ``(alias._pending_job_id IS NULL OR alias._pending_job_id =
        $param)`` job-scoped.
    """
    property_ref = f"{alias}.{PENDING_JOB_ID_PROPERTY}"
    if job_id_param is None:
        return f"{property_ref} IS NULL"
    return f"({property_ref} IS NULL OR {property_ref} = ${job_id_param})"
