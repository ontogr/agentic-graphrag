"""Write and bookkeeping logic shared by graph stores that speak Cypher."""

import array
import json
import numbers
from abc import abstractmethod
from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from opentelemetry.trace import Span, SpanKind, Tracer

from agrag.common.data_models.candidate import (
    CANDIDATE_EDGE_TYPES,
    CANDIDATE_LABEL,
    CandidateRecord,
)
from agrag.common.data_models.graph_record import (
    DeferredWrites,
    NodeRecord,
    RelationRecord,
    UpsertFailure,
    UpsertResult,
)
from agrag.common.data_models.vector_record import VectorHit
from agrag.common.validation import require_positive_batch_size
from agrag.cypher.candidates import (
    blocked_candidate_keys_query,
    upsert_candidates_query,
)
from agrag.cypher.entities import (
    MERGE_ALIAS_LABEL,
    NODE_IDENTITY_LABEL,
    is_safe_identifier,
    upsert_node_query,
    validate_identifier,
)
from agrag.cypher.relations import upsert_relation_query
from agrag.cypher.schema import list_relation_types_query, vector_search_query
from agrag.graphdb.base import GraphStore
from agrag.graphdb.serialize import candidate_params, node_params, relation_params
from agrag.observability import (
    DB_COLLECTION_NAME,
    DB_OPERATION_BATCH_SIZE,
    DB_QUERY_PARAMETER_PREFIX,
    get_tracer,
)


def _is_number(value: Any) -> bool:
    """Return whether ``value`` is a real number, excluding booleans."""
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


def _is_vector_value(value: Any) -> bool:
    """Return whether ``value`` is an embedding vector.

    A vector is a non-empty list, tuple, set, or array whose items are all
    numbers, or a numeric numpy-style array. Vectors are excluded from
    span attributes; only the remaining parameter values are recorded.
    """
    if isinstance(value, array.array):
        return len(value) > 0 and all(_is_number(item) for item in value)
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0 and all(_is_number(item) for item in value)
    dtype = getattr(value, "dtype", None)
    if (
        dtype is not None
        and hasattr(value, "tolist")
        and getattr(dtype, "kind", None) in ("i", "u", "f")
    ):
        size = getattr(value, "size", None)
        return size is None or size > 0
    return False


def _strip_vector_fields(value: Any) -> Any:
    """Return ``value`` with vector-valued fields removed.

    Vector-valued mapping fields are dropped and vector items are
    dropped from sequences and sets; the rest is kept as is, recursing
    into nested mappings and sequences.
    """
    if isinstance(value, Mapping):
        return {
            key: _strip_vector_fields(item)
            for key, item in value.items()
            if not _is_vector_value(item)
        }
    if isinstance(value, list):
        return [
            _strip_vector_fields(item) for item in value if not _is_vector_value(item)
        ]
    if isinstance(value, tuple):
        return tuple(
            _strip_vector_fields(item) for item in value if not _is_vector_value(item)
        )
    if isinstance(value, (set, frozenset)):
        return {
            _strip_vector_fields(item) for item in value if not _is_vector_value(item)
        }
    if isinstance(value, array.array):
        return list(value)
    return value


def _serialize_param_value(value: Any) -> str:
    """Serialize a stripped parameter value to a span attribute string.

    Scalars use ``str()``; dicts, lists, tuples, and sets use
    ``json.dumps`` (``default=str`` so UUIDs and other non-JSON scalars
    still serialize), with ``str()`` as the fallback for anything
    ``json.dumps`` rejects.
    """
    if isinstance(value, (dict, list, tuple, set, frozenset)):
        try:
            if isinstance(value, (set, frozenset)):
                return json.dumps(sorted(value, key=repr), default=str)
            return json.dumps(value, default=str)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


# Parameters that carry user search text. They never become span attributes.
_UNTRACED_PARAMETERS = frozenset({"fulltext_terms"})


