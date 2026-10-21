"""Entity resolution: deciding which ExtractedEntity mentions are the same thing."""

import asyncio
import logging
import math
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from time import monotonic
from uuid import UUID, uuid4

from opentelemetry.trace import Tracer
from pydantic import BaseModel, Field

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.text import normalize_text as _normalize
from agrag.embedding.base import Embedder
from agrag.ingestion.extract import ExtractionLLMSettings, ExtractorMissingExtraError
from agrag.ingestion.resolve.candidate_source import CandidateSource
from agrag.ingestion.resolve.zone_classifier import (
    DISCARD_THRESHOLD,
    HARD_MERGE_THRESHOLD,
    MAX_LLM_PAIRS,
    name_pair_gate,
    precluster_ambiguous,
    select_llm_pairs,
)
from agrag.llm.retry import NO_RETRY, call_with_retry
from agrag.observability import get_tracer, record_swallowed_exception


logger = logging.getLogger(__name__)


class ResolutionGroup(BaseModel):
    """One set of ExtractedEntity indices resolution decided are the same entity.

    Attributes:
        entity_indices: Indices into the entity list passed to Resolver.resolve.
            A group of one means resolution found no match for that entity.
    """

    entity_indices: list[int]


class ResolvedMatch(BaseModel):
    """One confirmed non-exact match between two input entity indices.

    Exact-name identity matches group mentions but do not create a match-graph
    edge. Every other confirmed comparator decision creates one record.
    Similarity retains candidate evidence separately from the comparator score.
    A batch id identifies the model request; non-model matches have no batch id.
    """

    left_index: int
    right_index: int
    comparator: str
    score: float | None = None
    reasoning: str | None = None
    decided_at: datetime
    similarity: float | None = None
    batch_id: UUID | None = None


class ResolutionResult(BaseModel):
    """The groups, non-exact evidence, and failure counts of one pass.

    Attributes:
        groups: One group per transitively connected mention set.
        matches: Evidence for every confirmed non-exact pair.
        ambiguous_count: LLM answers that were uncertain, missing, or
            malformed. These pairs never merge.
        failed_llm_requests: LLM verification requests that errored. Their
            pairs are undecided.
        cap_truncated_pairs: Boundary pairs that never reached the LLM
            because of the per-label pair cap. They are undecided.
        llm_unavailable_pairs: Boundary pairs skipped because no LLM
            settings were found or the resolver has no LLM comparator.
        unresolved_pairs: Every pair the resolver could not decide, sorted as
            ``(left_index, right_index)`` with the lower index first.
    """

    groups: list[ResolutionGroup]
    matches: list[ResolvedMatch]
    ambiguous_count: int = 0
    failed_llm_requests: int = 0
    cap_truncated_pairs: int = 0
    llm_unavailable_pairs: int = 0
    unresolved_pairs: list[tuple[int, int]] = Field(default_factory=list)


class ComparisonVerdict(StrEnum):
    """A Comparator's verdict on one entity pair.

    Attributes:
        MATCH: The comparator is confident these are the same entity.
        NO_MATCH: The comparator is confident these are different entities.
        UNCERTAIN: No decision. The comparator cannot decide, or the LLM tier
            failed, was capped, or had no settings. The next comparator gets a
            turn, and a caller must not treat it as a rejection.
    """

    MATCH = "match"
    NO_MATCH = "no_match"
    UNCERTAIN = "uncertain"


class ComparisonResult(BaseModel):
    """The verdict and evidence produced by one comparator."""

    verdict: ComparisonVerdict
    score: float | None = None
    reasoning: str | None = None


class Comparator(ABC):
    """One matching strategy a Resolver runs against a candidate pair."""

    @abstractmethod
    async def compare(
        self, a: ExtractedEntity, b: ExtractedEntity
    ) -> ComparisonVerdict:
        """Compare two entities.

        Args:
            a: The first entity.
            b: The second entity.

        Returns:
            This comparator's verdict. UNCERTAIN defers to the next comparator.
        """

    async def compare_with_evidence(
        self, a: ExtractedEntity, b: ExtractedEntity
    ) -> ComparisonResult:
        """Compare two entities and retain any available decision evidence."""
        return ComparisonResult(verdict=await self.compare(a, b))


class ExactMatch(Comparator):
    """Matches when normalized text is identical. Never returns NO_MATCH."""

    async def compare(
        self, a: ExtractedEntity, b: ExtractedEntity
    ) -> ComparisonVerdict:
        """Return MATCH on identical normalized text, else UNCERTAIN."""
        if _normalize(a.text) == _normalize(b.text):
            return ComparisonVerdict.MATCH
        return ComparisonVerdict.UNCERTAIN


