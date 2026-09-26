"""Resolution quality: B-cubed and pairwise scores of mention clusters.

``run_resolver`` sends mention strings through a ``Resolver`` and returns the
clusters it forms. ``cluster_quality_metric`` compares those clusters with gold
clusters. The score is B-cubed F1. The breakdown also holds B-cubed precision
and recall and pairwise precision, recall and F1. The counting is
``er-evaluation``'s.

Both sides list mentions by index. A mention that is in no cluster is a cluster
of one, so a gold set can list only its multi-mention clusters.
"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import er_evaluation as ee
import pandas as pd
from deepeval.test_case import LLMTestCase
from pydantic import BaseModel, model_validator

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.provenance import TextProvenance
from agrag.eval.adapter import ScoreMetric, ScoreResult, parse_json_case, to_json_case
from agrag.ingestion.resolve.resolver import LLMVerify, Resolver


class ClusterAssignment(BaseModel):
    """A grouping of mentions, listed by position in the mention list.

    Attributes:
        size: The number of mentions.
        clusters: Groups of mention indices. An index in no group is a cluster
            of one.
        matches_by_tier: How many confirmed non-exact matches each comparator
            made. Empty for gold clusters.
    """

    size: int
    clusters: list[list[int]]
    matches_by_tier: dict[str, int] = {}

    @model_validator(mode="after")
    def _check_indices(self) -> "ClusterAssignment":
        """Reject an index that is out of range or in two clusters."""
        seen: set[int] = set()
        for index in (i for cluster in self.clusters for i in cluster):
            if not 0 <= index < self.size:
                raise ValueError(f"index {index} is outside 0..{self.size - 1}")
            if index in seen:
                raise ValueError(f"index {index} is in more than one cluster")
            seen.add(index)
        return self


async def run_resolver(
    resolver: Resolver, mentions: Sequence[str], *, label: str = "Organization"
) -> ClusterAssignment:
    """Resolve mention strings and return the clusters the resolver forms.

    Each mention becomes one entity in its own chunk. The chunk holds only the
    mention text, and is registered with any ``LLMVerify`` comparator of the
    resolver so the comparator can look it up. Chunk ids come from the mention
    position, so runs are repeatable.

    Args:
        resolver: The resolver under test.
        mentions: The mention texts.
        label: The entity label given to every mention.

    Returns:
        The predicted clusters, and the count of matches per comparator.
    """
    chunk_ids = [
        uuid5(NAMESPACE_URL, f"mention:{index}") for index in range(len(mentions))
    ]
    chunks = [
        Chunk(
            id=chunk_id,
            document_id=uuid5(NAMESPACE_URL, "mentions"),
            text=text,
            provenance=TextProvenance(char_start=0, char_end=max(len(text), 1)),
        )
        for chunk_id, text in zip(chunk_ids, mentions, strict=True)
    ]
    for comparator in resolver.comparators:
        if isinstance(comparator, LLMVerify):
            comparator.chunks_by_id.update(zip(chunk_ids, chunks, strict=True))
    entities = [
        ExtractedEntity(
            chunk_id=chunk_id,
            label=label,
            text=chunk.text,
            char_start=0,
            char_end=max(len(chunk.text), 1),
        )
        for chunk_id, chunk in zip(chunk_ids, chunks, strict=True)
    ]
    result = await resolver.resolve(entities)
    matches_by_tier: dict[str, int] = {}
    for match in result.matches:
        matches_by_tier[match.comparator] = matches_by_tier.get(match.comparator, 0) + 1
    return ClusterAssignment(
        size=len(mentions),
        clusters=[group.entity_indices for group in result.groups],
        matches_by_tier=matches_by_tier,
    )


def resolution_case(
    mentions: Sequence[str], predicted: ClusterAssignment, gold: ClusterAssignment
) -> LLMTestCase:
    """Build a test case that holds predicted and gold clusters.

    Args:
        mentions: The mention texts. They show in DeepEval reports.
        predicted: The clusters the resolver formed.
        gold: The gold clusters.

    Returns:
        A test case with serialized predicted and gold clusters.
    """
    return to_json_case("\n".join(mentions), predicted, gold)


def cluster_quality_metric(*, threshold: float = 0.5) -> ScoreMetric:
    """Build a metric for cluster quality on one test case.

    The score is B-cubed F1. The breakdown holds ``b_cubed_precision``,
    ``b_cubed_recall``, ``pairwise_precision``, ``pairwise_recall`` and
    ``pairwise_f``. An over-merge lowers precision and an under-merge lowers
    recall. The score of a whole dataset is the score of one case that holds
    all its mentions, because pooling clusters from separate cases is not
    defined.

    Args:
        threshold: The minimum score that counts as success.

    Returns:
        A metric that scores one case from ``resolution_case``.
    """
    return ScoreMetric("Cluster quality", _score_clusters, threshold)


def _membership(assignment: ClusterAssignment) -> pd.Series:
    """Return the cluster id of each mention, with a new id for each singleton."""
    ids = list(range(assignment.size))
    for cluster_id, cluster in enumerate(assignment.clusters):
        for index in cluster:
            ids[index] = assignment.size + cluster_id
    return pd.Series(ids, index=range(assignment.size))


def _score_clusters(test_case: LLMTestCase) -> ScoreResult:
    """Score predicted clusters against gold with B-cubed and pairwise metrics."""
    predicted, gold = parse_json_case(test_case, ClusterAssignment)
    if predicted.size != gold.size:
        raise ValueError(
            f"predicted has {predicted.size} mentions but gold has {gold.size}"
        )
    prediction, reference = _membership(predicted), _membership(gold)
    breakdown = {
        "b_cubed_precision": ee.b_cubed_precision(prediction, reference),
        "b_cubed_recall": ee.b_cubed_recall(prediction, reference),
        "pairwise_precision": ee.pairwise_precision(prediction, reference),
        "pairwise_recall": ee.pairwise_recall(prediction, reference),
        "pairwise_f": ee.pairwise_f(prediction, reference),
    }
    score = float(ee.b_cubed_f(prediction, reference))
    return ScoreResult(
        score,
        f"B-cubed F1 {score:.2f}, pairwise F1 {breakdown['pairwise_f']:.2f}",
        {name: float(value) for name, value in breakdown.items()},
    )
