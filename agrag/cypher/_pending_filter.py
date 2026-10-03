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


def pending_path_filter_clause(path_alias: str, job_id_param: str | None = None) -> str:
    """Return a WHERE fragment keeping a path inside committed rows.

    Written as ``ALL`` predicates over the path's nodes and relationships,
    the form Neo4j applies while it searches, so a ``shortestPath`` skips
    pending rows instead of failing after it found a path through them.

    Args:
        path_alias: The Cypher path variable the filter applies to.
        job_id_param: The parameter name holding the in-flight job's id, or
            None for committed-only. See :func:`pending_filter_clause`.

    Returns:
        A ``WHERE`` fragment over every node and relationship of the path.
    """
    nodes = pending_filter_clause("path_node", job_id_param)
    relations = pending_filter_clause("path_relation", job_id_param)
    return (
        f"ALL(path_node IN nodes({path_alias}) WHERE {nodes}) "
        f"AND ALL(path_relation IN relationships({path_alias}) WHERE {relations})"
    )
