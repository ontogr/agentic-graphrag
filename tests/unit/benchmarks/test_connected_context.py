"""Tests the evidence retrieval fixtures: their internal consistency.

The committed manifest is read as data, and nothing is fetched. The checks against
the pinned source text are in tests/integration/benchmarks.
"""

import hashlib
import json

import pytest

from benchmarks.fixtures.builders.connected_context import (
    MANIFEST_PATH,
    apply_edit,
    locate_answer,
)


LEGAL_URIS = {
    "privacy_qa/Keep.txt",
    "privacy_qa/Viber Messenger.txt",
    "contractnli/Kenway-NDA-Form-Blank.txt",
}


@pytest.fixture
def manifest() -> dict:
    """Return the committed manifest."""
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _v1_spans(manifest: dict) -> list[dict]:
    """Return every span of the unmodified documents, including hold-outs."""
    spans = []
    for case in manifest["cases"]:
        spans += case["support"]
        if "support" in case["holdout"]:
            spans += case["holdout"]["support"]
    return spans


def _case(manifest: dict, case_id: str) -> dict:
    """Return the case with the given id."""
    case = next((c for c in manifest["cases"] if c["id"] == case_id), None)
    assert case is not None, case_id
    return case


def _case_spans(case: dict) -> list[dict]:
    """Return every span one case cites, the main variant and its hold-out."""
    spans = list(case["support"])
    if "support" in case["holdout"]:
        spans += case["holdout"]["support"]
    return spans


def _after_spans(manifest: dict) -> list[tuple[dict, dict]]:
    """Return ``(mutation, span)`` pairs for every span after each mutation."""
    return [
        (mutation, span)
        for mutation in manifest["mutations"]
        for span in mutation["spans_after"]
    ]