class FuzzyMatch(Comparator):
    """Fast-path accepter for near-identical names. Never returns NO_MATCH.

    Rejection belongs to later tiers, which see embedding and LLM evidence
    this comparator lacks.

    Attributes:
        match_above: A similarity score at or above this is a match.
    """

    def __init__(self, *, match_above: float = 0.97) -> None:
        """Create a comparator with the configured fast-path threshold."""
        self.match_above = match_above

    async def compare(
        self, a: ExtractedEntity, b: ExtractedEntity
    ) -> ComparisonVerdict:
        """Return a verdict from token-sort-ratio similarity."""
        return (await self.compare_with_evidence(a, b)).verdict

    async def compare_with_evidence(
        self, a: ExtractedEntity, b: ExtractedEntity
    ) -> ComparisonResult:
        """Compare two entities and include their token-sort similarity."""
        from rapidfuzz import fuzz  # noqa: PLC0415

        score = fuzz.token_sort_ratio(_normalize(a.text), _normalize(b.text)) / 100
        if score >= self.match_above:
            verdict = ComparisonVerdict.MATCH
        else:
            verdict = ComparisonVerdict.UNCERTAIN
        return ComparisonResult(verdict=verdict, score=score)


class LLMVerify(Comparator):
    """Ask an LLM to verify an ambiguous pair. Last resort.

    Returns ``UNCERTAIN``, never ``NO_MATCH``, for a pair it could not judge: a
    failed request, missing LLM settings, or a missing or malformed answer. A
    pair it did not judge never merges, and a caller must not treat it as
    rejected. A missing package extra is a configuration error, not a judgment
    call, and is raised outright (see compare's Raises section).

    Attributes:
        failed_requests: Requests that raised.
        unavailable_pairs: Pairs skipped because no LLM settings were found.
        unavailable_reason: Why the settings were missing, or None.
    """

    def __init__(
        self,
        *,
        chunks_by_id: dict[UUID, Chunk],
        settings: ExtractionLLMSettings | None = None,
        client: object | None = None,
        max_pairs_per_batch: int = 50,
        tracer: Tracer | None = None,
    ) -> None:
        """Create a comparator with chunk lookup for context and an LLM client.

        Args:
            chunks_by_id: Maps a Chunk id to the Chunk, for prompt context.
            settings: LLM client config. Defaults to ``ExtractionLLMSettings()``.
                Ignored when ``client`` is given: an injected client also
                disables ``settings.retry``, since a caller building its own
                client is assumed to own its own retry behavior too.
            client: An already-built BAML client. Tests inject a fake here.
            max_pairs_per_batch: Maximum pairs sent to the LLM in one request.
                A large ambiguous population is split into requests of at most
                this size so one oversized request cannot exceed the model's
                context limit and silently fail every pair in the batch.
            tracer: Opens the ``agrag.resolution.llm_verify`` span and the
                LLM call spans below it.
        """
        if max_pairs_per_batch <= 0:
            raise ValueError("max_pairs_per_batch must be positive")
        self.chunks_by_id = chunks_by_id
        self.settings = settings
        self._client = client
        self.max_pairs_per_batch = max_pairs_per_batch
        self.failed_requests: int = 0
        self.unavailable_pairs: int = 0
        self.unavailable_reason: str | None = None
        self._resolved_settings: ExtractionLLMSettings | None = settings
        self._tracer = tracer

    async def compare(
        self, a: ExtractedEntity, b: ExtractedEntity
    ) -> ComparisonVerdict:
        """Return the LLM's verdict for one pair, or UNCERTAIN when it gave none.

        Runs through compare_batch so the single-pair path shares the
        batch validation and fail-safe behavior.

        Raises:
            ExtractorMissingExtraError: The ``llm`` package extra is not
                installed.
        """
        results, _ = await self.compare_batch_detailed([(0, 0, a, b)])
        return results[(0, 0)].verdict

    async def compare_batch(
        self,
        pairs: list[tuple[int, int, ExtractedEntity, ExtractedEntity]],
        *,
        similarities: dict[tuple[int, int], float] | None = None,
        neighbors_by_index: dict[int, list[str]] | None = None,
    ) -> dict[tuple[int, int], ComparisonResult]:
        """Verify ambiguous candidate pairs across bounded LLM requests.

        Splits into requests of at most ``max_pairs_per_batch`` pairs so one
        oversized population cannot exceed the model's context limit.
        Invalid, missing, and uncertain model responses do not merge entities.

        Args:
            pairs: ``(left_index, right_index, left, right)`` tuples to verify.
            similarities: Embedding similarity per pair, sent to the model
                as decision context. Defaults to 0.0 when unknown.
            neighbors_by_index: Entity index to its neighboring-relationship
                context strings. Looked up globally, so every chunk sees the
                same map.
        """
        results, _ = await self.compare_batch_detailed(
            pairs, similarities=similarities, neighbors_by_index=neighbors_by_index
        )
        return results

    async def compare_batch_detailed(
        self,
        pairs: list[tuple[int, int, ExtractedEntity, ExtractedEntity]],
        *,
        similarities: dict[tuple[int, int], float] | None = None,
        neighbors_by_index: dict[int, list[str]] | None = None,
    ) -> tuple[dict[tuple[int, int], ComparisonResult], int]:
        """Verify pairs and count how many verdicts came back uncertain.

        Args:
            pairs: The candidate pairs to verify.
            similarities: Embedding similarity per pair, sent to the model
                as decision context. Defaults to 0.0 when unknown.
            neighbors_by_index: Entity index to its neighboring-relationship
                context strings. Looked up globally, so every chunk sees the
                same map.

        Returns:
            The per-pair results and the count of uncertain verdicts, including
                missing and malformed answers. A request that errors or has no
                settings returns UNCERTAIN for its pairs and increments
                ``failed_requests`` or ``unavailable_pairs`` instead.
        """
        if not pairs:
            return {}, 0
        results: dict[tuple[int, int], ComparisonResult] = {}
        uncertain = 0
        for start in range(0, len(pairs), self.max_pairs_per_batch):
            chunk = pairs[start : start + self.max_pairs_per_batch]
            chunk_results, chunk_uncertain = await self._compare_batch_chunk(
                chunk, similarities=similarities, neighbors_by_index=neighbors_by_index
            )
            results.update(chunk_results)
            uncertain += chunk_uncertain
        return results, uncertain

    async def _compare_batch_chunk(
        self,
        pairs: list[tuple[int, int, ExtractedEntity, ExtractedEntity]],
        *,
        similarities: dict[tuple[int, int], float] | None = None,
        neighbors_by_index: dict[int, list[str]] | None = None,
    ) -> tuple[dict[tuple[int, int], ComparisonResult], int]:
        """Verify one bounded chunk of ambiguous candidate pairs in one LLM request."""
        with get_tracer(self._tracer).start_as_current_span(
            "agrag.resolution.llm_verify",
            attributes={"agrag.pair_count": len(pairs)},
        ) as span:
            try:
                if self._client is not None:
                    client = self._client
                    baml_options: dict = {}
                    retry = NO_RETRY
                else:
                    from agrag.llm import client_registry  # noqa: PLC0415

                    client = self._default_client()
                    settings = self._load_settings()
                    if settings is None:
                        span.set_attribute("agrag.llm_unavailable", True)
                        self.unavailable_pairs += len(pairs)
                        return _undecided(pairs), 0
                    registry = client_registry.build_client_registry(
                        settings.clients, strategy=settings.strategy
                    )
                    baml_options = {"client_registry": registry}
                    retry = settings.retry
                pair_ids = [f"{left}:{right}" for left, right, _, _ in pairs]
                known = similarities or {}
                inputs = [
                    {
                        "pair_id": pair_id,
                        "entity_a": first.text,
                        "context_a": self._context_for(first),
                        "neighbors_a": (neighbors_by_index or {}).get(left, []),
                        "entity_b": second.text,
                        "context_b": self._context_for(second),
                        "neighbors_b": (neighbors_by_index or {}).get(right, []),
                        "similarity": known.get((left, right), 0.0),
                    }
                    for pair_id, (left, right, first, second) in zip(
                        pair_ids, pairs, strict=True
                    )
                ]
                results = await call_with_retry(
                    lambda options: client.VerifyEntityMatches(  # ty: ignore[unresolved-attribute]
                        inputs, options
                    ),
                    retry,
                    options=baml_options,
                    tracer=self._tracer,
                    function="VerifyEntityMatches",
                )
            except ExtractorMissingExtraError:
                raise
            except Exception as exc:  # noqa: BLE001
                record_swallowed_exception(exc)
                span.set_attribute("agrag.request_failed", True)
                self.failed_requests += 1
                return _undecided(pairs), 0
            from agrag.ingestion.resolve.batch_validation import (  # noqa: PLC0415
                validate_batch_verdicts,
            )

            verdicts = validate_batch_verdicts(pair_ids, results)
            uncertain = sum(
                verdict.verdict is ComparisonVerdict.UNCERTAIN
                for verdict in verdicts.values()
            )
            final = {
                (left, right): verdicts[pair_id]
                for pair_id, (left, right, _, _) in zip(pair_ids, pairs, strict=True)
            }
            span.set_attribute(
                "agrag.match_count",
                sum(
                    result.verdict is ComparisonVerdict.MATCH
                    for result in final.values()
                ),
            )
            span.set_attribute("agrag.uncertain_count", uncertain)
            span.set_attribute("agrag.request_failed", False)
            return final, uncertain

    def _default_client(self) -> object:
        """Return the default generated BAML client."""
        try:
            from agrag.llm.baml_client import b  # noqa: PLC0415
        except ImportError as exc:
            raise ExtractorMissingExtraError("LLMVerify", "llm") from exc
        return b

    def _load_settings(self) -> ExtractionLLMSettings | None:
        """Return LLM settings, trying the two environment sources once."""
        if self._resolved_settings is not None:
            return self._resolved_settings
        if self.unavailable_reason is not None:
            return None
        try:
            self._resolved_settings = ExtractionLLMSettings()
        except Exception:  # noqa: BLE001
            try:
                self._resolved_settings = (
                    ExtractionLLMSettings.from_openai_compatible_env()
                )
            except Exception as exc:  # noqa: BLE001
                self.unavailable_reason = (
                    "set EXTRACTION_LLM_CLIENTS, or LLM_BASE_URL and "
                    f"LLM_MODEL_ID ({type(exc).__name__})"
                )
        return self._resolved_settings

    def _context_for(self, entity: ExtractedEntity) -> str:
        """Return the mention's source chunk text as comparison context."""
        return self.chunks_by_id[entity.chunk_id].text


