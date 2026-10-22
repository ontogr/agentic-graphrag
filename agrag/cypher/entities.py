"""Cypher builders for node writes and filters.

Leaf module: imports nothing from ``agrag.graphdb`` or other store packages, so
the dependency points one way (store -> cypher).
"""

import re
from collections.abc import Sequence
from typing import Any

from agrag.common.data_models.candidate import CANDIDATE_LABEL
from agrag.common.data_models.graph_record import PENDING_JOB_ID_PROPERTY
from agrag.common.data_models.structure import HAS_PART
from agrag.cypher._pending_filter import pending_filter_clause


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Every node this store writes carries this label, used only to MERGE onto a
# node by id independently of its other, mutable labels. MERGE-ing on the
# full requested label set instead would only match a node that already has
# every one of those labels, so adding a label to an existing same-id node
# would create a duplicate node (and violate any per-label uniqueness
# constraint) rather than update it.
NODE_IDENTITY_LABEL = "_Node"

# One node per merge_key ever assigned to any entity, permanently mapping
# that key to the entity's own id. A live entity's node also carries
# merge_key directly (see merge_key_constraint_query); this table is what
# lets an accepted alternate name resolve to the same entity. See
# fetch_by_merge_keys_query and upsert_merge_alias_query.
MERGE_ALIAS_LABEL = "_MergeAlias"

# Commit and rollback find a job's nodes through one indexed lookup per label
# listed here, so any label a job can tag must be listed.
PENDING_TAGGED_NODE_LABELS: tuple[str, ...] = (
    NODE_IDENTITY_LABEL,
    MERGE_ALIAS_LABEL,
    CANDIDATE_LABEL,
)


def validate_identifier_syntax(value: str) -> str:
    """Check that a label or relationship type is a well-formed Cypher identifier.

    Args:
        value: The label or relationship type to check.

    Returns:
        ``value`` unchanged, once validated.

    Raises:
        ValueError: ``value`` is not a well-formed identifier.
    """
    if not _IDENTIFIER.match(value):
        raise ValueError(f"{value!r} is not a valid Cypher identifier")
    return value


def validate_identifier(value: str) -> str:
    """Check that a label or relationship type is a safe Cypher identifier.

    Args:
        value: The label or relationship type to check.

    Returns:
        ``value`` unchanged, once validated.

    Raises:
        ValueError: ``value`` is not a safe identifier or is reserved.
    """
    validate_identifier_syntax(value)
    if value == CANDIDATE_LABEL:
        raise ValueError(f"{value!r} is reserved for the candidate store")
    return value


def is_safe_identifier(value: str) -> bool:
    """Report whether a label or relationship type is a safe Cypher identifier.

    A non-raising counterpart to ``validate_identifier``, for filtering a
    batch of names (for example ones read back from the database) rather
    than validating one name a caller must supply correctly.

    Args:
        value: The label or relationship type to check.

    Returns:
        ``True`` if ``value`` is a safe identifier.
    """
    return _IDENTIFIER.match(value) is not None and value != CANDIDATE_LABEL


def own_row_expression(row: str, job: str) -> str:
    """Build Cypher that is true when a row belongs to the writing job.

    A row belongs to a writer when its pending tag equals the writer's job
    id. A committed row has no tag, so it belongs only to a writer with no
    job. ``coalesce`` makes two missing values equal.

    Args:
        row: The Cypher alias of the node or relationship.
        job: The Cypher expression for the writer's job id, such as a
            parameter or a record field.

    Returns:
        A Cypher boolean expression.
    """
    return f"coalesce({row}.{PENDING_JOB_ID_PROPERTY}, '') = coalesce({job}, '')"