def query_parameter_attributes(
    parameters: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Build ``db.query.parameter.<key>`` span attributes.

    Skips vector-valued parameters, skips the untraced user-text parameters, and
    strips vector-valued fields from nested dictionaries (including nested record
    dicts) before serializing each value to a string.
    """
    if not parameters:
        return {}
    attributes: dict[str, str] = {}
    for key, value in parameters.items():
        if _is_vector_value(value) or key in _UNTRACED_PARAMETERS:
            continue
        attributes[f"{DB_QUERY_PARAMETER_PREFIX}{key}"] = _serialize_param_value(
            _strip_vector_fields(value)
        )
    return attributes


def require_deferred(
    pending_job_id: UUID | None, deferred: DeferredWrites | None
) -> None:
    """Reject a job write that has nowhere to put deferred writes."""
    if pending_job_id is not None and deferred is None:
        raise ValueError("deferred is required when pending_job_id is set")


# The vector search procedure selects its top-k candidates before a WHERE
# filter runs, so a filtered call can return fewer than the requested limit
# even when enough matching nodes exist. Escalate k geometrically and retry
# until enough filtered hits come back or this ceiling is reached, matching
# the practical limit of a single vector query's k on a single vector query's k.
_VECTOR_SEARCH_OVERFETCH_MULTIPLIER = 4
_VECTOR_SEARCH_MAX_K = 1000


class CypherGraphStore(GraphStore):
    """A ``GraphStore`` for databases that run the shared Cypher builders.

    Holds the record grouping, batching, per-record failure isolation and label
    bookkeeping that every Cypher backend needs. A backend supplies its
    connection, query execution, schema statements and error classification.
    """

    def __init__(self, *, tracer: Tracer | None = None) -> None:
        """Set up the bookkeeping that the shared write methods use.

        Args:
            tracer: Opens every span this store's methods produce.
        """
        self._tracer = get_tracer(tracer)
        self._known_labels: set[str] = set()
        self._known_relation_types: set[str] = set()

    @abstractmethod
    async def _ensure_identity_constraint(self) -> None:
        """Make node ids unique across every node label, once."""

    @abstractmethod
    async def _ensure_relation_constraint(self, rel_type: str) -> None:
        """Make relationship ids unique within one type, once."""

    @abstractmethod
    async def _ensure_candidate_schema(self) -> None:
        """Create the candidate constraints and indexes, once."""

    @staticmethod
    @abstractmethod
    def _is_record_specific_error(exc: Exception) -> bool:
        """Return whether a database error can be caused by one record."""

    @staticmethod
    @abstractmethod
    def _is_missing_index_error(exc: Exception) -> bool:
        """Return whether a search failed because the index does not exist."""

    async def register_labels(self, labels: Sequence[str]) -> None:
        """Add labels to this instance's known-label set.

        Args:
            labels: The labels to register. Each must be a safe Cypher
                identifier.

        Raises:
            ValueError: Any label is not a safe identifier.
        """
        for label in labels:
            validate_identifier(label)
        self._known_labels.update(labels)

    async def register_relation_types(self, types: Sequence[str]) -> None:
        """Add types to this instance's known-relation-type set.

        Args:
            types: The relationship types to register. Each must be a safe
                Cypher identifier.

        Raises:
            ValueError: Any type is not a safe identifier.
        """
        for rel_type in types:
            validate_identifier(rel_type)
        self._known_relation_types.update(types)

    async def _all_labels(self) -> set[str]:
        """Return every node label this instance knows about.

        Combines labels written through this instance with every label
        already present in the database, so setup does not depend on this
        instance having written the data itself. A live label outside this
        store's stricter identifier subset (Neo4j itself allows names our
        Cypher builders cannot safely interpolate unquoted, such as ones with
        spaces or hyphens) is skipped rather than raised, so one such name
        left over from other tooling cannot block every other constraint.

        Returns:
            Labels excluding internal labels with dedicated constraints.
        """
        rows = await self.execute_read("CALL db.labels() YIELD label RETURN label")
        live = {
            row["label"]
            for row in rows
            if row["label"]
            not in {NODE_IDENTITY_LABEL, MERGE_ALIAS_LABEL, CANDIDATE_LABEL}
            and is_safe_identifier(row["label"])
        }
        return self._known_labels | live

    async def _all_relation_types(self) -> set[str]:
        """Return every relationship type this instance knows about.

        Combines types written through this instance with every type already
        present in the database, so setup does not depend on this instance
        having written the data itself. A live type outside this store's
        stricter identifier subset is skipped rather than raised, so one such
        name left over from other tooling cannot block every other
        constraint.

        Returns:
            The relationship type names.
        """
        rows = await self.execute_read(list_relation_types_query())
        live = {
            row["relationshipType"]
            for row in rows
            if is_safe_identifier(row["relationshipType"])
        }
        return self._known_relation_types | live

    async def upsert_nodes(
        self,
        label: str,
        nodes: Sequence[NodeRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult:
        """Write or merge nodes, honoring each record's full label set.

        ``label`` names the batch for constraint/index bookkeeping, matching
        every other tracked label; the labels actually written to a node come
        from ``NodeRecord.labels``, which may name more than one label (for
        example a node that is both ``Chunk`` and ``Entity``). Records with
        different label sets are grouped and written with separate ``MERGE``
        queries, since Cypher requires labels to be literal in the query text
        rather than a runtime parameter, so ``batch_size`` chunks apply within
        each group rather than across the whole call.

        ``pending_job_id`` tags only the nodes this call creates. A write that
        reaches a node the job did not create is not applied and is added to
        ``deferred``, so a job's rollback cannot change data committed earlier.

        Returns:
            The number written or deferred, and one failure entry for each
            isolated record.

        Raises:
            ValueError: ``batch_size`` is not positive, or ``deferred`` is
                missing while ``pending_job_id`` is set.
        """
        require_deferred(pending_job_id, deferred)
        with self._tracer.start_as_current_span(
            "agrag.graphdb.upsert_nodes",
            kind=SpanKind.INTERNAL,
            attributes={
                DB_COLLECTION_NAME: label,
                "agrag.record_count": len(nodes),
            },
        ) as span:
            require_positive_batch_size(batch_size)
            validate_identifier(label)
            await self._ensure_identity_constraint()
            self._known_labels.add(label)
            groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
            outcome = UpsertResult()
            for node in nodes:
                labels = tuple(sorted(set(node.labels)))
                try:
                    for node_label in labels:
                        validate_identifier(node_label)
                except ValueError as exc:
                    outcome.failures.append(
                        UpsertFailure(
                            id=str(node.id),
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )
                    continue
                self._known_labels.update(labels)
                groups[labels].append(node_params(node, pending_job_id=pending_job_id))
            # Records are chunked within each label group, so the largest
            # group bounds the biggest batch any of them can submit.
            self._record_batch_size(
                span,
                max((len(group) for group in groups.values()), default=0),
                batch_size,
            )
            for labels, records in groups.items():
                query = upsert_node_query(labels, extra_set=self.node_write_extra_set())
                batch_result = await self._batch_write(
                    query, records, batch_size, deferred=deferred
                )
                outcome.written += batch_result.written
                outcome.failures.extend(batch_result.failures)
            span.set_attribute("agrag.written", outcome.written)
            span.set_attribute("agrag.failures_count", len(outcome.failures))
            return outcome

    async def upsert_relations(
        self,
        relations: Sequence[RelationRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult:
        """Write or merge relationships between existing nodes.

        Relationship identity is each record's ``id``, not its endpoints: see
        ``upsert_relation_query`` for how endpoint changes and same-id
        parallel relationships are handled. ``pending_job_id`` tags only the
        relationships this call creates. A write that reaches a relationship
        the job did not create is not applied and is added to ``deferred``.

        Returns:
            The number written or deferred, and one failure entry for each
            isolated record.

        Raises:
            ValueError: ``batch_size`` is not positive, or ``deferred`` is
                missing while ``pending_job_id`` is set.
        """
        require_deferred(pending_job_id, deferred)
        with self._tracer.start_as_current_span(
            "agrag.graphdb.upsert_relations",
            kind=SpanKind.INTERNAL,
            attributes={
                "agrag.record_count": len(relations),
            },
        ) as span:
            require_positive_batch_size(batch_size)
            by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
            outcome = UpsertResult()
            for rel in relations:
                try:
                    validate_identifier(rel.type)
                    if rel.type in CANDIDATE_EDGE_TYPES:
                        raise ValueError(
                            f"{rel.type!r} is reserved for the candidate store"
                        )
                except ValueError as exc:
                    outcome.failures.append(
                        UpsertFailure(
                            id=str(rel.id),
                            error_type=type(exc).__name__,
                            error_message=str(exc),
                        )
                    )
                    continue
                by_type[rel.type].append(
                    relation_params(rel, pending_job_id=pending_job_id)
                )
            # Records are chunked within each type group, so the largest
            # group bounds the biggest batch any of them can submit.
            self._record_batch_size(
                span,
                max((len(group) for group in by_type.values()), default=0),
                batch_size,
            )
            for rel_type, params in by_type.items():
                await self._ensure_relation_constraint(rel_type)
                self._known_relation_types.add(rel_type)
                query = upsert_relation_query(rel_type)
                batch_result = await self._batch_write(
                    query,
                    params,
                    batch_size,
                    require_returned_ids=True,
                    deferred=deferred,
                )
                outcome.written += batch_result.written
                outcome.failures.extend(batch_result.failures)
            span.set_attribute("agrag.written", outcome.written)
            span.set_attribute("agrag.failures_count", len(outcome.failures))
            return outcome

    async def upsert_candidates(
        self,
        candidates: Sequence[CandidateRecord],
        *,
        batch_size: int = 256,
        pending_job_id: UUID | None = None,
    ) -> UpsertResult:
        """Write candidates without changing nodes that already exist."""
        with self._tracer.start_as_current_span(
            "agrag.graphdb.upsert_candidates",
            kind=SpanKind.INTERNAL,
            attributes={"agrag.record_count": len(candidates)},
        ) as span:
            require_positive_batch_size(batch_size)
            await self._ensure_candidate_schema()
            for edge_type in sorted(CANDIDATE_EDGE_TYPES):
                await self._ensure_relation_constraint(edge_type)
            self._known_relation_types.update(CANDIDATE_EDGE_TYPES)
            blocked = await self.blocked_candidate_keys(
                [record.key for record in candidates]
            )
            outcome = UpsertResult()
            records = []
            for record in candidates:
                if record.key in blocked:
                    outcome.failures.append(
                        UpsertFailure(
                            id=str(record.id),
                            error_type="ReviewedKeyBlocked",
                            error_message="a reviewed candidate with this key exists",
                        )
                    )
                    continue
                records.append(candidate_params(record, pending_job_id=pending_job_id))
            batch_outcome = await self._batch_write(
                upsert_candidates_query(),
                records,
                batch_size,
                require_returned_ids=True,
            )
            outcome.written += batch_outcome.written
            outcome.failures.extend(batch_outcome.failures)
            span.set_attribute("agrag.written", outcome.written)
            span.set_attribute("agrag.failures_count", len(outcome.failures))
            return outcome

    async def blocked_candidate_keys(self, keys: Sequence[str]) -> set[str]:
        """Return keys with a committed candidate that is not pending."""
        if not keys:
            return set()
        rows = await self.execute_read(
            blocked_candidate_keys_query(), {"keys": list(keys)}
        )
        return {str(row["key"]) for row in rows}

    async def vector_search(
        self,
        *,
        label: str,
        vector_property: str,
        query_vector: Sequence[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[VectorHit]:
        """Search nodes by dense vector using the native vector index.

        A label with no provisioned vector index has nothing to search,
        so an absent index returns an empty result list rather than a
        driver error.

        Neo4j's vector procedure applies pending and caller filters only after
        selecting its top ``k`` candidates, so a plain ``k=limit`` call can
        return fewer matches than actually exist. This escalates ``k`` and
        retries until ``limit`` visible hits come back or the escalation
        reaches ``_VECTOR_SEARCH_MAX_K``.

        Raises:
            ValueError: ``limit`` is not positive. A non-positive value is
                not a meaningful request and would send that same
                non-positive ``k`` to Neo4j's native vector procedure, which
                requires a positive top-k.
        """
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit}")
        validate_identifier(label)
        validate_identifier(vector_property)
        call = await self.vector_search_call(
            label=label, vector_property=vector_property
        )
        query, filter_params = vector_search_query(call.text, filters)
        with self._tracer.start_as_current_span(
            "agrag.graphdb.vector_search",
            kind=SpanKind.INTERNAL,
            attributes={DB_COLLECTION_NAME: label, "agrag.limit": limit},
        ) as span:
            k = limit
            rows: list[dict[str, Any]] = []
            while True:
                params: dict[str, Any] = {
                    **filter_params,
                    **call.params,
                    "k": k,
                    "vector": list(query_vector),
                }
                try:
                    rows = await self.execute_read(query, params)
                except Exception as exc:
                    # A label with no provisioned vector index (for example a
                    # filter naming a label that was never ingested) has nothing
                    # to search, so return empty instead of failing the whole
                    # retrieval. Any other driver error keeps propagating.
                    if not self._is_missing_index_error(exc):
                        raise
                    span.record_exception(exc)
                    span.set_attribute("agrag.index_missing", True)
                    return []
                if len(rows) >= limit or k >= _VECTOR_SEARCH_MAX_K:
                    break
                k = min(k * _VECTOR_SEARCH_OVERFETCH_MULTIPLIER, _VECTOR_SEARCH_MAX_K)
            span.set_attribute("agrag.k_final", k)
        hits: list[VectorHit] = []
        for row in rows[:limit]:
            node = row["node"]
            node_props = dict(node)
            node_props.pop(vector_property, None)
            node_props.pop("id", None)
            hits.append(
                VectorHit(
                    id=UUID(node["id"]),
                    score=float(row["score"]),
                    payload=node_props,
                )
            )
        return hits

    async def _batch_write(
        self,
        query: str,
        records: Sequence[dict[str, Any]],
        batch_size: int,
        *,
        require_returned_ids: bool = False,
        deferred: DeferredWrites | None = None,
    ) -> UpsertResult:
        """Run batched writes, isolating failures that belong to one record."""
        outcome = UpsertResult()
        for start in range(0, len(records), batch_size):
            batch = records[start : start + batch_size]
            try:
                rows = await self.execute_write(query, {"records": batch})
            except Exception as exc:  # noqa: BLE001
                if not self._is_record_specific_error(exc):
                    raise
                for record in batch:
                    try:
                        rows = await self.execute_write(query, {"records": [record]})
                    except Exception as item_exc:  # noqa: BLE001
                        if not self._is_record_specific_error(item_exc):
                            raise
                        outcome.failures.append(
                            UpsertFailure(
                                id=str(record["id"]),
                                error_type=type(item_exc).__name__,
                                error_message=str(item_exc),
                            )
                        )
                        continue
                    outcome.written += self._settle_rows(
                        query,
                        [record],
                        rows,
                        deferred=deferred,
                        outcome=outcome,
                        require_returned_ids=require_returned_ids,
                    )
                continue
            outcome.written += self._settle_rows(
                query,
                batch,
                rows,
                deferred=deferred,
                outcome=outcome,
                require_returned_ids=require_returned_ids,
            )
        return outcome

    @staticmethod
    def _settle_rows(
        query: str,
        batch: Sequence[dict[str, Any]],
        rows: Sequence[dict[str, Any]],
        *,
        deferred: DeferredWrites | None,
        outcome: UpsertResult,
        require_returned_ids: bool,
    ) -> int:
        """Record each sent record's outcome from the rows a write returned.

        With ``require_returned_ids``, a record with no returned row is a
        missing relationship endpoint and is reported as a failure. A row
        that reports ``written`` false belongs to another job: it is deferred
        when ``deferred`` is set and is a ``PendingRowConflict`` failure
        otherwise.

        Returns:
            The number of records the write applied or deferred.
        """
        returned_ids = {str(row["id"]) for row in rows}
        if require_returned_ids:
            found: list[dict[str, Any]] = []
            for record in batch:
                if str(record["id"]) in returned_ids:
                    found.append(record)
                else:
                    outcome.failures.append(
                        UpsertFailure(
                            id=str(record["id"]),
                            error_type="MissingEndpoint",
                            error_message="relationship endpoint does not exist",
                        )
                    )
            batch = found
        unwritten = {str(row["id"]) for row in rows if row.get("written") is False}
        if not unwritten:
            return len(batch)
        if deferred is not None:
            deferred.add_unwritten(query, batch, rows)
            return len(batch)
        applied = 0
        for record in batch:
            if str(record["id"]) in unwritten:
                outcome.failures.append(
                    UpsertFailure(
                        id=str(record["id"]),
                        error_type="PendingRowConflict",
                        error_message="row belongs to an in-flight job",
                    )
                )
            else:
                applied += 1
        return applied

    @staticmethod
    def _record_batch_size(span: Span | None, records: int, batch_size: int) -> None:
        """Record the size of the batch a write actually submits.

        The value describes records sent in one round trip, not the
        configured ``batch_size``: a caller writing fewer records than the
        limit submits one smaller batch, so reporting the limit there would
        misstate the round trip.

        It is set only where a batch really exists. A single record is one
        operation, not a batch, so the attribute is left off. An explicitly
        empty write records ``0``, which is distinguishable from the absent
        attribute a one-record write leaves. ``span`` is optional because
        this is also called from paths with no traced operation.
        """
        if span is None:
            return
        if records == 0:
            span.set_attribute(DB_OPERATION_BATCH_SIZE, 0)
        elif records > 1:
            span.set_attribute(DB_OPERATION_BATCH_SIZE, min(records, batch_size))
