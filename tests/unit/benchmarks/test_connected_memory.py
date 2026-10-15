"""Tests the evidence retrieval fixtures: their internal consistency and text.

The committed manifest is read as data, and nothing is fetched. The text checks run
only when the pinned files are already in the local Hugging Face cache, so the test
never reaches the network.
"""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from huggingface_hub import hf_hub_download
from huggingface_hub.errors import LocalEntryNotFoundError

from benchmarks.datasets.fetch import CACHE_DIR
from benchmarks.datasets.legal import REPO as LEGAL_REPO
from benchmarks.datasets.legal import REVISION as LEGAL_REVISION
from benchmarks.datasets.memory import PARQUET_FILE, session_document_text
from benchmarks.datasets.memory import REPO as BEAM_REPO
from benchmarks.datasets.memory import REVISION as BEAM_REVISION
from benchmarks.fixtures.builders.connected_memory import (
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


def _cached(repo: str, filename: str, revision: str) -> Path | None:
    """Return the cached copy of a pinned file, or None when it is not cached."""
    try:
        return Path(
            hf_hub_download(
                repo,
                filename,
                repo_type="dataset",
                revision=revision,
                cache_dir=CACHE_DIR / "hf",
                local_files_only=True,
            )
        )
    except LocalEntryNotFoundError:
        return None


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


def _memory_texts(manifest: dict) -> dict[str, str] | None:
    """Return each BEAM session text rebuilt from the cached chat file, or None."""
    path = _cached(BEAM_REPO, PARQUET_FILE, BEAM_REVISION)
    if path is None:
        return None
    rows = {
        row["conversation_id"]: row
        for row in pq.read_table(path, columns=["conversation_id", "chat"]).to_pylist()
    }
    texts = {}
    for document in manifest["documents"]:
        if document["corpus"] != "memory":
            continue
        _, conversation, session_label = document["uri"].split("/")
        number = int(session_label.removeprefix("session-"))
        session = rows[conversation]["chat"][number - 1]
        texts[document["uri"]] = session_document_text(
            session, number, conversation, document["messages"]
        )
    return texts


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
    def test_documents_are_the_three_legal_files_and_two_memory_sessions(
        manifest,
    ):
        """The corpus has three legal documents and two BEAM sessions."""
        corpora = [d["corpus"] for d in manifest["documents"]]

        assert {d["uri"] for d in manifest["documents"] if d["corpus"] == "legal"} == (
            LEGAL_URIS
        )
        assert corpora.count("memory") == 2

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


class TestCorpusText:
    """Text-level checks against the pinned files, when they are cached locally."""

    @pytest.mark.parametrize("uri", sorted(LEGAL_URIS))
    @staticmethod
    def test_legal_file_matches_its_content_hash(manifest, uri):
        """The pinned file reads back to the stored hash, unchanged by normalization."""
        path = _cached(LEGAL_REPO, f"corpus/{uri}", LEGAL_REVISION)
        if path is None:
            pytest.skip("pinned legal file is not in the local cache")
        text = path.read_text(encoding="utf-8")
        document = next((d for d in manifest["documents"] if d["uri"] == uri), None)
        assert document is not None

        assert _sha(text) == document["content_sha256"]

    @staticmethod
    def test_stored_span_text_hashes_match(manifest):
        """Each span's stored hash and its legal answer match the cached file."""
        texts = {}
        for uri in LEGAL_URIS:
            path = _cached(LEGAL_REPO, f"corpus/{uri}", LEGAL_REVISION)
            if path is None:
                pytest.skip("pinned legal files are not in the local cache")
            texts[uri] = path.read_text(encoding="utf-8")
        for span in _v1_spans(manifest):
            if span["document"] not in LEGAL_URIS:
                continue
            text = texts[span["document"]]
            found = text[span["char_start"] : span["char_end"]]
            assert _sha(found) == span["text_sha256"]
            if span.get("answer") is not None:
                assert found == span["answer"]

    @staticmethod
    def test_mutated_text_is_the_plain_replacement(manifest):
        """Each edit replaces the text at its recorded offset in the cached file."""
        texts = {}
        for uri in LEGAL_URIS:
            path = _cached(LEGAL_REPO, f"corpus/{uri}", LEGAL_REVISION)
            if path is None:
                pytest.skip("pinned legal files are not in the local cache")
            texts[uri] = path.read_text(encoding="utf-8")
        for mutation in manifest["mutations"]:
            base = texts[mutation["base"]]
            edit = mutation["edit"]
            start = edit["char_start"]
            end = start + len(edit["old"])
            assert base[start:end] == edit["old"]
            edited = base[:start] + edit["new"] + base[end:]
            assert _sha(edited) == mutation["content_sha256"]
            assert len(edited) == mutation["char_count"]
            for span in mutation["spans_after"]:
                if span["document"] != mutation["base"]:
                    continue
                found = edited[span["char_start"] : span["char_end"]]
                assert _sha(found) == span["text_sha256_after"]
                if span.get("answer_after") is not None:
                    assert found == span["answer_after"]

    @staticmethod
    def test_memory_sessions_match_their_stored_hashes(manifest):
        """Each BEAM session rebuilt from the cached chat file matches its hash."""
        texts = _memory_texts(manifest)
        if texts is None:
            pytest.skip("pinned BEAM file is not in the local cache")
        for document in manifest["documents"]:
            if document["corpus"] == "memory":
                assert _sha(texts[document["uri"]]) == document["content_sha256"]

    @staticmethod
    def test_memory_spans_read_back_from_their_session(manifest):
        """Each BEAM span lies inside its session and reads back to its hash."""
        texts = _memory_texts(manifest)
        if texts is None:
            pytest.skip("pinned BEAM file is not in the local cache")
        for span in _v1_spans(manifest):
            if span["document"] not in texts:
                continue
            text = texts[span["document"]]
            assert 0 <= span["char_start"] < span["char_end"] <= len(text)
            found = text[span["char_start"] : span["char_end"]]
            assert _sha(found) == span["text_sha256"]

    @staticmethod
    def test_memory_distractor_counts_match_the_other_session(manifest):
        """Each evidence phrase is counted in the other session as the manifest says."""
        texts = _memory_texts(manifest)
        if texts is None:
            pytest.skip("pinned BEAM file is not in the local cache")
        for span in _case(manifest, "cross_session_recall")["support"]:
            found = texts[span["document"]][span["char_start"] : span["char_end"]]
            others = [text for uri, text in texts.items() if uri != span["document"]]
            assert span["distractor_matches_in_other_excerpt"] == sum(
                text.count(found) for text in others
            )


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
