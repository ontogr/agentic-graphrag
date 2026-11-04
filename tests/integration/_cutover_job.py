"""Creates live Cutover Jobs for tests that write pending rows.

A write tagged with a job id runs only while that job is pending with a live
lease, so a test needs the job node before its first pending write. The test
removes the node with the rest of its data, by ``document_key``.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from agrag.cypher.cutover_job_write import acquire_lease_query
from agrag.graphdb.base import GraphStore


async def create_live_job(store: GraphStore, document_key: str) -> UUID:
    """Create a pending job with a one-hour lease and return its id."""
    job_id = uuid4()
    now = datetime.now(UTC)
    await store.execute_write(
        acquire_lease_query(),
        {
            "job_id": str(job_id),
            "document_key": document_key,
            "verb": "add",
            "lease_token": str(uuid4()),
            "lease_expires_at": int((now + timedelta(hours=1)).timestamp() * 1000),
            "affected_entity_ids": [],
            "created_at": now.isoformat(),
        },
    )
    return job_id