def upsert_node_query(labels: Sequence[str], *, extra_set: str = "") -> str:
    """Build the Cypher for an UNWIND-batched node upsert.

    MERGE identity is anchored to ``NODE_IDENTITY_LABEL``, not to ``labels``
    itself, so a node keeps resolving to the same id regardless of what
    labels it currently carries. ``labels`` is then applied additively with
    ``SET``, which is idempotent (a label the node already has is a no-op)
    and never removes a label a previous upsert of the same id set but this
    one omits: labels only ever accumulate. Every node in one call gets the
    same additive label set, since Cypher requires labels to be literal in
    the query text rather than a runtime parameter; nodes whose
    ``NodeRecord.labels`` differ need separate calls, one per distinct label
    set (see ``Neo4jGraphStore.upsert_nodes`` for how a mixed batch is
    grouped and split before reaching this builder).

    Identity is reasserted after applying properties, so a caller-supplied
    ``properties["id"]`` cannot overwrite the ``id`` used to ``MERGE`` and
    orphan the node from later upserts of the same record.

    The Cutover Job tag is set only when the ``MERGE`` creates the node, so
    the tag means "this job created this node". A write over a row the job
    did not create is not applied: the row reports ``written`` false, and the
    store defers the write to the job's commit transaction.

    Args:
        labels: The node's labels to add, in addition to the identity anchor.
            Must already be validated, and non-empty.
        extra_set: Extra ``SET`` clauses applied after the properties, for a
            backend that must convert some property values (such as embeddings)
            when it stores them. Empty by default.

    Returns:
        A parameterized Cypher query expecting a ``$records`` list parameter
        whose items carry ``id``, ``properties``, and ``pending_job_id``. It
        returns ``id`` and ``written`` for every record it matches.

    Raises:
        ValueError: ``labels`` is empty, or any label is not a safe
            identifier.
    """
    if not labels:
        raise ValueError("upsert_node_query requires at least one label")
    label_expr = ":".join(validate_identifier(label) for label in labels)
    own = own_row_expression("n", "record.pending_job_id")
    return (
        f"UNWIND $records AS record "
        f"MERGE (n:{NODE_IDENTITY_LABEL} {{id: record.id}}) "
        f"ON CREATE SET n.{PENDING_JOB_ID_PROPERTY} = record.pending_job_id "
        f"WITH n, record, {own} AS own "
        f"FOREACH (_ IN CASE WHEN own THEN [1] ELSE [] END | "
        f"SET n:{label_expr} "
        f"SET n += record.properties "
        f"{extra_set + ' ' if extra_set else ''}"
        f"SET n.id = record.id) "
        f"RETURN record.id AS id, own AS written"
    )


def fetch_by_merge_keys_query() -> str:
    """Build Cypher for a batched exact-match lookup by merge key.

    Resolves through the merge-key alias table (``MERGE_ALIAS_LABEL``)
    rather than matching each node's own ``merge_key`` property directly,
    so an accepted alternate name resolves to the entity that owns it.

    ``merge_key`` is returned alongside ``n`` so the caller can map a row
    back to the mention(s) that queried it without re-deriving a key from
    the resolved entity's current name: an accepted alias (see
    ``upsert_merge_alias_query``) can name an entity by something other
    than its current canonical name, so re-deriving would silently fail to
    map those mentions back.

    Returns:
        Parameterized Cypher expecting $merge_keys (list of strings) and
        $job_id (the in-flight Cutover Job's id, or null outside a job).
        An alias written by this same job resolves through the guard, so
        in-job exact-match lookups see the job's own writes; every other
        job's alias is excluded, and outside a job the guard reduces to
        committed-only.
    """
    return (
        f"UNWIND $merge_keys AS merge_key "
        f"MATCH (a:{MERGE_ALIAS_LABEL} {{merge_key: merge_key}}) "
        f"WHERE {pending_filter_clause('a', 'job_id')} "
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: a.entity_id}}) "
        f"WHERE {pending_filter_clause('n', 'job_id')} "
        f"RETURN merge_key, n"
    )


