"""Tests the Legal dataset: fixtures, document text, schema and span scores.

The document fetch is patched to local files, so no network is needed.
"""

import unicodedata
from pathlib import Path

import pytest

from agrag.common.data_models.graph_schema import GraphSchema
from benchmarks.datasets import legal
from benchmarks.datasets.legal import BENCHMARK_FILES_SHA256, LegalAdapter
from benchmarks.grading import legal_spans
from benchmarks.grading.legal_spans import LegalGrader, precision_recall
from benchmarks.harness.config import BENCH_CHUNKING
from benchmarks.models import BenchmarkQuestion, Corpus, CorpusDocument
from benchmarks.schemas.legal import LEGAL
from benchmarks.systems.base import CitedChunk, SystemAnswer


GOLD = [("a.txt", 10, 20), ("a.txt", 40, 50)]


class TestFixtures:
    """The committed lite and full fixtures."""

    def test_full_has_25_questions_for_each_of_four_sources(self):
        """Full has 100 questions, 25 per source, on 15 documents."""
        manifest = LegalAdapter().load("full")

        groups = [q.group for q in manifest.questions]

        assert len(manifest.questions) == 100
        assert {g: groups.count(g) for g in set(groups)} == dict.fromkeys(
            ("privacy_qa", "contractnli", "maud", "cuad"), 25
        )
        assert len(manifest.corpora[0].documents) == 15
        assert manifest.corpora[0].n_tokens == 223_766

    def test_lite_is_two_questions_on_one_short_privacy_policy(self):
        """Lite has a one-span and a two-span question on one policy."""
        manifest = LegalAdapter().load("lite")

        (document,) = manifest.corpora[0].documents
        spans = [len(q.reference["snippets"]) for q in manifest.questions]

        assert document.uri == "privacy_qa/Keep.txt"
        assert manifest.corpora[0].n_tokens == 2_024
        assert spans == [1, 2]

    def test_lite_questions_are_a_subset_of_full(self):
        """Every lite question is also a full question, with the same content."""
        full = {q.id: q for q in LegalAdapter().load("full").questions}

        for question in LegalAdapter().load("lite").questions:
            other = full[question.id]
            assert other.messages == question.messages
            assert other.reference == question.reference

    @pytest.mark.parametrize("mode", ["lite", "full"])
    def test_every_span_points_into_a_corpus_document(self, mode):
        """Every gold snippet names a document of its corpus, with a valid span."""
        manifest = LegalAdapter().load(mode)
        uris = {d.uri for d in manifest.corpora[0].documents}

        for question in manifest.questions:
            assert question.id.startswith(question.group + ":")
            assert question.query.startswith("Consider ")
            for snippet in question.reference["snippets"]:
                start, end = snippet["span"]
                assert snippet["uri"] in uris
                assert 0 <= start < end
                assert len(snippet["answer"]) == end - start

    def test_documents_are_pinned_by_hash_and_paths_are_nfc(self):
        """Each document has a SHA-256, and no path is in decomposed form."""
        for document in LegalAdapter().load("full").corpora[0].documents:
            assert len(document.sha256) == 64
            assert unicodedata.is_normalized("NFC", document.uri)

    def test_upstream_pins_the_revision_and_the_benchmark_files(self):
        """The manifest names the revision and the hash of the benchmark files."""
        upstream = LegalAdapter().load("lite").upstream

        assert len(upstream["revision"]) == 40
        assert upstream["benchmark_files_sha256"] == BENCHMARK_FILES_SHA256


class TestDocuments:
    """Document text keeps the offsets that gold spans use."""

    def _corpus(self, tmp_path: Path, monkeypatch, files: dict[str, bytes]) -> Corpus:
        for name, data in files.items():
            (tmp_path / name).write_bytes(data)
        monkeypatch.setattr(
            legal,
            "fetch_hf_file",
            lambda repo, filename, *, revision, sha256: (
                tmp_path / filename.removeprefix("corpus/")
            ),
        )
        return Corpus(
            id="c",
            service="legal-lite",
            schema_name="legal",
            documents=[
                CorpusDocument(id=n, uri=n, sha256="0", source="x") for n in files
            ],
        )

    def test_keeps_the_byte_order_mark_and_turns_crlf_into_lf(
        self, tmp_path, monkeypatch
    ):
        """The text starts with the mark, and a CRLF pair is one character."""
        corpus = self._corpus(
            tmp_path,
            monkeypatch,
            {"bom.txt": b"\xef\xbb\xbfone\r\ntwo", "plain.txt": b"abc"},
        )

        documents = LegalAdapter().documents(corpus)

        assert [d.text for d in documents] == ["﻿one\ntwo", "abc"]
        assert [d.uri for d in documents] == ["bom.txt", "plain.txt"]

    def test_every_chunk_text_is_the_slice_at_its_offsets(self, tmp_path, monkeypatch):
        """Chunk offsets index the document text, so gold spans line up."""
        body = "\r\n".join(
            f"Clause {i}. The parties agree to term {i}." for i in range(400)
        )
        corpus = self._corpus(
            tmp_path, monkeypatch, {"a.txt": b"\xef\xbb\xbf" + body.encode()}
        )
        (document,) = LegalAdapter().documents(corpus)

        chunks = BENCH_CHUNKING.chunk(document).chunks

        assert len(chunks) > 1
        for chunk in chunks:
            start, end = chunk.provenance.char_start, chunk.provenance.char_end
            assert chunk.text == document.text[start:end]


