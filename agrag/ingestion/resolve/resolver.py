"""Entity resolution: deciding which ExtractedEntity mentions are the same thing."""

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel

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
    precluster_ambiguous,
    select_llm_pairs,
)
from agrag.llm.retry import NO_RETRY, call_with_retry


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
    """

    left_index: int
    right_index: int
    comparator: str
    score: float | None = None
    reasoning: str | None = None
    decided_at: datetime


class ResolutionResult(BaseModel):
    """The groups, non-exact evidence, and ambiguity count of one pass.

    Attributes:
        groups: One group per transitively connected mention set.
        matches: Evidence for every confirmed non-exact pair.
        ambiguous_count: LLM verdicts that came back uncertain. These
            pairs never merge.
    """

    groups: list[ResolutionGroup]
    matches: list[ResolvedMatch]
    ambiguous_count: int = 0


class ComparisonVerdict(StrEnum):
    """A Comparator's verdict on one entity pair.

    Attributes:
        MATCH: The comparator is confident these are the same entity.
        NO_MATCH: The comparator is confident these are different entities.
        UNCERTAIN: This comparator can't decide; the next one gets a turn.
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
    """Asks an LLM to verify an ambiguous pair. Last resort; never UNCERTAIN.

    Never raises from an LLM-call failure: it resolves to NO_MATCH instead, by
    the same fail-safe design as every comparator a Resolver runs — an
    ambiguous or failed comparison never merges two entities. A missing package
    extra is a configuration error, not an ambiguous judgment call, and is
    raised outright instead (see compare's Raises section).
    """

    def __init__(
        self,
        *,
        chunks_by_id: dict[UUID, Chunk],
        settings: ExtractionLLMSettings | None = None,
        client: object | None = None,
        max_pairs_per_batch: int = 50,
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
        """
        if max_pairs_per_batch <= 0:
            raise ValueError("max_pairs_per_batch must be positive")
        self.chunks_by_id = chunks_by_id
        self.settings = settings
        self._client = client
        self.max_pairs_per_batch = max_pairs_per_batch

    async def compare(
        self, a: ExtractedEntity, b: ExtractedEntity
    ) -> ComparisonVerdict:
        """Return the LLM's verdict for one pair, or NO_MATCH on failure.

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
    ) -> dict[tuple[int, int], ComparisonResult]:
        """Verify ambiguous candidate pairs across bounded LLM requests.

        Splits into requests of at most ``max_pairs_per_batch`` pairs so one
        oversized population cannot exceed the model's context limit.
        Invalid, missing, and uncertain model responses do not merge entities.
        """
        results, _ = await self.compare_batch_detailed(pairs, similarities=similarities)
        return results

    async def compare_batch_detailed(
        self,
        pairs: list[tuple[int, int, ExtractedEntity, ExtractedEntity]],
        *,
        similarities: dict[tuple[int, int], float] | None = None,
    ) -> tuple[dict[tuple[int, int], ComparisonResult], int]:
        """Verify pairs and count how many verdicts came back uncertain.

        Args:
            pairs: The candidate pairs to verify.
            similarities: Embedding similarity per pair, sent to the model
                as decision context. Defaults to 0.0 when unknown.

        Returns:
            The per-pair results and the count of raw uncertain verdicts,
            before the fail-safe maps them to NO_MATCH.
        """
        if not pairs:
            return {}, 0
        results: dict[tuple[int, int], ComparisonResult] = {}
        uncertain = 0
        for start in range(0, len(pairs), self.max_pairs_per_batch):
            chunk = pairs[start : start + self.max_pairs_per_batch]
            chunk_results, chunk_uncertain = await self._compare_batch_chunk(
                chunk, similarities=similarities
            )
            results.update(chunk_results)
            uncertain += chunk_uncertain
        return results, uncertain

    async def _compare_batch_chunk(
        self,
        pairs: list[tuple[int, int, ExtractedEntity, ExtractedEntity]],
        *,
        similarities: dict[tuple[int, int], float] | None = None,
    ) -> tuple[dict[tuple[int, int], ComparisonResult], int]:
        """Verify one bounded chunk of ambiguous candidate pairs in one LLM request."""
        if self._client is not None:
            client = self._client
            baml_options: dict = {}
            retry = NO_RETRY
        else:
            from agrag.llm import client_registry  # noqa: PLC0415

            client = self._default_client()
            settings = self.settings or ExtractionLLMSettings()
            registry = client_registry.build_client_registry(
                settings.clients, strategy=settings.strategy
            )
            baml_options = {"client_registry": registry}
            retry = settings.retry
        try:
            pair_ids = [f"{left}:{right}" for left, right, _, _ in pairs]
            known = similarities or {}
            inputs = [
                {
                    "pair_id": pair_id,
                    "entity_a": first.text,
                    "context_a": self._context_for(first),
                    "neighbors_a": [],
                    "entity_b": second.text,
                    "context_b": self._context_for(second),
                    "neighbors_b": [],
                    "similarity": known.get((left, right), 0.0),
                }
                for pair_id, (left, right, first, second) in zip(
                    pair_ids, pairs, strict=True
                )
            ]
            results = await call_with_retry(
                lambda: client.VerifyEntityMatches(  # ty: ignore[unresolved-attribute]
                    inputs, baml_options
                ),
                retry,
            )
        except Exception:  # noqa: BLE001
            return {
                (left, right): ComparisonResult(verdict=ComparisonVerdict.NO_MATCH)
                for left, right, _, _ in pairs
            }, 0
        from agrag.ingestion.resolve.batch_validation import (  # noqa: PLC0415
            validate_batch_verdicts,
        )

        verdicts = validate_batch_verdicts(pair_ids, results)
        uncertain = sum(
            verdict.verdict is ComparisonVerdict.UNCERTAIN
            for verdict in verdicts.values()
        )
        return {
            (left, right): _final_llm_result(verdicts[pair_id])
            for pair_id, (left, right, _, _) in zip(pair_ids, pairs, strict=True)
        }, uncertain

    def _default_client(self) -> object:
        """Return the default generated BAML client."""
        try:
            from agrag.llm.baml_client import b  # noqa: PLC0415
        except ImportError as exc:
            raise ExtractorMissingExtraError("LLMVerify", "llm") from exc
        return b

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


