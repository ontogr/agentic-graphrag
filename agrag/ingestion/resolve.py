"""Entity resolution: deciding which ExtractedEntity mentions are the same thing."""

from abc import ABC, abstractmethod
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.text import normalize_text as _normalize
from agrag.ingestion.extract import ExtractionLLMSettings, ExtractorMissingExtraError
from agrag.llm.retry import NO_RETRY, call_with_retry


class ResolutionGroup(BaseModel):
    """One set of ExtractedEntity indices resolution decided are the same entity.

    Attributes:
        entity_indices: Indices into the entity list passed to Resolver.resolve.
            A group of one means resolution found no match for that entity.
    """

    entity_indices: list[int]


class CandidateSource(ABC):
    """Narrows which entity pairs resolution compares — the blocking step."""

    @abstractmethod
    async def candidates_for(
        self, index: int, entities: list[ExtractedEntity]
    ) -> list[int]:
        """Return indices worth comparing against entities[index].

        Args:
            index: The entity to find candidates for.
            entities: The full entity list this call is scoped to.

        Returns:
            Indices into ``entities``, excluding ``index`` itself. Order does
            not matter; duplicates are harmless but wasteful.
        """


class InBatchCandidateSource(CandidateSource):
    """Blocks by label: only entities sharing a label are ever compared.

    Scoped to whatever entity list a caller passes to candidates_for — today,
    always the current extraction batch. A future graph-backed candidate source
    can replace this without changing any Comparator, since comparators only
    ever see the pairs a CandidateSource proposes.
    """

    async def candidates_for(
        self, index: int, entities: list[ExtractedEntity]
    ) -> list[int]:
        """Return every other entity sharing entities[index]'s label."""
        label = entities[index].label
        return [
            other_index
            for other_index, entity in enumerate(entities)
            if other_index != index and entity.label == label
        ]


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
    """Matches by string similarity, within a confident-match/distinct band.

    Attributes:
        match_above: A similarity score at or above this is a confident match.
        no_match_below: A similarity score below this is a confident non-match.
            A score in between is UNCERTAIN and defers to the next comparator.
    """

    def __init__(
        self, *, match_above: float = 0.92, no_match_below: float = 0.70
    ) -> None:
        """Create a comparator with the given match/no-match band."""
        self.match_above = match_above
        self.no_match_below = no_match_below

    async def compare(
        self, a: ExtractedEntity, b: ExtractedEntity
    ) -> ComparisonVerdict:
        """Return a verdict from token-sort-ratio similarity."""
        from rapidfuzz import fuzz  # noqa: PLC0415

        score = fuzz.token_sort_ratio(_normalize(a.text), _normalize(b.text)) / 100
        if score >= self.match_above:
            return ComparisonVerdict.MATCH
        if score < self.no_match_below:
            return ComparisonVerdict.NO_MATCH
        return ComparisonVerdict.UNCERTAIN


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
    ) -> None:
        """Create a comparator with chunk lookup for context and an LLM client.

        Args:
            chunks_by_id: Maps a Chunk id to the Chunk, for prompt context.
            settings: LLM client config. Defaults to ``ExtractionLLMSettings()``.
                Ignored when ``client`` is given: an injected client also
                disables ``settings.retry``, since a caller building its own
                client is assumed to own its own retry behavior too.
            client: An already-built BAML client. Tests inject a fake here.
        """
        self.chunks_by_id = chunks_by_id
        self.settings = settings
        self._client = client

    async def compare(
        self, a: ExtractedEntity, b: ExtractedEntity
    ) -> ComparisonVerdict:
        """Return the LLM's verdict, or NO_MATCH if the call itself fails.

        Raises:
            ExtractorMissingExtraError: The ``llm`` package extra is not
                installed.
        """
        if self._client is not None:
            client = self._client
            baml_options: dict = {}
            retry = NO_RETRY
        else:
            from agrag.llm.client_registry import build_client_registry  # noqa: PLC0415

            client = self._default_client()
            settings = self.settings or ExtractionLLMSettings()
            registry = build_client_registry(
                settings.clients, strategy=settings.strategy
            )
            baml_options = {"client_registry": registry}
            retry = settings.retry
        try:
            # ponytail: retries every exception except the BAML error types
            # call_with_retry recognizes as permanently unretryable (an
            # invalid argument or a non-429 4xx); narrow further if noisy.
            is_match = await call_with_retry(
                lambda: client.VerifyEntityMatch(  # ty: ignore[unresolved-attribute]
                    a.text,
                    self._context_for(a),
                    b.text,
                    self._context_for(b),
                    baml_options,
                ),
                retry,
            )
        except Exception:  # noqa: BLE001
            return ComparisonVerdict.NO_MATCH
        return ComparisonVerdict.MATCH if is_match else ComparisonVerdict.NO_MATCH

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


class Resolver:
    """Runs an ordered comparator sequence over blocked candidate pairs.

    Groups every pair a comparator confirms as a match into a ResolutionGroup.
    """

    def __init__(
        self, *, comparators: list[Comparator], candidate_source: CandidateSource
    ) -> None:
        """Create a resolver from an ordered comparator sequence and a candidate source.

        Args:
            comparators: Tried in order per candidate pair. The first
                non-UNCERTAIN verdict wins; if every comparator is UNCERTAIN,
                the pair does not merge.
            candidate_source: Narrows which pairs get compared at all.
        """
        self.comparators = comparators
        self.candidate_source = candidate_source

    async def resolve(self, entities: list[ExtractedEntity]) -> list[ResolutionGroup]:
        """Group entities that resolution decided are the same thing.

        Args:
            entities: The entities to resolve. Only entities passed in the
                same call are ever compared against each other — resolving
                against previously-resolved entities from an earlier call is
                not supported by this Resolver.

        Returns:
            One ResolutionGroup per distinct entity found. Every input index
            appears in exactly one group.
        """
        edges: list[tuple[int, int]] = []
        compared: set[tuple[int, int]] = set()
        for index in range(len(entities)):
            candidates = await self.candidate_source.candidates_for(index, entities)
            for candidate_index in candidates:
                pair = (min(index, candidate_index), max(index, candidate_index))
                if pair in compared:
                    continue
                compared.add(pair)
                verdict = await self._first_verdict(
                    entities[index], entities[candidate_index]
                )
                if verdict is ComparisonVerdict.MATCH:
                    edges.append(pair)
        groups = _group_matches(len(entities), edges)
        return [ResolutionGroup(entity_indices=group) for group in groups]

    async def _first_verdict(
        self, a: ExtractedEntity, b: ExtractedEntity
    ) -> ComparisonVerdict:
        """Return the first non-UNCERTAIN verdict, or NO_MATCH if none.

        This is the fail-safe fallback: a pair every comparator is UNCERTAIN
        about is treated as distinct, never merged.
        """
        for comparator in self.comparators:
            verdict = await comparator.compare(a, b)
            if verdict is not ComparisonVerdict.UNCERTAIN:
                return verdict
        return ComparisonVerdict.NO_MATCH