class TestSchema:
    """The legal graph schema."""

    def test_schema_has_the_planned_size_and_survives_a_round_trip(self):
        """The schema has 11 entity types, 16 relations and 12 clause kinds."""
        assert len(LEGAL.entities) == 11
        assert len(LEGAL.relations) == 16
        clause = next(e for e in LEGAL.entities if e.label == "Clause")
        assert len(clause.subtypes) == 12
        assert GraphSchema.model_validate(LEGAL.model_dump(mode="json")) == LEGAL

    def test_adapter_returns_the_schema(self):
        """The adapter returns the legal schema for its corpus."""
        corpus = LegalAdapter().load("lite").corpora[0]

        assert LegalAdapter().schema(corpus) is LEGAL


class TestPrecisionRecall:
    """The span formulas, checked on hand-computed cases."""

    def test_exact_retrieval_scores_one(self):
        """Retrieving exactly the gold spans gives precision and recall 1."""
        assert precision_recall(GOLD, GOLD) == (1.0, 1.0)

    def test_a_larger_span_lowers_precision_only(self):
        """One span of 40 characters that holds 10 gold characters."""
        precision, recall = precision_recall([("a.txt", 0, 40)], GOLD[:1])

        assert (precision, recall) == (0.25, 1.0)

    def test_a_partial_span_lowers_recall_only(self):
        """A span that covers 5 of 10 gold characters."""
        assert precision_recall([("a.txt", 10, 15)], GOLD[:1]) == (1.0, 0.5)

    def test_gold_spans_of_one_question_add_up(self):
        """Half of the retrieved characters are gold, and 15 of 20 gold are found."""
        precision, recall = precision_recall(
            [("a.txt", 5, 25), ("a.txt", 40, 45)], GOLD
        )

        assert precision == pytest.approx(15 / 25)
        assert recall == pytest.approx(15 / 20)

    def test_touching_spans_do_not_overlap(self):
        """The end is exclusive, so a span that ends at the gold start scores 0."""
        assert precision_recall([("a.txt", 0, 10)], GOLD[:1]) == (0.0, 0.0)

    def test_another_document_scores_zero(self):
        """The same offsets in another file do not match."""
        assert precision_recall([("b.txt", 10, 20)], GOLD[:1]) == (0.0, 0.0)

    def test_nothing_retrieved_scores_zero(self):
        """An empty retrieval gives 0 for both, not a division error."""
        assert precision_recall([], GOLD) == (0.0, 0.0)


class _Judge:
    """Stands in for the judge; the patched quality function ignores it."""


def _question(uri: str = "d.txt") -> BenchmarkQuestion:
    return BenchmarkQuestion(
        id="q",
        corpus_id="c",
        messages=[{"role": "user", "content": "Consider X; what?"}],
        group="cuad",
        reference={
            "snippets": [
                {"uri": uri, "span": [10, 20], "answer": "first"},
                {"uri": uri, "span": [40, 50], "answer": "second"},
            ]
        },
    )


@pytest.fixture
def quality(monkeypatch):
    """Replace the judge call and record what it was asked."""
    seen = {}

    async def fake(judge, question, answer, reference, names=("correctness",)):
        seen["reference"] = reference
        return {"correctness": 0.75}

    monkeypatch.setattr(legal_spans, "answer_quality", fake)
    return seen


class TestLegalGrader:
    """Grading one answer."""

    async def test_scores_cited_chunks_and_the_expanded_variant(self, quality):
        """Source chunks of entities add to the expanded score only."""
        answer = SystemAnswer(
            text="a",
            cited_chunks=[CitedChunk("d.txt", 10, 20)],
            non_chunk_citations=1,
            source_chunks=[CitedChunk("d.txt", 40, 50)],
        )

        grade = await LegalGrader().grade(_question(), answer, _Judge())  # type: ignore[arg-type]

        assert grade.scores == {
            "precision": 1.0,
            "recall": 0.5,
            "expanded_precision": 1.0,
            "expanded_recall": 1.0,
            "correctness": 0.75,
            "non_chunk_citation_share": 0.5,
        }
        assert grade.flags == []
        assert quality["reference"] == "first\nsecond"

    async def test_no_chunk_citation_scores_zero_and_is_flagged(self, quality):
        """An answer that cites only entities has zero spans and the flag."""
        answer = SystemAnswer(
            text="a",
            non_chunk_citations=2,
            source_chunks=[CitedChunk("d.txt", 10, 20)],
        )

        grade = await LegalGrader().grade(_question(), answer, _Judge())  # type: ignore[arg-type]

        assert grade.flags == ["no_chunk_citation"]
        assert grade.scores["precision"] == grade.scores["recall"] == 0.0
        assert grade.scores["non_chunk_citation_share"] == 1.0

    async def test_path_match_ignores_unicode_form(self, quality):
        """A decomposed path in a citation matches the composed path in the gold."""
        composed = "café.txt"
        decomposed = unicodedata.normalize("NFD", composed)
        answer = SystemAnswer(text="a", cited_chunks=[CitedChunk(decomposed, 10, 20)])

        grade = await LegalGrader().grade(_question(composed), answer, _Judge())  # type: ignore[arg-type]

        assert grade.scores["recall"] == 0.5

    async def test_a_repeated_citation_counts_once(self, quality):
        """The same chunk cited twice does not double the retrieved length."""
        chunk = CitedChunk("d.txt", 0, 40)
        answer = SystemAnswer(text="a", cited_chunks=[chunk, chunk])

        grade = await LegalGrader().grade(_question(), answer, _Judge())  # type: ignore[arg-type]

        assert grade.scores["precision"] == 0.25