def upsert_merge_alias_query() -> str:
    """Build Cypher recording every accepted merge_key's owning entity id.

    Every ``apply_merge`` call writes one of these for each merge_key the
    merge accepted -- the survivor's own current name, but also every other
    name (mention text or absorbed entity's name) resolution folded into
    it -- so a later mention of any of those names resolves back to this
    entity instead of creating a duplicate. ``ON CREATE SET`` only claims a
    merge_key that has no alias yet: if resolution in some other merge
    already accepted this same key for a different entity, that entity
    keeps it. Without this, a resolution decision in one ``add()`` call
    could silently steal a name an unrelated entity already owns.

    Once created, an alias is never rewritten to point elsewhere.

    An alias written by an in-flight Cutover Job carries that job's id, so
    the exact-match lookup (which filters pending nodes) never resolves a
    mention into uncommitted data, and a rollback deletes the alias with
    the entity it names instead of leaving a dangling owner. A null
    ``pending_job_id`` sets no property, preserving today's behavior for
    callers outside a job.

    The returned rows are what let a caller detect the case ``ON CREATE
    SET`` alone cannot: an accepted merge_key already owned by some other
    live entity, not one this same merge is writing or absorbing. Neither
    entity's own node merge_key collides in that case, so nothing at the
    database level rejects the write; the caller must compare each row's
    entity_id against its own survivor id itself.

    Returns:
        Parameterized Cypher expecting $merge_keys (list of strings),
        $entity_id, and $pending_job_id (the in-flight job's id, or null
        outside a job — null sets no property). Returns each merge_key
        alongside the entity_id that now owns it -- $entity_id when this
        call claimed or already owned it, another entity's id when a
        different one claimed it first.
    """
    return (
        f"UNWIND $merge_keys AS merge_key "
        f"MERGE (a:{MERGE_ALIAS_LABEL} {{merge_key: merge_key}}) "
        f"ON CREATE SET a.entity_id = $entity_id, "
        f"a.{PENDING_JOB_ID_PROPERTY} = $pending_job_id "
        f"RETURN merge_key, a.entity_id AS entity_id"
    )


def upsert_survivor_query(labels: Sequence[str], *, extra_set: str = "") -> str:
    """Build Cypher upserting a merge survivor with atomic accumulation.

    Unlike ``upsert_node_query``'s plain ``SET n += record.properties``
    overwrite, ``source_chunk_ids`` is unioned against whatever the node
    currently has, and ``merge_count`` is incremented by a delta, all read
    and written inside this one query. Two concurrent
    callers merging into the same entity each read the node's current
    accumulator values fresh here, so neither's contribution is lost to
    whichever write lands second -- unlike overwriting from a full snapshot
    taken before either write landed. Every other property is still applied
    as-is (last write wins); resolving a conflict there needs the candidate
    values, which only a Python-side read can gather, so making that
    atomic too is out of scope here.

    The Cutover Job tag is set only when the ``MERGE`` creates the node. A
    write over a row the job did not create is not applied: the row reports
    ``written`` false, and the store defers the write to the job's commit
    transaction, where the accumulators are read again.

    Args:
        labels: The node's labels: the leaf label first, then ancestor
            labels. Must be non-empty. Each is validated here.
        extra_set: Extra ``SET`` clauses applied after the properties. Empty by
            default.

    Returns:
        A parameterized Cypher query expecting a ``$records`` list
        parameter whose items carry ``id``, ``properties`` (every survivor
        field except ``source_chunk_ids`` and ``merge_count``),
        ``pending_job_id`` (the Cutover Job tag, or None),
        ``new_source_chunk_ids``, and ``merge_count_delta``. It returns
        ``id`` and ``written`` for every record it matches.

    Raises:
        ValueError: ``labels`` is empty, or any label is not a safe
            identifier.
    """
    if not labels:
        raise ValueError("upsert_survivor_query requires at least one label")
    label_expr = ":".join(validate_identifier(label) for label in labels)
    own = own_row_expression("n", "record.pending_job_id")
    return (
        f"UNWIND $records AS record "
        f"MERGE (n:{NODE_IDENTITY_LABEL} {{id: record.id}}) "
        f"ON CREATE SET n.{PENDING_JOB_ID_PROPERTY} = record.pending_job_id "
        f"WITH n, record, {own} AS own, "
        f"coalesce(n.source_chunk_ids, []) AS existing_source_chunk_ids, "
        f"coalesce(n.merge_count, 0) AS existing_merge_count "
        f"FOREACH (_ IN CASE WHEN own THEN [1] ELSE [] END | "
        f"SET n:{label_expr} "
        f"SET n += record.properties "
        f"SET n.source_chunk_ids = [x IN existing_source_chunk_ids "
        f"WHERE NOT x IN record.new_source_chunk_ids] "
        f"+ record.new_source_chunk_ids "
        f"SET n.merge_count = existing_merge_count + record.merge_count_delta "
        f"{extra_set + ' ' if extra_set else ''}"
        f"SET n.id = record.id) "
        f"RETURN record.id AS id, own AS written"
    )


