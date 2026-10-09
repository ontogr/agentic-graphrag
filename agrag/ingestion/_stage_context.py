"""The dependencies that every stage of one ingestion batch shares."""

from dataclasses import dataclass
from uuid import UUID

from opentelemetry.trace import Tracer

from agrag.embedding.base import Embedder
from agrag.graphdb.base import GraphStore
from agrag.loaders.types import ErrorPolicy
from agrag.vectordb.base import VectorStore


@dataclass(frozen=True)
class StageContext:
    """The shared dependencies of the stages that run one ingestion batch.

    Attributes:
        graph_store: The store the stages read and write.
        embedder: Produces the vectors the stages write.
        vector_store: Optional second write target for the vectors.
        error_policy: How a failed record, write or embed is reported.
        tracer: Opens the spans of the stages. Never None.
        job_id: The in-flight cutover job, or None outside a job.
    """

    graph_store: GraphStore
    embedder: Embedder
    vector_store: VectorStore | None
    error_policy: ErrorPolicy
    tracer: Tracer
    job_id: UUID | None
