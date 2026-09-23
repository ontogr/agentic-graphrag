"""Tests for LLMVerify.compare_batch over the VerifyEntityMatches BAML function.

Uses an injected fake client, so no LLM is called. Covers sending seven
pairs in one request, splitting populations at max_pairs_per_batch (five
and ten pairs), mapping verdicts to pairs by pair_id rather than response
position, failing safe to NO_MATCH with no partial results when the batch
call raises, and the generated MatchVerdict model declaring reasoning
before verdict.
"""

from uuid import UUID, uuid4

import pytest

from agrag.common.data_models.chunk import Chunk
from agrag.common.data_models.extraction import ExtractedEntity
from agrag.common.data_models.provenance import TextProvenance
from agrag.ingestion.resolve import ComparisonVerdict, LLMVerify
from agrag.llm.baml_client.types import MatchVerdict


_DOC_ID = uuid4()


def _chunk(text: str = "context") -> Chunk:
    """Build a minimal Chunk."""
    return Chunk(
        document_id=_DOC_ID,
        text=text,
        provenance=TextProvenance(char_start=0, char_end=len(text)),
    )


def _entity(text: str, chunk_id: UUID) -> ExtractedEntity:
    """Build a minimal ExtractedEntity."""
    return ExtractedEntity(
        chunk_id=chunk_id,
        label="Person",
        text=text,
        char_start=0,
        char_end=max(len(text), 1),
    )


def _match(pair_id: str, reasoning: str = "same") -> dict[str, str]:
    """Build a match verdict payload for one pair."""
    return {"pair_id": pair_id, "verdict": "match", "reasoning": reasoning}