def set_embedding_query(
    vector_property: str, *, vector_value: str = "record.vector"
) -> str:
    """Build Cypher setting one vector property per node, guarded by its text.

    Touches only ``vector_property``, unlike a full node upsert: another
    write can update an entity's provenance or properties while its new
    embedding is being computed, and overwriting the whole node from a
    snapshot taken before that update would discard it along with
    delivering the vector. The ``name``/``description`` match is an
    optimistic-concurrency guard: a record only applies if the node's text
    still matches what its vector was computed from, so a slower write from
    an older call cannot overwrite a newer one's vector with a stale one.

    A record whose row the job did not create is not applied. Such a record
    belongs to a job, so the query returns it with ``written`` false and the
    store defers it: the vector is written at commit, after the text it was
    computed from. The text guard is not checked for those rows.

    Args:
        vector_property: The property to set. Must already be validated.
        vector_value: The Cypher expression stored in the property. Backends
            that need a typed vector pass ``GraphStore.vector_value(...)``.

    Returns:
        Parameterized Cypher expecting $records, a list of dicts with the keys
        id, vector, expected_name, expected_description, and pending_job_id.
        It returns ``id`` and ``written`` for each record whose guard passed
        and for each job record that reached a row the job did not create.
        A record the guard rejects gets no row, so a caller can tell which
        records were applied and which were skipped because a concurrent
        write already changed or removed the node.
    """
    safe_property = validate_identifier(vector_property)
    own = own_row_expression("n", "record.pending_job_id")
    return (
        f"UNWIND $records AS record "
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: record.id}}) "
        f"WITH n, record, {own} AS own "
        f"WHERE (own AND n.name = record.expected_name "
        f"AND coalesce(n.description, '') = record.expected_description) "
        f"OR (NOT own AND record.pending_job_id IS NOT NULL) "
        f"FOREACH (_ IN CASE WHEN own THEN [1] ELSE [] END | "
        f"SET n.{safe_property} = {vector_value}) "
        f"RETURN n.id AS id, own AS written"
    )


def clear_property_query(property_name: str) -> str:
    """Build Cypher removing one property from a batch of nodes, guarded by text.

    Used to drop a stale value rather than leave it readable after a write
    that was supposed to replace it fails partway through, such as an
    embedding vector left over from before an entity's text changed. The
    same ``name``/``description`` guard as ``set_embedding_query`` applies:
    a record only clears the property if the node's text still matches what
    this call started with, so it cannot wipe a vector a newer, still-in-
    flight call has already written for different text.

    A job clears only rows it created. A committed row is left as it is, so
    a job never removes a value it did not set.

    Args:
        property_name: The property to remove. Must already be validated.

    Returns:
        Parameterized Cypher expecting $records, a list of dicts with the keys
        id, expected_name, expected_description, and pending_job_id. It
        returns ``id`` and ``written`` for each record whose row the job owns
        and whose guard passed. Other records get no row.
    """
    safe_property = validate_identifier(property_name)
    own = own_row_expression("n", "record.pending_job_id")
    return (
        f"UNWIND $records AS record "
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: record.id}}) "
        f"WITH n, record, {own} AS own "
        f"WHERE own AND n.name = record.expected_name "
        f"AND coalesce(n.description, '') = record.expected_description "
        f"REMOVE n.{safe_property} "
        f"RETURN n.id AS id, own AS written"
    )


def fetch_all_by_label_query(label: str) -> str:
    """Build Cypher paginating every committed node with label.

    Nodes an in-flight Cutover Job wrote are excluded, so consolidation
    never resolves against uncommitted entities.

    Only nodes whose own (leaf) label is ``label`` are returned. A node of
    a child type also carries ``label`` as an ancestor label, but its
    merge_key starts with the child label, so the prefix test leaves it
    out. Resolution never merges across leaf labels.

    Args:
        label: The node label. Validated here.

    Returns:
        Parameterized Cypher expecting $skip and $limit.

    Raises:
        ValueError: ``label`` is not a safe identifier.
    """
    safe_label = validate_identifier(label)
    return (
        f"MATCH (n:{safe_label}) "
        f"WHERE {pending_filter_clause('n')} "
        f"AND n.merge_key STARTS WITH '{safe_label}:' "
        f"RETURN n ORDER BY n.id SKIP $skip LIMIT $limit"
    )