class TestManifestShape:
    """The committed manifest holds consistent spans, edits and hashes."""

    @staticmethod
    def test_documents_are_the_three_legal_files_and_two_history_sessions(
        manifest,
    ):
        """The corpus has three legal documents and two BEAM sessions."""
        corpora = [d["corpus"] for d in manifest["documents"]]

        assert {d["uri"] for d in manifest["documents"] if d["corpus"] == "legal"} == (
            LEGAL_URIS
        )
        assert corpora.count("conversation_history") == 2
        assert manifest["name"] == "connected-context-evidence"
        assert "conversation_history" in manifest["upstream"]

    @staticmethod
    def test_every_span_stays_inside_its_document(manifest):
        """A span is non-empty and ends within the text it indexes."""
        lengths = {d["uri"]: d["char_count"] for d in manifest["documents"]}
        for span in _v1_spans(manifest):
            assert 0 <= span["char_start"] < span["char_end"]
            assert span["char_end"] <= lengths[span["document"]]
        for mutation, span in _after_spans(manifest):
            assert 0 <= span["char_start"] < span["char_end"]
            assert span["char_end"] <= mutation["char_count"]

    @staticmethod
    def test_legal_answers_have_the_length_of_their_span(manifest):
        """Each legal answer is as long as the span that names it."""
        for span in _v1_spans(manifest):
            if span["document"] in LEGAL_URIS and span.get("answer") is not None:
                assert len(span["answer"]) == span["char_end"] - span["char_start"]
        for _, span in _after_spans(manifest):
            if span.get("answer_after") is not None:
                assert len(span["answer_after"]) == (
                    span["char_end"] - span["char_start"]
                )

    @staticmethod
    def test_every_mutation_names_an_unmodified_base_version(manifest):
        """Each edit starts from a document version the manifest records."""
        base_hashes = {d["uri"]: d["content_sha256"] for d in manifest["documents"]}
        for mutation in manifest["mutations"]:
            assert mutation["base_content_sha256"] == base_hashes[mutation["base"]]
            assert len(mutation["content_sha256"]) == 64

    @pytest.mark.parametrize("mutation_id", ["M1", "M2", "M3"])
    @staticmethod
    def test_edits_move_only_spans_at_or_after_the_edit(manifest, mutation_id):
        """Spans before an edit stay put, spans after it shift by its length change."""
        mutation = next(
            (m for m in manifest["mutations"] if m["id"] == mutation_id), None
        )
        assert mutation is not None, mutation_id
        edit = mutation["edit"]
        edit_end = edit["char_start"] + len(edit["old"])
        delta = len(edit["new"]) - len(edit["old"])
        for span in mutation["spans_after"]:
            before = (span["v1_char_start"], span["v1_char_end"])
            if before[1] <= edit["char_start"]:
                expected = before
            elif before[0] >= edit_end:
                expected = (before[0] + delta, before[1] + delta)
            else:
                expected = (before[0], before[1] + delta)
            assert (span["char_start"], span["char_end"]) == expected

    @staticmethod
    def test_case_three_cites_no_span(manifest):
        """The no-support case has no span to cite, in either variant."""
        case = next(
            (c for c in manifest["cases"] if c["id"] == "insufficient_evidence"), None
        )
        assert case is not None

        assert case["support"] == []
        assert case["holdout"]["support"] == []

    @staticmethod
    def test_each_cross_session_question_cites_only_its_own_session(manifest):
        """A question is supported by its own excerpt and not by the other one."""
        case = next(
            (c for c in manifest["cases"] if c["id"] == "cross_session_recall"), None
        )
        assert case is not None

        for question in case["questions"]:
            cited = {
                span["document"]
                for span in case["support"]
                if span["question_id"] == question["question_id"]
            }

            assert cited == {question["support_document"]}
            assert not cited & set(question["must_not_cite"])

    @staticmethod
    def test_resume_step_cites_the_span_it_names(manifest):
        """Each step has a support record, and step B cites the second Keep span."""
        case = _case(manifest, "interruption_and_resume")
        records = {span["role"]: span for span in case["support"]}
        assert set(case["steps"]) <= set(records)

        source = _case(manifest, "source_span_retrieval")
        second_span = sorted(
            (span["label_char_start"], span["label_char_end"])
            for span in source["support"]
            if span["question_id"] == "privacy_qa:c96be584"
        )[1]
        assert (
            records["B"]["label_char_start"],
            records["B"]["label_char_end"],
        ) == second_span

    @staticmethod
    def test_resume_checkpoint_splits_steps_into_completed_and_pending(manifest):
        """The interrupted run completed some steps and left the others pending."""
        case = _case(manifest, "interruption_and_resume")
        completed = set(case["checkpoint"]["completed"])
        pending = set(case["checkpoint"]["pending"])

        assert completed
        assert pending
        assert not completed & pending
        assert completed | pending == set(case["steps"])

    @staticmethod
    def test_unrelated_edit_lies_outside_every_cited_span(manifest):
        """The edit declared unrelated touches no document or span the case cites."""
        case = _case(manifest, "source_change_review")
        cited_documents = {span["document"] for span in _case_spans(case)}
        mutation = next(
            m for m in manifest["mutations"] if m["id"] == case["unrelated_mutation"]
        )
        assert mutation["base"] not in cited_documents

        edit = mutation["edit"]
        edit_start = edit["char_start"]
        edit_end = edit_start + len(edit["old"])
        for span in _v1_spans(manifest):
            if span["document"] == mutation["base"]:
                assert span["char_end"] <= edit_start or edit_end <= span["char_start"]


class TestLocateAnswer:
    """The span self-check keeps a stored span or relocates its one exact match."""

    @staticmethod
    def test_keeps_a_span_that_reads_back():
        """A span whose text equals its answer is returned unchanged."""
        assert locate_answer("abc def", 4, 7, "def") == (4, 7)

    @staticmethod
    def test_relocates_an_answer_that_occurs_once():
        """A stale span moves to the single occurrence of its answer."""
        assert locate_answer("xx abc def", 0, 3, "abc def") == (3, 10)

    @pytest.mark.parametrize(
        ("text", "answer"),
        [("xabc abc", "abc"), ("abc def", "xyz"), ("xaaa", "aa")],
        ids=["ambiguous", "absent", "overlapping"],
    )
    @staticmethod
    def test_refuses_an_answer_without_exactly_one_match(text, answer):
        """An answer that is absent or repeated has no single place to cite."""
        with pytest.raises(ValueError):
            locate_answer(text, 0, len(answer), answer)


class TestApplyEdit:
    """The edit step replaces exactly one occurrence of the old text."""

    @staticmethod
    def test_refuses_old_text_whose_occurrences_overlap():
        """Overlapping occurrences of the replaced text make the edit ambiguous."""
        with pytest.raises(ValueError):
            apply_edit("xaaa", "aa", "b")


def _sha(text: str) -> str:
    """Return the SHA-256 of a text as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