def _final_llm_result(result: ComparisonResult) -> ComparisonResult:
    """Make an inconclusive LLM judgment a fail-safe negative decision."""
    if result.verdict is ComparisonVerdict.UNCERTAIN:
        return ComparisonResult(verdict=ComparisonVerdict.NO_MATCH)
    return result


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
) -> ResolvedMatch:
    """Build a ResolvedMatch stamped with the current time."""
    return ResolvedMatch(
        left_index=left,
        right_index=right,
        comparator=comparator,
        score=score,
        reasoning=reasoning,
        decided_at=datetime.now(UTC),
    )


class Resolver:
    """Routes blocked candidate pairs through exact, fuzzy, embedding, and LLM zones.

    Exact identity groups mentions without evidence. A near-identical
    fuzzy score merges on the fast path. Every other pair consults its
    embedding cosine similarity: at or above the hard-merge threshold it
    merges, below the discard threshold it drops, and inside the band it
    needs LLM review, capped per label. Tight ambiguous sub-clusters
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
            max_llm_pairs: Maximum ambiguous pairs sent to the LLM per
                label.
            llm_batch_size: Pairs per LLM request. Must fit the
                LLMVerify comparator's max_pairs_per_batch.

        Raises:
            ValueError: llm_batch_size is not positive, or exceeds the
                LLMVerify comparator's max_pairs_per_batch.
        """
        if llm_batch_size <= 0:
            raise ValueError("llm_batch_size must be positive")
        self.comparators = comparators
        self.candidate_source = candidate_source
        self.embedder = embedder
        self.hard_merge_threshold = hard_merge_threshold
        self.discard_threshold = discard_threshold
        self.max_llm_pairs = max_llm_pairs
        self.llm_batch_size = llm_batch_size
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

    async def resolve(self, entities: list[ExtractedEntity]) -> ResolutionResult:
        """Resolve entity groups and retain each confirmed non-exact match.

        Args:
            entities: The entities to resolve. Only entities passed in the
                same call are ever compared against each other — resolving
                against previously-resolved entities from an earlier call is
                not supported by this Resolver.

        Returns:
            Groups for every input index, evidence for every confirmed
            non-exact pair, and the count of uncertain LLM verdicts.
        """
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
        edges, matches, ambiguous_count = await self._resolve_pairs(pairs, entities)
        groups = _group_matches(len(entities), edges)
        return ResolutionResult(
            groups=[ResolutionGroup(entity_indices=group) for group in groups],
            matches=matches,
            ambiguous_count=ambiguous_count,
        )

    async def _resolve_pairs(
        self, pairs: list[tuple[int, int]], entities: list[ExtractedEntity]
    ) -> tuple[list[tuple[int, int]], list[ResolvedMatch], int]:
        """Route candidate pairs through the exact, fuzzy, embedding, and LLM zones.

        LLM calls stay bounded: ambiguous pairs are capped per label at
        ``max_llm_pairs`` and pooled across labels into requests of
        ``llm_batch_size``, so one call makes at most
        ``ceil(L * max_llm_pairs / llm_batch_size)`` LLM requests for
        ``L`` labels.
        """
        edges: list[tuple[int, int]] = []
        matches: list[ResolvedMatch] = []
        fuzzy_uncertain: list[tuple[int, int, float]] = []
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

        ambiguous, scored = await self._embedding_tier(
            fuzzy_uncertain, entities, edges, matches
        )
        boundary = self._precluster_tier(ambiguous, scored, edges, matches)
        ambiguous_count = await self._llm_tier(boundary, entities, edges, matches)
        return edges, matches, ambiguous_count

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
        if not fuzzy_uncertain:
            return ambiguous, scored
        if self.embedder is None:
            for left, right, fuzzy_score in fuzzy_uncertain:
                ambiguous.setdefault(entities[left].label, []).append(
                    (left, right, fuzzy_score)
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
                    _match_record(left, right, comparator="embedding", score=similarity)
                )
            elif similarity >= self.discard_threshold:
                ambiguous.setdefault(label, []).append((left, right, similarity))
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
            for cluster in precluster_ambiguous(ids, similarities):
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
                            )
                        )
            for left, right, similarity in ambiguous.get(label, []):
                if (min(left, right), max(left, right)) not in auto_merged:
                    boundary.append((left, right, similarity))
        return boundary

    async def _llm_tier(
        self,
        boundary: list[tuple[int, int, float]],
        entities: list[ExtractedEntity],
        edges: list[tuple[int, int]],
        matches: list[ResolvedMatch],
    ) -> int:
        """Verify capped boundary pairs with the LLM and merge its matches.

        Returns:
            How many verdicts came back uncertain.
        """
        if not boundary or self._llm is None:
            return 0
        by_label: dict[str, list[tuple[int, int, float]]] = {}
        for left, right, similarity in boundary:
            by_label.setdefault(entities[left].label, []).append(
                (left, right, similarity)
            )
        selected: list[tuple[int, int]] = []
        for candidates in by_label.values():
            selected.extend(select_llm_pairs(candidates, max_pairs=self.max_llm_pairs))
        ambiguous_count = 0
        for start in range(0, len(selected), self.llm_batch_size):
            selected_chunk = selected[start : start + self.llm_batch_size]
            chunk = [
                (left, right, entities[left], entities[right])
                for left, right in selected_chunk
            ]
            chunk_similarities = {
                (left, right): similarity
                for left, right, similarity in boundary
                if (left, right) in selected_chunk
            }
            results, chunk_uncertain = await self._llm.compare_batch_detailed(
                chunk, similarities=chunk_similarities
            )
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
                        )
                    )
        return ambiguous_count