def fetch_relations_between_query(rel_type: str, *, job_id: str | None = None) -> str:
    """Build Cypher for batched lookup of existing relations by endpoints.

    Args:
        rel_type: The relationship type. Must already be validated.
        job_id: Optional parameter name for same-job pending visibility.

    Returns:
        Parameterized Cypher expecting $pairs (list of
        ``{source_id, target_id}``). Returns each match's id and
        source_chunk_ids alongside the pair it matched.
    """
    safe_type = validate_identifier(rel_type)
    pending = pending_filter_clause("r", job_id)
    return (
        f"UNWIND $pairs AS pair "
        f"MATCH (a:{NODE_IDENTITY_LABEL} {{id: pair.source_id}})"
        f"-[r:{safe_type}]->(b:{NODE_IDENTITY_LABEL} {{id: pair.target_id}}) "
        f"WHERE {pending} "
        f"RETURN pair.source_id AS source_id, pair.target_id AS target_id, "
        f"r.id AS id, r.source_chunk_ids AS source_chunk_ids"
    )


def fetch_entity_neighbors_query() -> str:
    """Build Cypher for a bounded, per-entity sample of neighboring relations.

    Reads committed rows only: an entity or relation an in-flight Cutover
    Job wrote is never sampled as context.

    Returns:
        Parameterized Cypher expecting ``$ids`` (entity id strings),
        ``$exclude_types`` (relation types to skip, such as resolution's own
        system relation types), and ``$limit`` (maximum neighbors returned
        per id). Returns ``entity_id``, ``rel_type``, and ``neighbor_name``
        for each sampled relation, in either direction.
    """
    return (
        "UNWIND $ids AS entity_id "
        "CALL { WITH entity_id "
        "MATCH (n:"
        f"{NODE_IDENTITY_LABEL} {{id: entity_id}})-[r]-(m:{NODE_IDENTITY_LABEL}) "
        "WHERE NOT type(r) IN $exclude_types "
        f"AND {pending_filter_clause('n')} "
        f"AND {pending_filter_clause('r')} "
        f"AND {pending_filter_clause('m')} "
        "RETURN type(r) AS rel_type, m.name AS neighbor_name "
        "LIMIT $limit "
        "} "
        "RETURN entity_id, rel_type, neighbor_name"
    )


def set_chunk_embedding_query(
    vector_property: str, *, vector_value: str = "record.vector"
) -> str:
    """Build Cypher setting a vector property on Chunk nodes.

    Similar to ``set_embedding_query`` but guards on ``text`` instead of
    ``name``/``description``, since chunks have no name field. The text
    guard prevents a stale write from overwriting a newer vector. A record
    whose row the job did not create is not applied and comes back with
    ``written`` false, so the store can defer it to the commit.

    Args:
        vector_property: The property to set. Must already be validated.
        vector_value: The Cypher expression stored in the property.

    Returns:
        Parameterized Cypher expecting $records, a list of dicts with the
        keys id, vector, expected_text, and pending_job_id. It returns
        ``id`` and ``written`` for each record whose guard passed and for
        each job record that reached a row the job did not create.
    """
    safe_property = validate_identifier(vector_property)
    own = own_row_expression("n", "record.pending_job_id")
    return (
        f"UNWIND $records AS record "
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: record.id}}) "
        f"WITH n, record, {own} AS own "
        f"WHERE (own AND n.text = record.expected_text) "
        f"OR (NOT own AND record.pending_job_id IS NOT NULL) "
        f"FOREACH (_ IN CASE WHEN own THEN [1] ELSE [] END | "
        f"SET n.{safe_property} = {vector_value}) "
        f"RETURN n.id AS id, own AS written"
    )


