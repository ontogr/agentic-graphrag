"""Tests the FinanceBench dataset: fixtures, PDF documents, schema and grading.

The PDF download and the Docling conversion are patched, so no network and no
model is needed.
"""

from collections import Counter
from pathlib import Path

from agrag.common.data_models.document import DocumentFamily, SourceFormat
from agrag.common.data_models.graph_schema import GraphSchema
from benchmarks.datasets import financial
from benchmarks.datasets.financial import COMMIT, FinancialAdapter
from benchmarks.grading import financial as grading
from benchmarks.grading.financial import FinancialGrader
from benchmarks.models import BenchmarkQuestion, Corpus, CorpusDocument
from benchmarks.schemas.financial import FINANCIAL
from benchmarks.systems.base import SystemAnswer


class TestFixtures:
    """The committed lite and full fixtures."""

    def test_full_has_53_questions_on_18_documents_with_the_planned_mix(self):
        """Full has 53 questions, 18 documents and the three question types."""
        manifest = FinancialAdapter().load("full")

        groups = Counter(q.group for q in manifest.questions)

        assert len(manifest.questions) == 53
        assert len(manifest.corpora) == 1
        assert len(manifest.corpora[0].documents) == 18
        assert manifest.corpora[0].n_tokens == 783_071
        assert groups == {
            "domain-relevant": 17,
            "novel-generated": 33,
            "metrics-generated": 3,
        }

    def test_lite_has_10_questions_on_3_filings_and_all_question_types(self):
        """Lite has 10 questions on Boeing, Amazon and Netflix 10-Ks."""
        manifest = FinancialAdapter().load("lite")

        groups = Counter(q.group for q in manifest.questions)

        assert len(manifest.questions) == 10
        assert [d.id for d in manifest.corpora[0].documents] == [
            "BOEING_2022_10K",
            "AMAZON_2017_10K",
            "NETFLIX_2017_10K",
        ]
        assert manifest.corpora[0].n_tokens == 239_544
        assert groups == {
            "domain-relevant": 4,
            "novel-generated": 3,
            "metrics-generated": 3,
        }

    def test_lite_is_a_subset_of_full_with_the_same_content(self):
        """Every lite question and document is also in full, with the same content."""
        full = FinancialAdapter().load("full")
        lite = FinancialAdapter().load("lite")
        questions = {q.id: q for q in full.questions}

        for question in lite.questions:
            other = questions[question.id]
            assert other.messages == question.messages
            assert other.reference == question.reference
            assert other.group == question.group
        assert full.corpora[0].documents[:3] == lite.corpora[0].documents

    def test_every_question_points_at_a_corpus_document_and_holds_evidence(self):
        """A question names its own document, and each evidence item has a page."""
        for mode in ("lite", "full"):
            manifest = FinancialAdapter().load(mode)
            documents = {d.id for d in manifest.corpora[0].documents}
            for question in manifest.questions:
                reference = question.reference
                assert reference["doc_name"] in documents
                assert reference["answer"]
                assert reference["evidence"]
                assert all(e["text"] and e["page"] >= 0 for e in reference["evidence"])
                assert len(reference["row_sha256"]) == 64

    def test_each_pdf_is_pinned_by_hash_to_the_benchmark_commit(self):
        """Every document has a SHA-256 and a URL at the pinned commit."""
        manifest = FinancialAdapter().load("full")

        for document in manifest.corpora[0].documents:
            assert len(document.sha256) == 64
            assert f"/{COMMIT}/pdfs/{document.id}.pdf" in document.source
            assert document.uri == f"{document.id}.pdf"
        assert len(manifest.upstream["commit"]) == 40

    def test_services_do_not_share_a_graph_across_modes(self):
        """Lite and full use their own services."""
        lite = FinancialAdapter().load("lite").corpora[0]
        full = FinancialAdapter().load("full").corpora[0]

        assert {lite.service, full.service} == {"financial-lite", "financial-full"}


