"""The ingest cache: a marker node in each corpus's own Neo4j instance.

The cache key covers everything that changes the graph, so a matching marker
means the stored graph is what a new ingest would build.
"""

import json
from collections.abc import Collection
from dataclasses import dataclass

from agrag.graphdb import GraphStore
from benchmarks.harness.record import GraphStats, PathUsage
from benchmarks.models import CorpusManifest, canonical_sha256


MARKER_LABEL = "BenchmarkMarker"
_READ_MARKER = f"MATCH (m:{MARKER_LABEL}) RETURN m.cache_key AS key, m.usage AS usage"
_WRITE_MARKER = (
    f"MERGE (m:{MARKER_LABEL} {{id: 'ingest'}}) "
    "SET m.cache_key = $key, m.usage = $usage"
)
_ENTITY_COUNTS = (
    "MATCH (n) UNWIND labels(n) AS label WITH label, count(*) AS count "
    "WHERE label IN $labels RETURN label, count"
)
_RELATION_COUNTS = (
    "MATCH ()-[r]->() WITH type(r) AS type, count(*) AS count "
    "WHERE type IN $types RETURN type, count"
)


def cache_key(
    *,
    manifest: CorpusManifest,
    corpus_id: str,
    schema_sha256: str,
    extractor_model: str,
    embedder_model: str,
    chunking_fingerprint: str,
    agrag_tree: str,
    benchmarks_code_sha256: str,
    uv_lock_sha256: str,
) -> str:
    """Return the ingest cache key of one corpus.

    Any change to the corpus documents, schema, models, chunking, the ``agrag/``
    tree, the benchmark code or the dependency lock changes the key.
    """
    corpus = next(c for c in manifest.corpora if c.id == corpus_id)
    return canonical_sha256(
        {
            "corpus": corpus.model_dump(mode="json"),
            "schema": schema_sha256,
            "extractor": extractor_model,
            "embedder": embedder_model,
            "chunking": chunking_fingerprint,
            "agrag_tree": agrag_tree,
            "benchmarks_code": benchmarks_code_sha256,
            "uv_lock": uv_lock_sha256,
        }
    )


@dataclass(frozen=True)
class IngestMarker:
    """What a finished ingest left in the graph.

    Attributes:
        key: The cache key the ingest ran under.
        usage: The calls and tokens the ingest spent.
        empty_extractions: The chunks whose extraction returned no entities.
    """

    key: str
    usage: PathUsage
    empty_extractions: int


async def read_marker(store: GraphStore) -> IngestMarker | None:
    """Return the marker stored in the graph, or None when there is none."""
    rows = await store.execute_read(_READ_MARKER)
    if not rows:
        return None
    stored = json.loads(rows[0]["usage"])
    return IngestMarker(
        key=rows[0]["key"],
        usage=PathUsage.model_validate(stored["usage"]),
        empty_extractions=stored["empty_extractions"],
    )


async def write_marker(store: GraphStore, marker: IngestMarker) -> None:
    """Store the ingest marker in the graph."""
    stored = {
        "usage": marker.usage.model_dump(),
        "empty_extractions": marker.empty_extractions,
    }
    await store.execute_write(
        _WRITE_MARKER, {"key": marker.key, "usage": json.dumps(stored)}
    )


async def graph_stats(
    store: GraphStore, *, labels: Collection[str], relation_types: Collection[str]
) -> GraphStats:
    """Count entities by label and relations by type in the ingested graph."""
    entities = await store.execute_read(_ENTITY_COUNTS, {"labels": list(labels)})
    relations = await store.execute_read(
        _RELATION_COUNTS, {"types": list(relation_types)}
    )
    return GraphStats(
        entities_by_label={row["label"]: row["count"] for row in entities},
        relations_by_type={row["type"]: row["count"] for row in relations},
    )