def clear_chunk_embedding_query(vector_property: str) -> str:
    """Build Cypher removing a vector property from Chunk nodes.

    Guards on ``text`` the same way ``set_chunk_embedding_query`` does,
    so a concurrent update that changed a chunk's text between this
    call's embed and its clear does not accidentally wipe a newer
    vector. A job clears only chunks it created, so a committed chunk is
    never changed by a job.

    Args:
        vector_property: The property to remove. Must already be
            validated.

    Returns:
        Parameterized Cypher expecting $records, a list of dicts with
        the keys id, expected_text, and pending_job_id. It returns ``id``
        and ``written`` for each record whose row the job owns and whose
        text guard passed. Other records get no row.
    """
    safe_property = validate_identifier(vector_property)
    own = own_row_expression("n", "record.pending_job_id")
    return (
        f"UNWIND $records AS record "
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: record.id}}) "
        f"WITH n, record, {own} AS own "
        f"WHERE own AND n.text = record.expected_text "
        f"REMOVE n.{safe_property} "
        f"RETURN n.id AS id, own AS written"
    )


def load_entities_by_id_query() -> str:
    """Build Cypher fetching committed entities by id.

    Returns:
        Parameterized Cypher expecting $ids (list of string ids). Nodes an
        in-flight Cutover Job wrote are excluded.
    """
    return (
        f"UNWIND $ids AS id "
        f"MATCH (n:{NODE_IDENTITY_LABEL} {{id: id}}) "
        f"WHERE n._pending_job_id IS NULL "
        f"RETURN n"
    )


def load_chunks_by_id_query() -> str:
    """Build Cypher fetching chunks by id.

    The query follows only currently valid ``HAS_PART`` edges, so superseded
    document versions cannot surface in retrieval. Chunks without any
    ``HAS_PART`` edge are also returned for direct or legacy chunk fixtures.

    Pending visibility is job-scoped: the storage stage runs inside its
    own job's pending phase and must see the chunks that same job just
    wrote (the partial-write fallback checks exactly those), while still
    excluding every other in-flight job's. A null ``$job_id`` reduces the
    guard to committed-only, which is what every caller outside a job
    passes.

    Returns:
        Parameterized Cypher expecting $ids (list of string ids) and
        $job_id (the in-flight job's id, or null outside a job).
    """
    return (
        f"UNWIND $ids AS id "
        f"MATCH (n:{NODE_IDENTITY_LABEL}:Chunk {{id: id}}) "
        "CALL { WITH n "
        f"MATCH (d:{NODE_IDENTITY_LABEL}:Document)-[p:{HAS_PART}]->(n) "
        f"WHERE {pending_filter_clause('p', 'job_id')} "
        "WITH 1 AS h LIMIT 1 RETURN count(h) AS pending_edges } "
        "CALL { WITH n "
        f"MATCH (d:{NODE_IDENTITY_LABEL}:Document)-[p:{HAS_PART}]->(n) "
        "WHERE p.invalid_at IS NULL "
        f"AND {pending_filter_clause('p', 'job_id')} "
        "WITH 1 AS h LIMIT 1 RETURN count(h) AS valid_edges } "
        "WITH n, pending_edges, valid_edges "
        "WHERE (pending_edges = 0 OR valid_edges > 0) "
        f"AND {pending_filter_clause('n', 'job_id')} "
        f"RETURN n"
    )


def filter_clause(
    filters: dict[str, Any], node_var: str = "node"
) -> tuple[str, dict[str, Any]]:
    """Build a Cypher WHERE clause and parameters from a flat-dict filter.

    Args:
        filters: A flat-dict filter: a scalar value means exact match, a list
            value means any of, and all keys are AND-ed together.
        node_var: The Cypher variable bound to the node in the surrounding query.

    Returns:
        The ``WHERE`` clause text (beginning with ``WHERE`` when ``filters`` is
        non-empty, otherwise an empty string) and the parameter dict to pass
        with it.
    """
    if not filters:
        return "", {}
    clauses: list[str] = []
    params: dict[str, Any] = {}
    for key, value in filters.items():
        field = validate_identifier(key)
        param = f"filter_{field}"
        if isinstance(value, list):
            clauses.append(f"{node_var}.{field} IN ${param}")
        else:
            clauses.append(f"{node_var}.{field} = ${param}")
        params[param] = value
    return "WHERE " + " AND ".join(clauses), params