class _BatchClient:
    """Record requests and reply from a per-request script."""

    def __init__(self, replies: list[list | Exception]) -> None:
        """Serve one script entry per request; exceptions raise."""
        self.replies = replies
        self.calls: list[tuple[list, dict]] = []

    async def VerifyEntityMatches(  # noqa: N802
        self, pairs: list, options: dict
    ) -> list:
        """Record one request and return its scripted reply."""
        self.calls.append((pairs, options))
        reply = self.replies[len(self.calls) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply


def _verifier(
    count: int, client: _BatchClient, max_pairs_per_batch: int = 50
) -> tuple[LLMVerify, list[tuple[int, int, ExtractedEntity, ExtractedEntity]]]:
    """Build a verifier over count entities sharing one chunk, plus pairs."""
    chunk = _chunk()
    entities = [_entity(f"Entity {index}", chunk.id) for index in range(count)]
    verifier = LLMVerify(
        chunks_by_id={chunk.id: chunk},
        client=client,
        max_pairs_per_batch=max_pairs_per_batch,
    )
    pairs = [
        (index, index + 1, entities[index], entities[index + 1])
        for index in range(count - 1)
    ]
    return verifier, pairs


class TestCompareBatch:
    """compare_batch verifies many pairs across bounded LLM requests."""

    async def test_seven_pairs_send_one_request(self) -> None:
        """Seven pairs fit in the default batch and map back by pair_id."""
        client = _BatchClient([[_match(f"{index}:{index + 1}") for index in range(7)]])
        verifier, pairs = _verifier(8, client)

        results = await verifier.compare_batch(pairs)

        assert len(client.calls) == 1
        assert len(client.calls[0][0]) == 7
        assert client.calls[0][1] == {}
        assert len(results) == 7
        for index in range(7):
            assert results[(index, index + 1)].verdict is ComparisonVerdict.MATCH
            assert results[(index, index + 1)].reasoning == "same"

    @pytest.mark.parametrize(
        ("count", "expected_calls", "expected_sizes"),
        [(6, 1, [5]), (8, 2, [5, 2]), (11, 2, [5, 5])],
    )
    async def test_batching_bounds(
        self, count: int, expected_calls: int, expected_sizes: list[int]
    ) -> None:
        """Five- and ten-pair populations split into requests of five."""
        client = _BatchClient([[_match("0:1")] for _ in range(expected_calls)])
        verifier, pairs = _verifier(count, client, max_pairs_per_batch=5)

        await verifier.compare_batch(pairs)

        assert len(client.calls) == expected_calls
        assert [len(call[0]) for call in client.calls] == expected_sizes

    async def test_verdicts_map_by_pair_id_not_position(self) -> None:
        """A reversed response still judges each requested pair correctly."""
        client = _BatchClient(
            [[_match("1:2", "same person"), {"pair_id": "0:1", "verdict": "no_match"}]]
        )
        verifier, pairs = _verifier(3, client)

        results = await verifier.compare_batch(pairs[:2])

        assert results[(1, 2)].verdict is ComparisonVerdict.MATCH
        assert results[(1, 2)].reasoning == "same person"
        assert results[(0, 1)].verdict is ComparisonVerdict.NO_MATCH

    async def test_failed_batch_resolves_every_pair_without_partial(self) -> None:
        """A raising batch call marks every requested pair NO_MATCH."""
        client = _BatchClient([RuntimeError("LLM call failed")])
        verifier, pairs = _verifier(8, client)

        results = await verifier.compare_batch(pairs)

        assert set(results) == {(left, right) for left, right, _, _ in pairs}
        for result in results.values():
            assert result.verdict is ComparisonVerdict.NO_MATCH

    async def test_failed_chunk_marks_only_its_own_pairs(self) -> None:
        """A mid-batch failure keeps earlier chunks and fails the rest safe."""
        client = _BatchClient(
            [
                [_match(f"{index}:{index + 1}") for index in range(5)],
                RuntimeError("LLM call failed"),
            ]
        )
        verifier, pairs = _verifier(8, client, max_pairs_per_batch=5)

        results = await verifier.compare_batch(pairs)

        for index in range(5):
            assert results[(index, index + 1)].verdict is ComparisonVerdict.MATCH
        for index in range(5, 7):
            assert results[(index, index + 1)].verdict is ComparisonVerdict.NO_MATCH


class TestMatchVerdictFieldOrder:
    """The generated MatchVerdict model declares reasoning before verdict."""

    def test_reasoning_precedes_verdict(self) -> None:
        """Field order keeps the explanation ahead of the judgment."""
        assert list(MatchVerdict.model_fields) == [
            "pair_id",
            "reasoning",
            "verdict",
        ]


class TestCompareBatchDetailed:
    """compare_batch_detailed returns results plus the uncertain count."""

    async def test_counts_uncertain_verdicts(self) -> None:
        """One uncertain verdict counts 1 while match and no_match count 0."""
        client = _BatchClient(
            [
                [
                    _match("0:1"),
                    {"pair_id": "1:2", "verdict": "uncertain"},
                    {"pair_id": "2:3", "verdict": "no_match"},
                ]
            ]
        )
        verifier, pairs = _verifier(4, client)

        results, uncertain = await verifier.compare_batch_detailed(pairs[:3])

        assert results[(0, 1)].verdict is ComparisonVerdict.MATCH
        assert results[(1, 2)].verdict is ComparisonVerdict.NO_MATCH
        assert results[(2, 3)].verdict is ComparisonVerdict.NO_MATCH
        assert uncertain == 1

    async def test_compare_batch_delegates_without_count(self) -> None:
        """compare_batch returns the same verdicts as the detailed call."""
        client = _BatchClient([[_match("0:1")]])
        verifier, pairs = _verifier(2, client)

        results = await verifier.compare_batch(pairs[:1])

        assert results[(0, 1)].verdict is ComparisonVerdict.MATCH

    async def test_known_similarities_reach_the_model(self) -> None:
        """Supplied embedding similarities are sent, not a 0.0 default."""
        client = _BatchClient([[_match("0:1"), _match("1:2")]])
        verifier, pairs = _verifier(3, client)

        await verifier.compare_batch(
            pairs[:2], similarities={(0, 1): 0.83, (1, 2): 0.91}
        )

        sent = client.calls[0][0]
        assert [item["similarity"] for item in sent] == [0.83, 0.91]

    async def test_missing_similarity_defaults_to_zero(self) -> None:
        """Pairs without a supplied similarity still send 0.0."""
        client = _BatchClient([[_match("0:1")]])
        verifier, pairs = _verifier(2, client)

        await verifier.compare_batch(pairs[:1])

        assert client.calls[0][0][0]["similarity"] == 0.0
