"""Evidence-linked decisions scoped to one project."""

import asyncio
import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_OID, UUID, uuid5

from pydantic import TypeAdapter

from agrag.common.data_models.decision import (
    DECISION_LABEL,
    DEPENDS_ON,
    HAS_SUPPORT,
    MADE,
    SUPERSEDES,
    SUPPORT_LABEL,
    ConflictGroup,
    ConflictList,
    Decision,
    DecisionHit,
    DecisionLookup,
    DecisionPage,
    DecisionPageLookup,
    DecisionReviewList,
    DecisionStatus,
    DecisionSupport,
    DecisionSupportInput,
    DocumentSupport,
    DocumentSupportInput,
    EventSupport,
    EventSupportInput,
    ReaffirmDecisionResult,
    RecordDecisionResult,
    RejectDecisionResult,
    ReviewState,
    Support,
    SupportHistoryPage,
    SupportInput,
    SupportKind,
)
from agrag.common.data_models.evidence import FetchOutcome, FetchStatus
from agrag.common.data_models.memory_result import MemoryErrorCode
from agrag.common.data_models.task import (
    PROJECT_LABEL,
    REQUEST_LABEL,
    TASK_LABEL,
    EventKind,
)
from agrag.cypher.memory import (
    append_event_query,
    claim_request_query,
    create_decision_query,
    decision_by_id_query,
    decision_page_query,
    decision_status_query,
    find_task_query,
    memory_schema_queries,
    set_event_id_query,
    store_request_result_query,
)
from agrag.cypher.memory_review import (
    REVIEW_CHILD_PAGE_SIZE,
    claim_review_unit_query,
    clear_decision_review_query,
    current_document_query,
    expand_review_unit_query,
    finish_review_propagation_query,
    flag_new_decision_for_review_query,
    next_support_ordinal_query,
    queue_superseded_decision_query,
    replace_document_supports_query,
    support_history_query,
)
from agrag.cypher.schema import fulltext_index_name
from agrag.evidence.ids import MalformedEvidenceIdError, decode_evidence_id
from agrag.graphdb.base import GraphStore, GraphStoreTransaction
from agrag.graphdb.errors import GraphStoreConstraintViolationError


MAX_DECISIONS = 100
DECISION_PAGE_LIMIT = 20


