"""Integration tests for citation traceability checks over the authored corpus.

The ids come from real fetches, so the verdicts depend on what the caller
fetched. A verdict says only whether a citation traces to fetched evidence. It
says nothing about whether the cited text supports a claim.
"""

from uuid import uuid4

from agrag.common.data_models.evidence import (
    CitationCheck,
    CitationVerdict,
    EvidenceKind,
    EvidenceReference,
    FetchStatus,
)
from agrag.evidence import check_citations, fetch
from agrag.evidence.ids import encode_evidence_id
from tests.integration.retrieval.evidence._corpus import (
    GOLD_SENTENCE,
    KEEP_TEXT,
    locate,
    span_evidence_id,
)
from tests.integration.retrieval.evidence.conftest import EvidenceEnv


_GOLD_START, _GOLD_END = locate(KEEP_TEXT, GOLD_SENTENCE)
_OTHER_START, _OTHER_END = locate(
    KEEP_TEXT, "Questions about this notice can be sent to the support team."
)


async def _fetched_ids(env: EvidenceEnv, evidence_ids: list[str]) -> list[str]:
    """Fetch ids with every corpus document in scope and keep the ok ones."""
    outcomes = await fetch(
        env.store,
        evidence_ids,
        scope=frozenset({env.keep, env.viber, env.harbor}),
        max_chars=8000,
    )
    return [o.evidence_id for o in outcomes if o.status is FetchStatus.OK]


async def _verdicts(
    cited: list[str], fetched: list[str], scope: frozenset[str]
) -> list[CitationVerdict]:
    """Return the verdicts for cited ids in order."""
    checks: list[CitationCheck] = await check_citations(cited, fetched, scope=scope)
    assert [check.cited_id for check in checks] == cited
    return [check.verdict for check in checks]


class TestCitationVerdicts:
    """Each citation gets the verdict that matches what the caller fetched."""

    async def test_fetched_id_is_valid(self, evidence_env: EvidenceEnv) -> None:
        """A citation of an id the caller fetched is valid."""
        gold = span_evidence_id(evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END)
        fetched = await _fetched_ids(evidence_env, [gold])

        verdicts = await _verdicts(
            [gold], fetched, frozenset({evidence_env.keep, evidence_env.viber})
        )

        assert verdicts == [CitationVerdict.VALID]

    async def test_malformed_citation_is_malformed(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """An invented string that does not decode is malformed."""
        verdicts = await _verdicts(
            ["ev1:s:made-up:0123456789abcdef:1-5"],
            [],
            frozenset({evidence_env.keep}),
        )

        assert verdicts == [CitationVerdict.MALFORMED]

    async def test_invented_id_for_an_unknown_document_is_unavailable(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A well-formed id for a document outside the scope is unavailable."""
        invented = encode_evidence_id(
            EvidenceReference(
                kind=EvidenceKind.SPAN,
                document_node_id=uuid4(),
                content_hash_prefix="0123456789abcdef",
                char_start=0,
                char_end=10,
            )
        )

        verdicts = await _verdicts([invented], [], frozenset({evidence_env.keep}))

        assert verdicts == [CitationVerdict.UNAVAILABLE]

    async def test_real_id_never_fetched_is_not_fetched(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """An in-scope id the caller did not fetch is not fetched."""
        never_fetched = span_evidence_id(
            evidence_env.keep, KEEP_TEXT, _OTHER_START, _OTHER_END
        )
        gold = span_evidence_id(evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END)
        fetched = await _fetched_ids(evidence_env, [gold])

        verdicts = await _verdicts(
            [never_fetched], fetched, frozenset({evidence_env.keep})
        )

        assert verdicts == [CitationVerdict.NOT_FETCHED]

    async def test_out_of_scope_id_is_unavailable_even_if_fetched_earlier(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """Scope is checked first, so a fetched id outside the scope is unavailable."""
        gold = span_evidence_id(evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END)
        fetched = await _fetched_ids(evidence_env, [gold])

        verdicts = await _verdicts([gold], fetched, frozenset({evidence_env.viber}))

        assert verdicts == [CitationVerdict.UNAVAILABLE]

    async def test_narrower_range_inside_a_fetched_span_is_valid(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A cited span inside a fetched span of the same version is valid."""
        fetched_id = span_evidence_id(
            evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END
        )
        narrower = span_evidence_id(
            evidence_env.keep, KEEP_TEXT, _GOLD_START + 4, _GOLD_END - 4
        )
        fetched = await _fetched_ids(evidence_env, [fetched_id])

        verdicts = await _verdicts([narrower], fetched, frozenset({evidence_env.keep}))

        assert verdicts == [CitationVerdict.VALID]

    async def test_wider_range_than_a_fetched_span_is_not_fetched(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A cited span that reaches past the fetched range is not fetched."""
        fetched_id = span_evidence_id(
            evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END
        )
        wider = span_evidence_id(
            evidence_env.keep, KEEP_TEXT, _GOLD_START - 4, _GOLD_END
        )
        fetched = await _fetched_ids(evidence_env, [fetched_id])

        verdicts = await _verdicts([wider], fetched, frozenset({evidence_env.keep}))

        assert verdicts == [CitationVerdict.NOT_FETCHED]

    async def test_malformed_fetched_ids_do_not_validate_anything(
        self, evidence_env: EvidenceEnv
    ) -> None:
        """A malformed id in the fetched list does not make a citation valid."""
        gold = span_evidence_id(evidence_env.keep, KEEP_TEXT, _GOLD_START, _GOLD_END)

        verdicts = await _verdicts(
            [gold], ["ev1:s:garbage"], frozenset({evidence_env.keep})
        )

        assert verdicts == [CitationVerdict.NOT_FETCHED]
