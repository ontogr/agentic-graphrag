"""Shared fake-store helpers for the ingestion unit tests.

``CutoverJobLeaseFake`` implements the lease protocol's query contracts on
top of any existing fake GraphStore: acquire (first claimant wins),
compare-and-swap status transitions fenced by the lease token, tag
clearing, and rollback. Everything else is forwarded to the wrapped
store's implementation unchanged, so assertions on recorded calls keep
working.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from agrag.cypher.cutover_job_write import (
    acquire_lease_query,
    claim_job_query,
    clear_pending_tag_query,
    commit_job_query,
    finish_cleaning_query,
    rollback_job_query,
    start_cleaning_query,
    steal_expired_lease_query,
)
from agrag.cypher.relations import close_part_of_query


class CutoverJobLeaseFake:
    """Mixin adding the Cutover Job query contracts to a fake store.

    Attributes:
        closed_part_of_edges: The count the PART_OF close reports, so a
            test can assert the number of superseded document edges
            without standing up a graph.
        persisted_jobs: The job table, keyed by document_key.
    """

    closed_part_of_edges: int
    persisted_jobs: dict[str, dict[str, Any]]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Create the mixin's job table before the wrapped store's init."""
        self.persisted_jobs = {}
        self.closed_part_of_edges = 0
        super().__init__(*args, **kwargs)

    @property
    def _cutover_jobs(self) -> dict[str, dict[str, Any]]:
        """The job table, created on first use for stores that skip __init__."""
        jobs = getattr(self, "persisted_jobs", None)
        if jobs is None:
            jobs = self.persisted_jobs = {}
        return jobs

    def handle_cutover_query(
        self, query: str, parameters: Mapping[str, Any] | None = None
    ) -> list[dict[str, Any]] | None:
        """Run one Cutover Job query against the in-memory job table.

        Args:
            query: The Cypher text to dispatch on.
            parameters: The query's parameters.

        Returns:
            The rows the query yields, or None when ``query`` is not a
            Cutover Job query and the caller should handle it.
        """
        handler = self._handlers().get(query)
        if handler is None:
            return None
        return handler(dict(parameters or {}))

    def _handlers(self) -> dict[str, Any]:
        """Map each Cutover Job query to its in-memory implementation."""
        return {
            acquire_lease_query(): self._acquire,
            steal_expired_lease_query(): self._steal,
            commit_job_query(): lambda p: self._transition(p, "pending", "committed"),
            start_cleaning_query(): lambda p: self._transition(
                p, "committed", "cleaning"
            ),
            finish_cleaning_query(): lambda p: self._transition(p, "cleaning", "done"),
            claim_job_query(): self._claim,
            clear_pending_tag_query(): self._clear_tags,
            rollback_job_query(): self._rollback,
            close_part_of_query(): self._close_part_of,
        }

    def _acquire(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """MERGE on document_key: the first claimant creates the job node."""
        key = str(params["document_key"])
        job = self._cutover_jobs.get(key)
        if job is None:
            job = {
                "id": str(params["job_id"]),
                "status": "pending",
                "verb": params["verb"],
                "lease_token": str(params["lease_token"]),
                "lease_expires_at": datetime.fromisoformat(
                    str(params["lease_expires_at"])
                ),
            }
            self._cutover_jobs[key] = job
        return [{"lease_token": job["lease_token"], "status": job["status"]}]

    def _claim(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Take a committed or cleaning job over for roll-forward."""
        for job in self._cutover_jobs.values():
            if job["id"] == str(params["job_id"]) and job["status"] in (
                "committed",
                "cleaning",
            ):
                job["status"] = "cleaning"
                job["lease_token"] = str(params["lease_token"])
                return [{"status": "cleaning"}]
        return []

    def _clear_tags(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Report the tag clear; the fake holds no tagged nodes."""
        del params
        return [{"cleared_nodes": 0, "cleared_relationships": 0}]

    def _rollback(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Mark the named job rolled back."""
        for job in self._cutover_jobs.values():
            if job["id"] == str(params["job_id"]):
                job["status"] = "rolled_back"
        return [{"deleted_nodes": 0, "deleted_relationships": 0}]

    def _close_part_of(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Report the configured superseded-edge count."""
        del params
        # A fake whose __init__ skipped the mixin's has no count yet.
        return [{"closed": getattr(self, "closed_part_of_edges", 0)}]

    def _steal(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Take over a job only when its lease lapsed or it went terminal.

        Mirrors ``steal_expired_lease_query``: the steal adopts the new
        run's id, verb, token, and expiry, so a document that has been
        mutated before can be mutated again.
        """
        job = self._cutover_jobs.get(str(params["document_key"]))
        if job is None:
            return []
        expired = job["lease_expires_at"] < datetime.now(UTC)
        if job["status"] in ("done", "rolled_back") or (
            job["status"] == "pending" and expired
        ):
            job["id"] = str(params["job_id"])
            job["status"] = "pending"
            job["verb"] = params["verb"]
            job["lease_token"] = str(params["lease_token"])
            job["lease_expires_at"] = datetime.fromisoformat(
                str(params["lease_expires_at"])
            )
            return [{"lease_token": job["lease_token"]}]
        return []

    def _transition(
        self, params: dict[str, Any], expected: str, nxt: str
    ) -> list[dict[str, Any]]:
        """Compare-and-swap a job's status, fenced by its lease token."""
        for job in self._cutover_jobs.values():
            if (
                job["id"] == str(params["job_id"])
                and job["lease_token"] == str(params["lease_token"])
                and job["status"] == expected
            ):
                job["status"] = nxt
                return [{"id": job["id"]}]
        return []