class _DecisionRefusedError(ValueError):
    """A validation failure that must roll back the current write."""

    def __init__(self, code: MemoryErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


def _uuid(*parts: str | int | UUID) -> UUID:
    return uuid5(NAMESPACE_OID, json.dumps([str(part) for part in parts]))


def _digest(operation: str, arguments: dict[str, Any]) -> str:
    body = json.dumps(
        {"operation": operation, "arguments": arguments},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _decision_from_row(row: dict[str, Any]) -> Decision:
    """Validate a decision row and its typed supports.

    While a project's review propagation is pending, clear decisions read as
    unknown.
    """
    raw = dict(row["decision"])
    if row.get("review_incomplete") and raw.get("review_state", "clear") == "clear":
        raw["review_state"] = ReviewState.UNKNOWN.value
    raw["task_name"] = row["task_name"]
    raw["supports"] = [dict(support) for support in row["supports"] if support]
    return Decision.model_validate(raw)


class DecisionMemory:
    """Write and search durable decisions for one configured project."""

    def __init__(self, store: GraphStore, *, project_id: str, agent_id: str) -> None:
        """Bind decision operations to a project and an author."""
        self._store = store
        self._project_id = project_id
        self._agent_id = agent_id
        self._schema_ready = False
        self._schema_lock = asyncio.Lock()

    async def record_decision(
        self,
        task_name: str,
        choice_key: str,
        conclusion: str,
        rationale: str,
        *,
        supports: Sequence[SupportInput],
        fetched_evidence: Sequence[FetchOutcome] = (),
        assumptions: Sequence[str] = (),
        open_questions: Sequence[str] = (),
        request_id: str | None = None,
    ) -> RecordDecisionResult:
        """Record a decision only when every support is valid and in scope.

        Document evidence must appear in ``fetched_evidence`` with status
        ``ok``. All checks and writes share one graph transaction.
        """
        if not supports:
            return RecordDecisionResult(
                recorded=False, error=MemoryErrorCode.SUPPORT_REQUIRED
            )
        args = {
            "task_name": task_name,
            "choice_key": choice_key,
            "conclusion": conclusion,
            "rationale": rationale,
            "supports": [s.model_dump(mode="json") for s in supports],
            "assumptions": list(assumptions),
            "open_questions": list(open_questions),
            "fetched_evidence": [
                item.model_dump(mode="json") for item in fetched_evidence
            ],
        }
        return await self._write(
            "record_decision",
            args,
            request_id,
            RecordDecisionResult,
            lambda tx: self._record(
                tx,
                task_name=task_name,
                choice_key=choice_key,
                conclusion=conclusion,
                rationale=rationale,
                supports=supports,
                fetched=fetched_evidence,
                assumptions=assumptions,
                open_questions=open_questions,
                supersedes=None,
                explanation=None,
            ),
        )

    async def supersede_decision(
        self,
        decision_id: UUID,
        conclusion: str,
        rationale: str,
        *,
        explanation: str,
        supports: Sequence[SupportInput],
        fetched_evidence: Sequence[FetchOutcome] = (),
        assumptions: Sequence[str] = (),
        open_questions: Sequence[str] = (),
        request_id: str | None = None,
    ) -> RecordDecisionResult:
        """Record a same-choice replacement and preserve the old decision."""
        if not explanation.strip():
            return RecordDecisionResult(
                recorded=False, error=MemoryErrorCode.EXPLANATION_REQUIRED
            )
        old = await self.get_decision(decision_id)
        if not old.found or old.decision is None:
            return RecordDecisionResult(
                recorded=False, error=MemoryErrorCode.SUPERSEDE_TARGET_INVALID
            )
        current = old.decision
        args = {
            "old_id": str(decision_id),
            "conclusion": conclusion,
            "rationale": rationale,
            "explanation": explanation,
            "supports": [s.model_dump(mode="json") for s in supports],
            "assumptions": list(assumptions),
            "open_questions": list(open_questions),
            "fetched_evidence": [
                item.model_dump(mode="json") for item in fetched_evidence
            ],
        }
        return await self._write(
            "supersede_decision",
            args,
            request_id,
            RecordDecisionResult,
            lambda tx: self._record(
                tx,
                task_name=current.task_name,
                choice_key=current.choice_key,
                conclusion=conclusion,
                rationale=rationale,
                supports=supports,
                fetched=fetched_evidence,
                assumptions=assumptions,
                open_questions=open_questions,
                supersedes=decision_id,
                explanation=explanation,
            ),
        )

    async def reject_decision(
        self, decision_id: UUID, reason: str, *, request_id: str | None = None
    ) -> RejectDecisionResult:
        """Mark a decision rejected without changing its recorded conclusion."""
        args = {"id": str(decision_id), "reason": reason}
        return await self._write(
            "reject_decision",
            args,
            request_id,
            RejectDecisionResult,
            lambda tx: self._reject(tx, decision_id, reason),
        )

    async def reaffirm_decision(
        self,
        decision_id: UUID,
        evidence: Sequence[DocumentSupportInput],
        *,
        fetched_evidence: Sequence[FetchOutcome] = (),
        explanation: str = "Reaffirmed after review.",
        request_id: str | None = None,
    ) -> ReaffirmDecisionResult:
        """Confirm a decision still stands on the current version of its documents.

        Review means the decision needs a look. It does not mean the decision
        is false. Reaffirming records the caller as the reviewer, replaces the
        decision's document supports with ``evidence``, and clears the review
        flag. It does not change the flags of dependent decisions.

        Every document the decision cites must be fetched in its current
        version, and ``evidence`` must cite exactly those documents. A cited
        document that is removed, or whose current version was not fetched
        with status ``ok``, fails with ``cannot_revalidate`` and the decision
        stays flagged. So does a decision that depends on another decision
        still needing review.

        Args:
            decision_id: The id of the active decision to reaffirm.
            evidence: The new document supports, one or more per cited document.
            fetched_evidence: Fetch outcomes from this session. They must cover
                the current version of each cited document.
            explanation: The reason the reviewer accepts the current supports.
            request_id: An optional key that makes a retry return the stored
                result of the first call.

        Returns:
            The reaffirmed decision, or a result with an error code.
        """
        args = {
            "id": str(decision_id),
            "evidence": [item.model_dump(mode="json") for item in evidence],
            "fetched_evidence": [
                item.model_dump(mode="json") for item in fetched_evidence
            ],
            "explanation": explanation,
        }
        return await self._write(
            "reaffirm_decision",
            args,
            request_id,
            ReaffirmDecisionResult,
            lambda tx: self._reaffirm(
                tx,
                decision_id,
                evidence=evidence,
                fetched=fetched_evidence,
                explanation=explanation,
            ),
        )

    async def get_decision(self, decision_id: UUID) -> DecisionLookup:
        """Read a decision only when it belongs to this project."""
        rows = await self._store.execute_read(
            decision_by_id_query(),
            {"project_id": self._project_id, "id": str(decision_id)},
        )
        return DecisionLookup(
            found=bool(rows), decision=_decision_from_row(rows[0]) if rows else None
        )

    async def continue_review_propagation(self, *, limit: int = 100) -> int:
        """Expand at most ``limit`` queued decisions by one dependency hop each."""
        processed = 0
        for _ in range(max(0, min(limit, 100))):

            async def process(tx: GraphStoreTransaction) -> bool:
                claimed = await tx.execute_write(
                    claim_review_unit_query(), {"project_id": self._project_id}
                )
                if not claimed:
                    return False
                decision_id = claimed[0].get("id")
                if decision_id:
                    await tx.execute_write(
                        expand_review_unit_query(),
                        {
                            "project_id": self._project_id,
                            "decision_id": decision_id,
                            "page_limit": REVIEW_CHILD_PAGE_SIZE + 1,
                            "child_limit": REVIEW_CHILD_PAGE_SIZE,
                        },
                    )
                await tx.execute_write(
                    finish_review_propagation_query(),
                    {"project_id": self._project_id},
                )
                return bool(decision_id)

            if not await self._store.run_in_transaction(process):
                break
            processed += 1
        return processed

    async def list_support_history(
        self, decision_id: UUID, *, after_ordinal: int = -1, limit: int = 20
    ) -> SupportHistoryPage:
        """Read exact historical support associations and who reviewed them."""
        size = max(1, min(limit, 100))
        rows = await self._store.execute_read(
            support_history_query(),
            {
                "project_id": self._project_id,
                "id": str(decision_id),
                "after_ordinal": after_ordinal,
                "limit": size + 1,
            },
        )
        return SupportHistoryPage(
            supports=[
                TypeAdapter(Support).validate_python(dict(row["support"]))
                for row in rows[:size]
            ],
            truncated=len(rows) > size,
            next_after_ordinal=rows[size - 1]["support"]["ordinal"]
            if len(rows) > size
            else None,
        )

    async def list_review(
        self, *, task_name: str | None = None, limit: int = 20
    ) -> DecisionReviewList:
        """List active decisions that need a look, within this project's bounds.

        A listed decision is flagged because a source or a decision it depends
        on changed. Review means it needs a look, not that it is false. Use
        ``reaffirm_decision``, ``supersede_decision`` or ``reject_decision`` to
        clear the flag.

        Args:
            task_name: Only list decisions of this task, or all tasks if None.
            limit: The number of decisions to return, capped at the page limit.

        Returns:
            The decisions in the page, the total count, and whether more exist.
        """
        size = max(1, min(limit, DECISION_PAGE_LIMIT))
        rows = await self._store.execute_read(
            f"MATCH (t:{TASK_LABEL} {{project_id: $project_id}})-[:{MADE}]->"
            f"(d:{DECISION_LABEL} {{status: 'active'}}) "
            "MATCH (p:MemoryProject {project_id: $project_id}) "
            "WHERE (d.review_state = 'needs_review' OR "
            "p.review_incomplete) "
            "AND ($task_name IS NULL OR t.name = $task_name) "
            f"OPTIONAL MATCH (d)-[:{HAS_SUPPORT}]->"
            f"(s:{SUPPORT_LABEL} {{current: true}}) "
            "WITH t, d, p, s ORDER BY s.current DESC, s.ordinal "
            "WITH t, d, p, collect(s) AS supports "
            "RETURN d AS decision, supports, t.name AS task_name, "
            "p.review_incomplete AS review_incomplete "
            "ORDER BY d.created_at DESC LIMIT $limit",
            {
                "project_id": self._project_id,
                "task_name": task_name,
                "limit": size + 1,
            },
        )
        count_rows = await self._store.execute_read(
            f"MATCH (t:{TASK_LABEL} {{project_id: $project_id}})-[:{MADE}]->"
            f"(d:{DECISION_LABEL} {{status: 'active'}}) "
            "MATCH (p:MemoryProject {project_id: $project_id}) "
            "WHERE (d.review_state = 'needs_review' OR "
            "p.review_incomplete) "
            "AND ($task_name IS NULL OR t.name = $task_name) "
            "RETURN count(d) AS count",
            {"project_id": self._project_id, "task_name": task_name},
        )
        count = int(count_rows[0]["count"])
        decisions = [_decision_from_row(row) for row in rows[:size]]
        return DecisionReviewList(
            decisions=decisions, count=count, truncated=count > size
        )

    async def list_decisions(
        self, task_name: str, *, include_history: bool = True
    ) -> DecisionPageLookup:
        """List decisions for a task, including lifecycle history by default."""
        rows = await self._store.execute_read(
            decision_page_query(),
            {
                "project_id": self._project_id,
                "task_name": task_name,
                "limit": DECISION_PAGE_LIMIT + 1,
                "include_history": include_history,
            },
        )
        count_rows = await self._store.execute_read(
            f"MATCH (t:{TASK_LABEL} {{project_id: $project_id, name: $task_name}})"
            f"-[:{MADE}]->(d:{DECISION_LABEL}) "
            "WHERE $include_history OR d.status = 'active' RETURN count(d) AS count",
            {
                "project_id": self._project_id,
                "task_name": task_name,
                "include_history": include_history,
            },
        )
        if not rows:
            task = await self._store.execute_read(
                find_task_query(), {"project_id": self._project_id, "name": task_name}
            )
            return DecisionPageLookup(found=bool(task))
        decisions = [_decision_from_row(row) for row in rows]
        count = int(count_rows[0]["count"])
        return DecisionPageLookup(
            found=True,
            page=DecisionPage(
                decisions=decisions[:DECISION_PAGE_LIMIT],
                count=count,
                truncated=count > DECISION_PAGE_LIMIT,
            ),
        )

    async def search_decisions(
        self, query: str, *, task_name: str | None = None, limit: int = 20
    ) -> list[DecisionHit]:
        """Find same-project decisions as precedents, with their task context."""
        size = max(1, min(limit, MAX_DECISIONS))
        rows = await self._store.execute_read(
            "CALL db.index.fulltext.queryNodes($index, $query) YIELD node, score "
            f"MATCH (t:{TASK_LABEL} {{project_id: $project_id}})-[:{MADE}]->(node) "
            f"WHERE node:{DECISION_LABEL} AND node.status = 'active' "
            "AND ($task_name IS NULL OR t.name = $task_name) "
            f"OPTIONAL MATCH (node)-[:{HAS_SUPPORT}]->"
            f"(s:{SUPPORT_LABEL} {{current: true}}) "
            "OPTIONAL MATCH (p:MemoryProject {project_id: $project_id}) "
            "WITH node, score, t, p, s ORDER BY s.current DESC, s.ordinal "
            "WITH node, score, t, p, collect(s) AS supports "
            "RETURN node AS decision, supports, t.name AS task_name, "
            "t.goal AS task_goal, score, "
            "coalesce(p.review_incomplete, false) AS review_incomplete "
            "ORDER BY score DESC LIMIT $limit",
            {
                "index": fulltext_index_name(
                    DECISION_LABEL, ["conclusion", "rationale"]
                ),
                "query": query,
                "project_id": self._project_id,
                "task_name": task_name,
                "limit": size + 1,
            },
        )
        return [
            DecisionHit(decision=_decision_from_row(row), task_goal=row["task_goal"])
            for row in rows[:size]
        ]

    async def list_conflicts(self) -> ConflictList:
        """List active same-choice decisions with different conclusions."""
        rows = await self._store.execute_read(
            f"MATCH (t:{TASK_LABEL} {{project_id: $project_id}})-[:{MADE}]->"
            f"(d:{DECISION_LABEL} {{status: 'active'}}) "
            "WITH d.choice_key AS choice_key, collect(d) AS decisions, "
            "collect(DISTINCT d.conclusion) AS conclusions, "
            "collect(DISTINCT t.name) AS task_names "
            "WHERE size(conclusions) > 1 AND size(task_names) > 1 "
            "RETURN choice_key, [d IN decisions[..51] | d.id] AS ids, "
            "size(decisions) AS count "
            "ORDER BY choice_key LIMIT 51",
            {"project_id": self._project_id},
        )
        groups = []
        for row in rows[:50]:
            ids = row["ids"][:50]
            decisions = []
            if ids:
                found = await self._store.execute_read(
                    f"MATCH (t:{TASK_LABEL} {{project_id: $project_id}})-[:{MADE}]->"
                    f"(d:{DECISION_LABEL}) WHERE d.id IN $ids "
                    "OPTIONAL MATCH (p:MemoryProject {project_id: $project_id}) "
                    f"OPTIONAL MATCH (d)-[:{HAS_SUPPORT}]->"
                    f"(s:{SUPPORT_LABEL} {{current: true}}) "
                    "WITH d, t, p, s ORDER BY s.current DESC, s.ordinal "
                    "WITH d, t, p, collect(s) AS supports "
                    "RETURN d AS decision, supports, t.name AS task_name, "
                    "coalesce(p.review_incomplete, false) AS review_incomplete",
                    {"project_id": self._project_id, "ids": ids},
                )
                decisions = [_decision_from_row(item) for item in found]
            groups.append(
                ConflictGroup(
                    choice_key=row["choice_key"],
                    decisions=decisions,
                    truncated=row["count"] > len(ids),
                )
            )
        return ConflictList(groups=groups, truncated=len(rows) > 50)

    async def _record(
        self,
        tx: GraphStoreTransaction,
        *,
        task_name: str,
        choice_key: str,
        conclusion: str,
        rationale: str,
        supports: Sequence[SupportInput],
        fetched: Sequence[FetchOutcome],
        assumptions: Sequence[str],
        open_questions: Sequence[str],
        supersedes: UUID | None,
        explanation: str | None,
    ) -> RecordDecisionResult:
        task_rows = await tx.execute_read(
            "MATCH (t:MemoryTask {project_id: $project_id, name: $name}) RETURN t",
            {"project_id": self._project_id, "name": task_name},
        )
        if not task_rows:
            raise _DecisionRefusedError(MemoryErrorCode.TASK_NOT_FOUND)
        task = task_rows[0]["t"]
        await tx.execute_write(
            "MATCH (t:MemoryTask {id: $id, project_id: $project_id}) "
            "SET t.id = t.id RETURN t.id AS id",
            {"id": task["id"], "project_id": self._project_id},
        )
        choice_rows = await tx.execute_read(
            f"MATCH (t:{TASK_LABEL} {{project_id: $project_id, name: $name}})"
            f"-[:{MADE}]->(d:{DECISION_LABEL} {{choice_key: $choice_key}}) "
            "RETURN collect(d) AS decisions",
            {
                "project_id": self._project_id,
                "name": task_name,
                "choice_key": choice_key,
            },
        )
        revisions = choice_rows[0]["decisions"] if choice_rows else []
        if supersedes is not None:
            await tx.execute_write(
                f"MATCH (d:{DECISION_LABEL} {{id: $id, project_id: $project_id}}) "
                "SET d.id = d.id RETURN d.id AS id",
                {"id": str(supersedes), "project_id": self._project_id},
            )
            choice_rows = await tx.execute_read(
                f"MATCH (t:{TASK_LABEL} {{project_id: $project_id, name: $name}})"
                f"-[:{MADE}]->(d:{DECISION_LABEL} {{choice_key: $choice_key}}) "
                "RETURN collect(d) AS decisions",
                {
                    "project_id": self._project_id,
                    "name": task_name,
                    "choice_key": choice_key,
                },
            )
            revisions = choice_rows[0]["decisions"] if choice_rows else []
        active = [decision for decision in revisions if decision["status"] == "active"]
        old_decision = (
            max(active, key=lambda decision: decision["revision"]) if active else None
        )
        if revisions and supersedes is None:
            raise _DecisionRefusedError(MemoryErrorCode.CHOICE_EXISTS)
        if supersedes is not None and (
            old_decision is None or old_decision["id"] != str(supersedes)
        ):
            raise _DecisionRefusedError(MemoryErrorCode.SUPERSEDE_TARGET_INVALID)
        if not supports:
            raise _DecisionRefusedError(MemoryErrorCode.SUPPORT_REQUIRED)
        support_props, currency_changed = await self.resolve_supports(
            tx, supports, fetched
        )
        revision = max((int(item["revision"]) for item in revisions), default=0) + 1
        identity = str(_uuid("Decision", task["id"], choice_key, revision))
        created = datetime.now(UTC)
        status_review = (
            ReviewState.NEEDS_REVIEW if currency_changed else ReviewState.CLEAR
        )
        props = {
            "id": identity,
            "task_id": task["id"],
            "project_id": self._project_id,
            "choice_key": choice_key,
            "revision": revision,
            "conclusion": conclusion,
            "rationale": rationale,
            "assumptions": list(assumptions),
            "open_questions": list(open_questions),
            "author": self._agent_id,
            "status": DecisionStatus.ACTIVE.value,
            "review_state": status_review.value,
            "review_reason": "source_changed_during_recording"
            if currency_changed
            else None,
            "rejection_reason": None,
            "rejected_by": None,
            "created_at": created.isoformat(),
            "supersession_explanation": explanation,
        }
        await tx.execute_write(
            create_decision_query(),
            {
                "project_id": self._project_id,
                "task_id": task["id"],
                "decision": props,
                "supports": [
                    {
                        **support,
                        "id": str(_uuid("Support", identity, index)),
                        "current": True,
                        "project_id": self._project_id,
                        "target_decision_id": str(support["decision_id"])
                        if support["kind"] == "decision"
                        else None,
                    }
                    for index, support in enumerate(support_props)
                ],
            },
        )
        await tx.execute_write(
            flag_new_decision_for_review_query(),
            {"project_id": self._project_id, "decision_id": identity},
        )
        if supersedes is not None:
            await tx.execute_write(
                queue_superseded_decision_query(),
                {
                    "project_id": self._project_id,
                    "id": str(supersedes),
                    "new_id": identity,
                },
            )
        lookup = await self._get_decision_tx(tx, identity)
        return RecordDecisionResult(
            recorded=True,
            decision=lookup,
            warnings=["source_changed_during_recording"] if currency_changed else [],
        )

    async def _reject(
        self, tx: GraphStoreTransaction, decision_id: UUID, reason: str
    ) -> RejectDecisionResult:
        lookup = await self._get_decision_tx(tx, str(decision_id))
        if lookup is None:
            raise _DecisionRefusedError(MemoryErrorCode.DECISION_NOT_FOUND)
        task_rows = await tx.execute_read(
            "MATCH (t:MemoryTask {id: $id, project_id: $project_id}) RETURN t.id AS id",
            {"id": str(lookup.task_id), "project_id": self._project_id},
        )
        if not task_rows:
            raise _DecisionRefusedError(MemoryErrorCode.DECISION_NOT_FOUND)
        await tx.execute_write(
            "MATCH (t:MemoryTask {id: $id, project_id: $project_id}) "
            "SET t.id = t.id RETURN t.id AS id",
            {"id": str(lookup.task_id), "project_id": self._project_id},
        )
        await tx.execute_write(
            f"MATCH (d:{DECISION_LABEL} {{id: $id, project_id: $project_id}}) "
            "SET d.id = d.id RETURN d.id AS id",
            {"id": str(decision_id), "project_id": self._project_id},
        )
        lookup = await self._get_decision_tx(tx, str(decision_id))
        if lookup is None:
            raise _DecisionRefusedError(MemoryErrorCode.DECISION_NOT_FOUND)
        if lookup.status is not DecisionStatus.ACTIVE:
            raise _DecisionRefusedError(MemoryErrorCode.DECISION_NOT_ACTIVE)
        await tx.execute_write(
            decision_status_query(),
            {
                "project_id": self._project_id,
                "id": str(decision_id),
                "status": DecisionStatus.REJECTED.value,
                "reason": reason,
                "by": self._agent_id,
            },
        )
        await tx.execute_write(
            finish_review_propagation_query(), {"project_id": self._project_id}
        )
        return RejectDecisionResult(
            recorded=True, decision=await self._get_decision_tx(tx, str(decision_id))
        )

    async def _reaffirm(
        self,
        tx: GraphStoreTransaction,
        decision_id: UUID,
        *,
        evidence: Sequence[DocumentSupportInput],
        fetched: Sequence[FetchOutcome],
        explanation: str,
    ) -> ReaffirmDecisionResult:
        lookup = await self._get_decision_tx(tx, str(decision_id))
        if lookup is None:
            raise _DecisionRefusedError(MemoryErrorCode.DECISION_NOT_FOUND)
        if lookup.status is not DecisionStatus.ACTIVE:
            raise _DecisionRefusedError(MemoryErrorCode.DECISION_NOT_ACTIVE)
        await tx.execute_write(
            f"MATCH (d:{DECISION_LABEL} {{id: $id, project_id: $project_id}}) "
            "SET d.id = d.id RETURN d.id AS id",
            {"id": str(decision_id), "project_id": self._project_id},
        )
        cited = {
            str(support.document_node_id)
            for support in lookup.supports
            if isinstance(support, DocumentSupport) and support.current
        }
        for document_id in cited:
            if not await self._is_revalidated(tx, document_id, fetched):
                raise _DecisionRefusedError(MemoryErrorCode.CANNOT_REVALIDATE)
        for support in lookup.supports:
            if isinstance(support, EventSupport):
                await self._event_support(
                    tx, EventSupportInput(task_name=support.task_name, seq=support.seq)
                )
            if not isinstance(support, DecisionSupport):
                continue
            parent = await self._get_decision_tx(tx, str(support.decision_id))
            if (
                parent is None
                or parent.status is not DecisionStatus.ACTIVE
                or parent.review_state is not ReviewState.CLEAR
            ):
                raise _DecisionRefusedError(MemoryErrorCode.CANNOT_REVALIDATE)
        pending = await tx.execute_read(
            f"MATCH (p:{PROJECT_LABEL} {{project_id: $project_id}}) "
            "RETURN coalesce(p.review_incomplete, false) AS incomplete",
            {"project_id": self._project_id},
        )
        if pending and pending[0]["incomplete"]:
            raise _DecisionRefusedError(MemoryErrorCode.CANNOT_REVALIDATE)
        try:
            support_props, changed = await self.resolve_supports(tx, evidence, fetched)
        except _DecisionRefusedError as refused:
            if refused.code in (
                MemoryErrorCode.SUPPORT_NOT_FETCHED,
                MemoryErrorCode.SUPPORT_DOCUMENT_NOT_FOUND,
            ):
                raise _DecisionRefusedError(MemoryErrorCode.CANNOT_REVALIDATE) from None
            raise
        cited_by_evidence = {str(item["document_node_id"]) for item in support_props}
        if changed or cited_by_evidence != cited:
            raise _DecisionRefusedError(MemoryErrorCode.CANNOT_REVALIDATE)
        created = datetime.now(UTC)
        ordinal_rows = await tx.execute_read(
            next_support_ordinal_query(),
            {"project_id": self._project_id, "id": str(decision_id)},
        )
        await tx.execute_write(
            replace_document_supports_query(),
            {
                "project_id": self._project_id,
                "decision_id": str(decision_id),
                "reviewer": self._agent_id,
                "reviewed_at": created.isoformat(),
                "explanation": explanation,
                "supports": [
                    {
                        **support,
                        "id": str(
                            _uuid(
                                "Support",
                                decision_id,
                                "reaffirm",
                                created.isoformat(),
                                index,
                            )
                        ),
                        "project_id": self._project_id,
                        "ordinal": ordinal_rows[0]["ordinal"] + index,
                        "current": True,
                        "reviewed_by": self._agent_id,
                        "reviewed_at": created.isoformat(),
                        "review_explanation": explanation,
                    }
                    for index, support in enumerate(support_props)
                ],
            },
        )
        await tx.execute_write(
            clear_decision_review_query(),
            {"project_id": self._project_id, "decision_id": str(decision_id)},
        )
        await self._append_note(
            tx,
            task_id=lookup.task_id,
            payload=f"Decision {decision_id} reaffirmed.",
        )
        return ReaffirmDecisionResult(
            recorded=True, decision=await self._get_decision_tx(tx, str(decision_id))
        )

    async def _is_revalidated(
        self,
        tx: GraphStoreTransaction,
        document_id: str,
        fetched: Sequence[FetchOutcome],
    ) -> bool:
        """Check that the document is live and that a fetch returned its version."""
        rows = await tx.execute_read(current_document_query(), {"id": document_id})
        if not rows or not rows[0]["live"] or rows[0]["hash"] is None:
            return False
        return any(
            item.status is FetchStatus.OK
            and item.document_key == rows[0]["key"]
            and item.content_hash == rows[0]["hash"]
            and item.reference is not None
            and str(item.reference.document_node_id) == document_id
            for item in fetched
        )

    async def _append_note(
        self, tx: GraphStoreTransaction, *, task_id: UUID, payload: str
    ) -> None:
        """Append a note event to a task, recorded by this agent."""
        rows = await tx.execute_write(
            append_event_query(),
            {
                "project_id": self._project_id,
                "task_id": str(task_id),
                "kind": EventKind.NOTE.value,
                "role": None,
                "name": None,
                "payload": payload,
                "payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
                "truncated": False,
                "author": self._agent_id,
                "at": datetime.now(UTC).isoformat(),
            },
        )
        seq = int(rows[0]["seq"])
        await tx.execute_write(
            set_event_id_query(),
            {
                "task_id": str(task_id),
                "seq": seq,
                "id": str(_uuid("Event", task_id, seq)),
            },
        )

    async def resolve_supports(
        self,
        tx: GraphStoreTransaction,
        supports: Sequence[SupportInput],
        fetched: Sequence[FetchOutcome],
    ) -> tuple[list[dict[str, Any]], bool]:
        """Resolve typed supports in a caller-owned transaction.

        Returns property maps and whether any observed source has changed.
        Raises ValueError when a reference cannot be resolved or was not fetched.
        """
        if len(supports) > 20:
            raise _DecisionRefusedError(MemoryErrorCode.SUPPORT_REQUIRED)
        support_props: list[dict[str, Any]] = []
        currency_changed = False
        decision_ids = sorted(
            {
                support.decision_id
                for support in supports
                if isinstance(support, DecisionSupportInput)
            }
        )
        for decision_id in decision_ids:
            await tx.execute_write(
                f"MATCH (d:{DECISION_LABEL} {{id: $id, project_id: $project_id}}) "
                "SET d.id = d.id RETURN d.id AS id",
                {"id": decision_id, "project_id": self._project_id},
            )
        for source in supports:
            if isinstance(source, DocumentSupportInput):
                value, changed = await self._document_support(tx, source, fetched)
                currency_changed |= changed
            elif isinstance(source, EventSupportInput):
                value = await self._event_support(tx, source)
            elif isinstance(source, DecisionSupportInput):
                decision = await self._get_decision_tx(tx, source.decision_id)
                if decision is None:
                    raise _DecisionRefusedError(
                        MemoryErrorCode.SUPPORT_DECISION_NOT_FOUND
                    )
                if decision.status is not DecisionStatus.ACTIVE:
                    raise _DecisionRefusedError(
                        MemoryErrorCode.SUPPORT_DECISION_NOT_ACTIVE
                    )
                value = DecisionSupport(
                    kind=SupportKind.DECISION, decision_id=UUID(str(decision.id))
                ).model_dump(mode="json")
            else:
                raise _DecisionRefusedError(MemoryErrorCode.SUPPORT_MALFORMED)
            support_props.append({**value, "ordinal": len(support_props)})
        return support_props, currency_changed

    async def _document_support(
        self,
        tx: GraphStoreTransaction,
        source: DocumentSupportInput,
        fetched: Sequence[FetchOutcome],
    ) -> tuple[dict[str, Any], bool]:
        """Validate fetched document currency and capture its current activation."""
        try:
            ref = decode_evidence_id(source.evidence_id)
        except MalformedEvidenceIdError:
            raise _DecisionRefusedError(MemoryErrorCode.SUPPORT_MALFORMED) from None
        outcome = next(
            (item for item in fetched if item.evidence_id == source.evidence_id), None
        )
        if (
            outcome is None
            or outcome.status is not FetchStatus.OK
            or outcome.reference != ref
            or not outcome.content_hash
        ):
            raise _DecisionRefusedError(MemoryErrorCode.SUPPORT_NOT_FETCHED)
        doc_id = str(ref.document_node_id)
        docs = await tx.execute_read(
            "MATCH (doc:Document {id: $id}) RETURN doc.document_key AS key",
            {"id": doc_id},
        )
        if not docs or docs[0]["key"] != outcome.document_key:
            raise _DecisionRefusedError(MemoryErrorCode.SUPPORT_DOCUMENT_NOT_FOUND)
        if outcome.observed_activation_seq is None:
            raise _DecisionRefusedError(MemoryErrorCode.SUPPORT_NOT_FETCHED)
        current = (
            await tx.execute_read(
                "MATCH (doc:Document {id: $id}) RETURN doc.document_key AS key, "
                "doc.current_content_hash AS hash, doc.activation_seq AS seq",
                {"id": doc_id},
            )
        )[0]
        changed = (
            current["hash"] != outcome.content_hash
            or current["seq"] != outcome.observed_activation_seq
        )
        support = DocumentSupport(
            kind=SupportKind.DOCUMENT,
            evidence_id=source.evidence_id,
            document_key=current["key"],
            document_node_id=ref.document_node_id,
            content_hash_prefix=ref.content_hash_prefix,
            content_hash=outcome.content_hash,
            reference_kind=ref.kind,
            char_start=ref.char_start,
            char_end=ref.char_end,
            chunk_id=ref.chunk_id,
            recorded_activation_seq=outcome.observed_activation_seq,
        ).model_dump(mode="json")
        return support, changed

    async def _event_support(
        self, tx: GraphStoreTransaction, source: EventSupportInput
    ) -> dict[str, Any]:
        """Resolve an event only inside this project."""
        rows = await tx.execute_read(
            "MATCH (t:MemoryTask {project_id: $project_id, name: $name})"
            "-[:HAS_EVENT]->(e:MemoryEvent {seq: $seq}) "
            "RETURN e.id AS id, e.redacted_at AS redacted_at",
            {
                "project_id": self._project_id,
                "name": source.task_name,
                "seq": source.seq,
            },
        )
        if not rows:
            raise _DecisionRefusedError(MemoryErrorCode.SUPPORT_EVENT_NOT_FOUND)
        if rows[0]["redacted_at"] is not None:
            raise _DecisionRefusedError(MemoryErrorCode.CANNOT_REVALIDATE)
        return EventSupport(
            kind=SupportKind.EVENT,
            event_id=rows[0]["id"],
            task_name=source.task_name,
            seq=source.seq,
        ).model_dump(mode="json")

    async def _get_decision_tx(
        self, tx: GraphStoreTransaction, decision_id: str
    ) -> Decision | None:
        rows = await tx.execute_read(
            decision_by_id_query(), {"project_id": self._project_id, "id": decision_id}
        )
        return _decision_from_row(rows[0]) if rows else None

    async def _write(
        self,
        operation: str,
        arguments: dict[str, Any],
        request_id: str | None,
        result_type: Any,
        effect: Any,
    ) -> Any:
        if request_id is not None and not 0 < len(request_id) <= 64:
            return result_type(recorded=False, error=MemoryErrorCode.INVALID_REQUEST_ID)
        await self._ensure_schema()
        digest = _digest(operation, arguments)

        async def work(tx: GraphStoreTransaction) -> Any:
            if request_id is None:
                return await effect(tx)
            rows = await tx.execute_write(
                claim_request_query(),
                {
                    "project_id": self._project_id,
                    "request_id": request_id,
                    "id": str(_uuid("Request", self._project_id, request_id)),
                    "operation": operation,
                    "payload_sha256": digest,
                },
            )
            claim = rows[0]
            if claim["payload_sha256"] != digest:
                raise _DecisionRefusedError(MemoryErrorCode.REQUEST_ID_REUSED)
            if claim["result_json"] is not None:
                return result_type.model_validate_json(claim["result_json"])
            result = await effect(tx)
            await tx.execute_write(
                store_request_result_query(),
                {
                    "project_id": self._project_id,
                    "request_id": request_id,
                    "result_json": result.model_dump_json(),
                },
            )
            return result

        try:
            return await self._store.run_in_transaction(work)
        except _DecisionRefusedError as error:
            return result_type(recorded=False, error=error.code)
        except GraphStoreConstraintViolationError:
            try:
                return await self._store.run_in_transaction(work)
            except _DecisionRefusedError as error:
                return result_type(recorded=False, error=error.code)

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        async with self._schema_lock:
            if self._schema_ready:
                return
            await self._store.register_labels(
                [
                    DECISION_LABEL,
                    SUPPORT_LABEL,
                    REQUEST_LABEL,
                    TASK_LABEL,
                    PROJECT_LABEL,
                ]
            )
            await self._store.register_relation_types(
                [MADE, HAS_SUPPORT, DEPENDS_ON, SUPERSEDES]
            )
            for query in memory_schema_queries():
                await self._store.execute_write(query)
            await self._store.ensure_fulltext_index(
                label=DECISION_LABEL, properties=["conclusion", "rationale"]
            )
            self._schema_ready = True