class TestDocuments:
    """PDFs become prose documents, and the conversion is cached."""

    def _corpus(self, *names: str) -> Corpus:
        return Corpus(
            id="financial-lite",
            service="financial-lite",
            schema_name=FINANCIAL.name,
            documents=[
                CorpusDocument(
                    id=name,
                    uri=f"{name}.pdf",
                    sha256=f"{i:064d}",
                    source=f"https://example.test/{name}.pdf",
                )
                for i, name in enumerate(names)
            ],
        )

    def _patch(self, monkeypatch, tmp_path: Path) -> list[str]:
        converted: list[str] = []

        def fetch(url, sha256, dest):
            dest.write_bytes(b"%PDF fake")
            return dest

        def convert(path, uri):
            converted.append(uri)
            return f"# {uri}\n\nPage one.\n\nPage two."

        monkeypatch.setattr(financial, "PDF_CACHE", tmp_path)
        monkeypatch.setattr(financial, "fetch_url", fetch)
        monkeypatch.setattr(financial, "convert_pdf", convert)
        return converted

    def test_each_pdf_is_one_pdf_prose_document_with_the_pdf_hash(
        self, tmp_path, monkeypatch
    ):
        """The document holds the conversion and the hash of the PDF bytes."""
        self._patch(monkeypatch, tmp_path)

        documents = FinancialAdapter().documents(
            self._corpus("A_2022_10K", "B_2017_10K")
        )

        assert [d.uri for d in documents] == ["A_2022_10K.pdf", "B_2017_10K.pdf"]
        assert documents[0].text.startswith("# A_2022_10K.pdf")
        assert documents[0].source_format is SourceFormat.PDF
        assert documents[0].family is DocumentFamily.PROSE
        assert documents[0].content_hash == f"{0:064d}"
        assert documents[0].loader_name == "docling"

    def test_a_second_call_reuses_the_cached_conversion(self, tmp_path, monkeypatch):
        """Docling runs once per PDF, however often the documents are built."""
        converted = self._patch(monkeypatch, tmp_path)
        corpus = self._corpus("A_2022_10K")

        first = FinancialAdapter().documents(corpus)
        second = FinancialAdapter().documents(corpus)

        assert converted == ["A_2022_10K.pdf"]
        assert first[0].text == second[0].text


class TestSchema:
    """The financial graph schema."""

    def test_schema_has_the_planned_size_and_survives_a_round_trip(self):
        """The schema has 13 entity types and 22 relation types."""
        assert len(FINANCIAL.entities) == 13
        assert len(FINANCIAL.relations) == 22
        assert (
            GraphSchema.model_validate(FINANCIAL.model_dump(mode="json")) == FINANCIAL
        )

    def test_adapter_returns_the_schema(self):
        """The adapter returns the financial schema for its corpus."""
        corpus = FinancialAdapter().load("lite").corpora[0]

        assert FinancialAdapter().schema(corpus) is FINANCIAL


class _Judge:
    """Stands in for the judge; the patched quality function ignores it."""


def _question() -> BenchmarkQuestion:
    return BenchmarkQuestion(
        id="financebench_id_1",
        corpus_id="financial-lite",
        messages=[{"role": "user", "content": "What was revenue?"}],
        group="domain-relevant",
        reference={
            "answer": "$5466.00",
            "evidence": [
                {"text": "Total 5,466", "page": 3},
                {"text": "Note 2", "page": 9},
            ],
        },
    )


class TestFinancialGrader:
    """Grading one answer."""

    async def test_judges_the_answer_and_the_evidence_with_their_own_references(
        self, monkeypatch
    ):
        """Quality uses the answer. Context metrics add the evidence text."""
        seen = {}

        async def fake(judge, question, answer, reference, names=("correctness",)):
            seen[names] = reference
            return dict.fromkeys(names, 0.5)

        monkeypatch.setattr(grading, "answer_quality", fake)

        grade = await FinancialGrader().grade(
            _question(),
            SystemAnswer(text="5,466"),
            _Judge(),  # type: ignore[arg-type]
        )

        assert seen == {
            ("correctness", "faithfulness", "citation_accuracy"): "$5466.00",
            ("context_precision", "context_recall"): "$5466.00\nTotal 5,466\nNote 2",
        }
        assert set(grade.scores) == set(FinancialGrader.metrics)
        assert grade.flags == []