def _group_matches(entity_count: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    """Return groups of transitively connected indices from confirmed-match edges.

    Union-find with path compression. Every index from 0 to entity_count - 1
    appears in exactly one returned group, including entities with no edges,
    which each form their own group of one.

    Args:
        entity_count: The total number of entities, including ones with no
            confirmed matches.
        edges: Pairs of indices a MATCH verdict connected.

    Returns:
        The groups, each a list of entity indices. Group order is arbitrary.
    """
    parent = list(range(entity_count))

    def find(index: int) -> int:
        """Return index's group representative, compressing the path to it."""
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for left, right in edges:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[left_root] = right_root

    groups: dict[int, list[int]] = {}
    for index in range(entity_count):
        groups.setdefault(find(index), []).append(index)
    return list(groups.values())


def _undecided(
    pairs: list[tuple[int, int, ExtractedEntity, ExtractedEntity]],
) -> dict[tuple[int, int], ComparisonResult]:
    """Return an UNCERTAIN result for every pair of a request that gave no answer."""
    return {
        (left, right): ComparisonResult(verdict=ComparisonVerdict.UNCERTAIN)
        for left, right, _, _ in pairs
    }


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return the cosine similarity of two vectors, or 0.0 on zero norm."""
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _match_record(
    left: int,
    right: int,
    *,
    comparator: str,
    score: float | None = None,
    reasoning: str | None = None,
    similarity: float | None = None,
    batch_id: UUID | None = None,
) -> ResolvedMatch:
    """Build a ResolvedMatch stamped with the current time."""
    return ResolvedMatch(
        left_index=left,
        right_index=right,
        comparator=comparator,
        score=score,
        reasoning=reasoning,
        decided_at=datetime.now(UTC),
        similarity=similarity,
        batch_id=batch_id,
    )


def _constrain_matches(
    entity_count: int,
    edges: list[tuple[int, int]],
    matches: list[ResolvedMatch],
    cannot_link: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    """Reject weaker edges that would connect a forbidden pair transitively.

    Comparator score ranks edges first, with candidate similarity when no score
    is available. Index pairs break ties. Exact identity edges rank first.
    """
    if not cannot_link:
        return set()
    parent = list(range(entity_count))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    confidence = {
        (match.left_index, match.right_index): (
            match.score if match.score is not None else match.similarity or 0.0
        )
        for match in matches
    }
    rejected: set[tuple[int, int]] = set()
    for left, right in sorted(
        edges, key=lambda pair: (-confidence.get(pair, 1.0), pair)
    ):
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            continue
        if any(
            {find(first), find(second)} == {left_root, right_root}
            for first, second in cannot_link
        ):
            rejected.add((left, right))
        else:
            parent[left_root] = right_root
    return rejected


@dataclass(frozen=True)
class _LlmTier:
    """What the LLM tier left behind for one resolve call."""

    ambiguous_count: int = 0
    failed_requests: int = 0
    cap_truncated_pairs: int = 0
    unavailable_pairs: int = 0
    unavailable_reason: str | None = None
    unresolved_pairs: tuple[tuple[int, int], ...] = ()
    cannot_link: frozenset[tuple[int, int]] = frozenset()
    pairs_sent_to_model: int = 0


class Resolver:
    """Routes blocked candidate pairs through exact, fuzzy, embedding, and LLM zones.

    Exact identity groups mentions without evidence. A near-identical
    fuzzy score merges on the fast path. Every other pair consults its
    embedding cosine similarity: at or above the hard-merge threshold it
    merges, below the discard threshold it drops, and inside the band it
    needs LLM review, capped per label, most similar first. Tight sub-clusters
    merge without spending LLM calls.
    """

    def __init__(
        self,
        *,
        comparators: list[Comparator],
        candidate_source: CandidateSource,
        embedder: Embedder | None = None,
        hard_merge_threshold: float = HARD_MERGE_THRESHOLD,
        discard_threshold: float = DISCARD_THRESHOLD,
        max_llm_pairs: int = MAX_LLM_PAIRS,
        llm_batch_size: int = 10,
        llm_concurrency: int = 2,
        on_progress: Callable[[int, int, float], None] | None = None,
        tracer: Tracer | None = None,
    ) -> None:
        """Create a zone-routed resolver from comparators and a candidate source.

        Args:
            comparators: The ExactMatch, FuzzyMatch, and LLMVerify tiers,
                each picked out by type. A missing ExactMatch or FuzzyMatch
                falls back to its defaults; without an LLMVerify the LLM
                tier is skipped and boundary pairs never merge.
            candidate_source: Narrows which pairs get compared at all.
            embedder: Embeds mention texts for the similarity tier. None
                skips that tier: every fuzzy-uncertain pair counts as
                ambiguous, ranked by its fuzzy score.
            hard_merge_threshold: Embedding similarity at or above which
                a pair merges without LLM review.
            discard_threshold: Embedding similarity below which a pair
                drops without LLM review.
            max_llm_pairs: Maximum ambiguous pairs sent to the LLM per label,
                most similar first. The rest are undecided.
            llm_batch_size: Pairs per LLM request. Must fit the
                LLMVerify comparator's max_pairs_per_batch.
            llm_concurrency: Maximum simultaneous verification requests, at least 1.
            on_progress: Receives completed batches, total batches and elapsed seconds.
            tracer: Opens this resolver's spans.

        Raises:
            ValueError: llm_concurrency or llm_batch_size is not positive,
                or llm_batch_size exceeds the comparator's max_pairs_per_batch.
        """
        if llm_batch_size <= 0:
            raise ValueError("llm_batch_size must be positive")
        if llm_concurrency < 1:
            raise ValueError("llm_concurrency must be positive")
        self.comparators = comparators
        self.candidate_source = candidate_source
        self.embedder = embedder
        self.hard_merge_threshold = hard_merge_threshold
        self.discard_threshold = discard_threshold
        self.max_llm_pairs = max_llm_pairs
        self.llm_batch_size = llm_batch_size
        self.llm_concurrency = llm_concurrency
        self.on_progress = on_progress
        self._tracer = get_tracer(tracer)
        self._exact = next(
            (c for c in comparators if isinstance(c, ExactMatch)), ExactMatch()
        )
        self._fuzzy = next(
            (c for c in comparators if isinstance(c, FuzzyMatch)), FuzzyMatch()
        )
        self._llm = next((c for c in comparators if isinstance(c, LLMVerify)), None)
        if self._llm is not None and self._llm.max_pairs_per_batch < llm_batch_size:
            raise ValueError(
                "llm_batch_size must fit the LLMVerify max_pairs_per_batch"
            )

    async def resolve(
        self,
        entities: list[ExtractedEntity],
        *,
        neighbors_by_index: dict[int, list[str]] | None = None,
        similarity_by_pair: dict[tuple[int, int], float] | None = None,
        chunk_ids_by_index: dict[int, set[UUID]] | None = None,
        already_decided_pairs: set[tuple[int, int]] | None = None,
    ) -> ResolutionResult:
        """Resolve entity groups and retain each confirmed non-exact match.

        Args:
            entities: The entities to resolve. Only entities passed in the
                same call are ever compared against each other — resolving
                against previously-resolved entities from an earlier call is
                not supported by this Resolver.
            neighbors_by_index: Entity index to that entity's neighboring-
                relationship context for LLM verification, when the caller has
                such a source. Omitted by callers that do not.
            similarity_by_pair: Already-known real similarity scores keyed by
                ``(min(left, right), max(left, right))``, such as an ANN
                backend's hit score. Never drives zone routing -- that scale
                is not comparable to this Resolver's own cosine similarity --
                but reaches the LLM as decision context, preferred over a
                freshly embedded score, for a pair that lands on the boundary
                anyway. Not mutated.
            chunk_ids_by_index: Actual source chunks per mention or persisted entity.
                Omitted entries mean unknown; None uses mention chunk ids.
            already_decided_pairs: Previously joined pairs to count, not skip.

        Returns:
            Groups and evidence, plus counts of uncertain verdicts, failed
            requests, cap-truncated pairs, unavailable pairs, and all
            unresolved pairs.
        """
        with self._tracer.start_as_current_span(
            "agrag.resolution.resolve", attributes={"agrag.entity_count": len(entities)}
        ) as span:
            pairs: list[tuple[int, int]] = []
            compared: set[tuple[int, int]] = set()
            for index in range(len(entities)):
                candidates = await self.candidate_source.candidates_for(index, entities)
                for candidate_index in candidates:
                    pair = (min(index, candidate_index), max(index, candidate_index))
                    if pair in compared:
                        continue
                    compared.add(pair)
                    pairs.append(pair)
            gated: set[tuple[int, int]] = set()
            counts = {"long_name": 0, "digit_mismatch": 0}
            for left, right in pairs:
                first, second = entities[left].text, entities[right].text
                if _normalize(first) == _normalize(second):
                    continue
                reason = name_pair_gate(first, second)
                if reason is not None:
                    counts[reason] += 1
                    gated.add((left, right))
            chunks = (
                chunk_ids_by_index
                if chunk_ids_by_index is not None
                else {index: {entity.chunk_id} for index, entity in enumerate(entities)}
            )
            span.set_attribute(
                "agrag.same_chunk_pairs",
                sum(
                    bool(chunks.get(left, set()) & chunks.get(right, set()))
                    for left, right in pairs
                ),
            )
            span.set_attribute(
                "agrag.already_decided_pairs",
                len(compared & (already_decided_pairs or set())),
            )
            edges, matches, tier = await self._resolve_pairs(
                [pair for pair in pairs if pair not in gated],
                entities,
                neighbors_by_index or {},
                similarity_by_pair or {},
            )
            rejected = _constrain_matches(
                len(entities), edges, matches, set(tier.cannot_link) | gated
            )
            edges = [edge for edge in edges if edge not in rejected]
            matches = [
                match
                for match in matches
                if (match.left_index, match.right_index) not in rejected
            ]
            span.set_attribute("agrag.pair_count", len(pairs))
            span.set_attribute("agrag.long_name_pairs", counts["long_name"])
            span.set_attribute("agrag.digit_mismatch_pairs", counts["digit_mismatch"])
            span.set_attribute("agrag.pairs_sent_to_model", tier.pairs_sent_to_model)
            span.set_attribute("agrag.ambiguous_count", tier.ambiguous_count)
            span.set_attribute("agrag.failed_llm_requests", tier.failed_requests)
            span.set_attribute("agrag.cap_truncated_pairs", tier.cap_truncated_pairs)
            span.set_attribute("agrag.llm_unavailable_pairs", tier.unavailable_pairs)
            groups = _group_matches(len(entities), edges)
            result = ResolutionResult(
                groups=[ResolutionGroup(entity_indices=group) for group in groups],
                matches=matches,
                ambiguous_count=tier.ambiguous_count,
                failed_llm_requests=tier.failed_requests,
                cap_truncated_pairs=tier.cap_truncated_pairs,
                llm_unavailable_pairs=tier.unavailable_pairs,
                unresolved_pairs=sorted(set(tier.unresolved_pairs) | gated | rejected),
            )
            if result.unresolved_pairs:
                reason = (
                    f" LLM tier unavailable: {tier.unavailable_reason}."
                    if tier.unavailable_pairs
                    else ""
                )
                logger.warning(
                    "Resolution left %d pairs undecided: %d failed LLM requests, "
                    "%d pairs over the cap of %d per label, %d pairs without an "
                    "LLM.%s Existing matches stay in place.",
                    len(result.unresolved_pairs),
                    result.failed_llm_requests,
                    result.cap_truncated_pairs,
                    self.max_llm_pairs,
                    result.llm_unavailable_pairs,
                    reason,
                )
            return result

    async def _resolve_pairs(
        self,
        pairs: list[tuple[int, int]],
        entities: list[ExtractedEntity],
        neighbors_by_index: dict[int, list[str]],
        similarity_by_pair: dict[tuple[int, int], float],
    ) -> tuple[list[tuple[int, int]], list[ResolvedMatch], _LlmTier]:
        """Route candidate pairs through the exact, fuzzy, embedding, and LLM zones.

        LLM calls stay bounded: ambiguous pairs are capped per label at
        ``max_llm_pairs`` and pooled across labels into requests of
        ``llm_batch_size``, so one call makes at most
        ``ceil(L * max_llm_pairs / llm_batch_size)`` LLM requests for
        ``L`` labels. ``similarity_by_pair`` never drives zone routing --
        an ANN backend's score is not on the same scale as this tier's own
        cosine similarity, so it only reaches the LLM as decision context
        for a pair that lands on the boundary anyway.
        """
        edges: list[tuple[int, int]] = []
        matches: list[ResolvedMatch] = []
        fuzzy_uncertain: list[tuple[int, int, float]] = []
        with self._tracer.start_as_current_span(
            "agrag.resolution.exact_fuzzy_pass",
            attributes={"agrag.pair_count": len(pairs)},
        ) as span:
            for left, right in pairs:
                if (
                    await self._exact.compare(entities[left], entities[right])
                    is ComparisonVerdict.MATCH
                ):
                    edges.append((left, right))
                    continue
                evidence = await self._fuzzy.compare_with_evidence(
                    entities[left], entities[right]
                )
                if evidence.verdict is ComparisonVerdict.MATCH:
                    edges.append((left, right))
                    matches.append(
                        _match_record(
                            left,
                            right,
                            comparator="fuzzy_fast_path",
                            score=evidence.score,
                            reasoning=evidence.reasoning,
                        )
                    )
                    continue
                fuzzy_uncertain.append((left, right, evidence.score or 0.0))
            span.set_attribute("agrag.exact_match_count", len(edges))
            span.set_attribute("agrag.fuzzy_fast_path_count", len(matches))
            span.set_attribute("agrag.fuzzy_uncertain_count", len(fuzzy_uncertain))

        ambiguous, scored = await self._embedding_tier(
            fuzzy_uncertain, entities, edges, matches
        )
        boundary = self._precluster_tier(ambiguous, scored, edges, matches)
        tier = await self._llm_tier(
            boundary,
            entities,
            edges,
            matches,
            neighbors_by_index=neighbors_by_index,
            similarity_by_pair=similarity_by_pair,
        )
        return edges, matches, tier

    async def _embedding_tier(
        self,
        fuzzy_uncertain: list[tuple[int, int, float]],
        entities: list[ExtractedEntity],
        edges: list[tuple[int, int]],
        matches: list[ResolvedMatch],
    ) -> tuple[
        dict[str, list[tuple[int, int, float]]],
        dict[str, dict[tuple[int, int], float]],
    ]:
        """Sort fuzzy-uncertain pairs into merge, drop, or ambiguous by zone.

        Embeds each unique mention text once. Without an embedder every
        pair counts as ambiguous, ranked by its fuzzy score.

        Returns:
            Ambiguous ``(left, right, similarity)`` triples grouped by
            label, and every scored pair's similarity by label for the
            precluster tier.
        """
        ambiguous: dict[str, list[tuple[int, int, float]]] = {}
        scored: dict[str, dict[tuple[int, int], float]] = {}
        with self._tracer.start_as_current_span(
            "agrag.resolution.embedding_tier",
            attributes={"agrag.fuzzy_uncertain_count": len(fuzzy_uncertain)},
        ) as span:
            if not fuzzy_uncertain:
                return ambiguous, scored
            if self.embedder is None:
                for left, right, fuzzy_score in fuzzy_uncertain:
                    ambiguous.setdefault(entities[left].label, []).append(
                        (left, right, fuzzy_score)
                    )
                span.set_attribute(
                    "agrag.ambiguous_count",
                    sum(len(v) for v in ambiguous.values()),
                )
                return ambiguous, scored
            texts = list(
                dict.fromkeys(
                    entities[index].text
                    for pair in fuzzy_uncertain
                    for index in (pair[0], pair[1])
                )
            )
            vectors = dict(zip(texts, await self.embedder.embed(texts), strict=True))
            hard_merges = 0
            for left, right, _ in fuzzy_uncertain:
                similarity = _cosine_similarity(
                    vectors[entities[left].text], vectors[entities[right].text]
                )
                label = entities[left].label
                scored.setdefault(label, {})[(min(left, right), max(left, right))] = (
                    similarity
                )
                if similarity >= self.hard_merge_threshold:
                    edges.append((left, right))
                    matches.append(
                        _match_record(
                            left,
                            right,
                            comparator="embedding",
                            score=similarity,
                            similarity=similarity,
                        )
                    )
                    hard_merges += 1
                elif similarity >= self.discard_threshold:
                    ambiguous.setdefault(label, []).append((left, right, similarity))
            span.set_attribute("agrag.hard_merge_count", hard_merges)
            span.set_attribute(
                "agrag.ambiguous_count", sum(len(v) for v in ambiguous.values())
            )
            return ambiguous, scored

    def _precluster_tier(
        self,
        ambiguous: dict[str, list[tuple[int, int, float]]],
        scored: dict[str, dict[tuple[int, int], float]],
        edges: list[tuple[int, int]],
        matches: list[ResolvedMatch],
    ) -> list[tuple[int, int, float]]:
        """Auto-merge ambiguous pairs inside tight scored sub-clusters.

        Clusters over every scored pair so an ambiguous pair riding with
        hard-merge neighbors skips LLM review. Pairs the embedding tier
        already confirmed keep their edge; discarded pairs stay dropped.

        Without an embedder there are no embedding similarities to
        cluster on, so every ambiguous pair stays on the boundary.

        Returns:
            The boundary pairs still needing LLM review.
        """
        if self.embedder is None:
            return [pair for pairs in ambiguous.values() for pair in pairs]
        boundary: list[tuple[int, int, float]] = []
        with self._tracer.start_as_current_span(
            "agrag.resolution.precluster_tier",
            attributes={
                "agrag.boundary_pairs_before": sum(len(v) for v in ambiguous.values())
            },
        ) as span:
            auto_merged_total = 0
            for label, similarities_by_pair in scored.items():
                position_of: dict[int, int] = {}
                members: list[int] = []
                for left, right in similarities_by_pair:
                    for index in (left, right):
                        if index not in position_of:
                            position_of[index] = len(members)
                            members.append(index)
                similarities = {
                    (position_of[left], position_of[right]): similarity
                    for (left, right), similarity in similarities_by_pair.items()
                }
                ids = [uuid4() for _ in members]
                member_of = dict(zip(ids, members, strict=True))
                ambiguous_keys = {
                    (min(left, right), max(left, right))
                    for left, right, _ in ambiguous.get(label, [])
                }
                auto_merged: set[tuple[int, int]] = set()
                for cluster in precluster_ambiguous(
                    ids,
                    similarities,
                    hard_merge_threshold=self.hard_merge_threshold,
                ):
                    ordered = sorted(member_of[member_id] for member_id in cluster)
                    for first in range(len(ordered)):
                        for second in range(first + 1, len(ordered)):
                            left, right = ordered[first], ordered[second]
                            pair = (min(left, right), max(left, right))
                            if pair in auto_merged or pair not in ambiguous_keys:
                                continue
                            auto_merged.add(pair)
                            edges.append(pair)
                            matches.append(
                                _match_record(
                                    pair[0],
                                    pair[1],
                                    comparator="embedding",
                                    score=similarities_by_pair[pair],
                                    similarity=similarities_by_pair[pair],
                                )
                            )
                auto_merged_total += len(auto_merged)
                for left, right, similarity in ambiguous.get(label, []):
                    if (min(left, right), max(left, right)) not in auto_merged:
                        boundary.append((left, right, similarity))
            span.set_attribute("agrag.auto_merged_count", auto_merged_total)
            span.set_attribute("agrag.boundary_pairs_after", len(boundary))
            return boundary

    async def _llm_tier(  # noqa: PLR0915
        self,
        boundary: list[tuple[int, int, float]],
        entities: list[ExtractedEntity],
        edges: list[tuple[int, int]],
        matches: list[ResolvedMatch],
        *,
        neighbors_by_index: dict[int, list[str]],
        similarity_by_pair: dict[tuple[int, int], float],
    ) -> _LlmTier:
        """Verify capped boundary pairs with the LLM and merge its matches.

        Every boundary pair the tier cannot decide is returned in
        ``unresolved_pairs``: pairs over the cap, from failed requests, skipped
        for missing settings, or left uncertain by the model.
        """
        if not boundary:
            return _LlmTier()
        if self._llm is None:
            return _LlmTier(
                unavailable_pairs=len(boundary),
                unavailable_reason="the resolver has no LLMVerify comparator",
                unresolved_pairs=tuple((left, right) for left, right, _ in boundary),
            )
        with self._tracer.start_as_current_span(
            "agrag.resolution.llm_tier",
            attributes={"agrag.boundary_pair_count": len(boundary)},
        ) as span:
            by_label: dict[str, list[tuple[int, int, float]]] = {}
            for left, right, similarity in boundary:
                by_label.setdefault(entities[left].label, []).append(
                    (left, right, similarity)
                )
            selected: list[tuple[int, int]] = []
            unresolved: list[tuple[int, int]] = []
            for candidates in by_label.values():
                chosen = select_llm_pairs(candidates, max_pairs=self.max_llm_pairs)
                chosen_set = set(chosen)
                unresolved.extend(
                    (left, right)
                    for left, right, _ in candidates
                    if (left, right) not in chosen_set
                )
                selected.extend(chosen)
            cap_truncated_pairs = len(unresolved)
            span.set_attribute("agrag.selected_pair_count", len(selected))
            span.set_attribute("agrag.cap_truncated_pairs", cap_truncated_pairs)
            failed_before = self._llm.failed_requests
            unavailable_before = self._llm.unavailable_pairs
            ambiguous_count = 0
            cannot_link: set[tuple[int, int]] = set()
            batches = [
                selected[start : start + self.llm_batch_size]
                for start in range(0, len(selected), self.llm_batch_size)
            ]
            semaphore = asyncio.Semaphore(self.llm_concurrency)
            started = monotonic()
            done = 0
            verifier = self._llm
            similarities = {
                (left, right): similarity_by_pair.get((left, right), score)
                for left, right, score in boundary
            }
            if self.on_progress is not None:
                self.on_progress(0, len(batches), 0.0)

            async def verify(
                selected_chunk: list[tuple[int, int]],
            ) -> tuple[dict[tuple[int, int], ComparisonResult], int, UUID]:
                nonlocal done
                async with semaphore:
                    batch_id = uuid4()
                    with self._tracer.start_as_current_span(
                        "agrag.resolution.llm_batch",
                        attributes={
                            "agrag.batch_size": len(selected_chunk),
                            "agrag.batch_id": str(batch_id),
                        },
                    ) as batch_span:
                        results, uncertain = await verifier.compare_batch_detailed(
                            [
                                (left, right, entities[left], entities[right])
                                for left, right in selected_chunk
                            ],
                            similarities={
                                pair: similarities[pair] for pair in selected_chunk
                            },
                            neighbors_by_index=neighbors_by_index,
                        )
                        batch_span.set_attribute("agrag.uncertain_count", uncertain)
                        done += 1
                        if self.on_progress is not None:
                            self.on_progress(done, len(batches), monotonic() - started)
                        return results, uncertain, batch_id

            tasks = [asyncio.create_task(verify(batch)) for batch in batches]
            try:
                outcomes = await asyncio.gather(*tasks)
            except BaseException:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                raise
            for results, chunk_uncertain, batch_id in outcomes:
                ambiguous_count += chunk_uncertain
                for (left, right), comparison in results.items():
                    if comparison.verdict is ComparisonVerdict.MATCH:
                        edges.append((left, right))
                        matches.append(
                            _match_record(
                                left,
                                right,
                                comparator="llm",
                                score=comparison.score,
                                reasoning=comparison.reasoning,
                                similarity=similarities[(left, right)],
                                batch_id=batch_id,
                            )
                        )
                    elif comparison.verdict is ComparisonVerdict.NO_MATCH:
                        cannot_link.add((left, right))
                    elif comparison.verdict is ComparisonVerdict.UNCERTAIN:
                        unresolved.append((left, right))
            failed_llm_requests = self._llm.failed_requests - failed_before
            unavailable_pairs = self._llm.unavailable_pairs - unavailable_before
            span.set_attribute("agrag.ambiguous_count", ambiguous_count)
            span.set_attribute("agrag.failed_llm_requests", failed_llm_requests)
            span.set_attribute("agrag.llm_unavailable_pairs", unavailable_pairs)
        return _LlmTier(
            ambiguous_count=ambiguous_count,
            failed_requests=failed_llm_requests,
            cap_truncated_pairs=cap_truncated_pairs,
            unavailable_pairs=unavailable_pairs,
            unavailable_reason=self._llm.unavailable_reason,
            unresolved_pairs=tuple(unresolved),
            cannot_link=frozenset(cannot_link),
            pairs_sent_to_model=len(selected),
        )
