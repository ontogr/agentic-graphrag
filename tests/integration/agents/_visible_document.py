"""Seed the document node that makes a test chunk visible to evidence discovery.

Discovery reads a chunk only when a committed Document node holds it through an
open HAS_PART edge, and the chunk carries that document's current content hash.
The agent tests write chunks directly, so they need this node as well.
"""

import hashlib
from uuid import UUID

from agrag.common.data_models.chunk import CHUNK_LABEL
from agrag.common.data_models.document import DOCUMENT_LABEL, Document
from agrag.common.data_models.structure import HAS_PART
from agrag.cypher.entities import NODE_IDENTITY_LABEL
from agrag.graphdb.base import GraphStore


def document_content_hash(document_key: str) -> str:
    """Return the content hash shared by every chunk of one test document."""
    return hashlib.sha256(document_key.encode("utf-8")).hexdigest()


async def seed_document_part(
    store: GraphStore, *, document_key: str, chunk_id: UUID
) -> None:
    """Hold one chunk under its document, the way ingestion does.

    Args:
        store: The connected graph store.
        document_key: The key of the document the chunk belongs to.
        chunk_id: The id of a chunk already written with CHUNK_LABEL.
    """
    await store.execute_write(
        f"MERGE (d:{NODE_IDENTITY_LABEL}:{DOCUMENT_LABEL} {{id: $document_id}}) "
        "SET d.document_key = $document_key, "
        "d.current_content_hash = $content_hash "
        f"WITH d MATCH (c:{CHUNK_LABEL} {{id: $chunk_id}}) "
        f"MERGE (d)-[:{HAS_PART}]->(c)",
        {
            "document_id": str(Document.node_id_for(document_key=document_key)),
            "document_key": document_key,
            "content_hash": document_content_hash(document_key),
            "chunk_id": str(chunk_id),
        },
    )


async def delete_documents(store: GraphStore, document_keys: list[str]) -> None:
    """Delete the document nodes a test wrote, after its chunks are gone."""
    await store.execute_write(
        f"MATCH (d:{DOCUMENT_LABEL}) WHERE d.document_key IN $keys DETACH DELETE d",
        {"keys": document_keys},
    )
