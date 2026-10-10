"""Tests the FinanceBench dataset: fixtures, PDF documents and grading.

The PDF download and the Docling conversion are patched, so no network and no
model is needed.
"""

from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest
from pydantic import ValidationError

from agrag.common.data_models.document import DocumentFamily, SourceFormat
from agrag.loaders.errors import MissingExtraError
from benchmarks.datasets import financial
from benchmarks.datasets.financial import FinancialAdapter
from benchmarks.grading import financial as grading
from benchmarks.grading.financial import FinancialGrader
from benchmarks.models import BenchmarkQuestion, Corpus, CorpusDocument
from benchmarks.schemas.financial import FINANCIAL
from benchmarks.systems.base import SystemAnswer


class TestFixtures:
    """The committed lite and full fixtures."""

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
        assert lite.corpora[0].documents[0].sha256 == (
            full.corpora[0].documents[0].sha256
        )

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


def _write_pdf(path: Path, widths: list[int]) -> None:
    """Write a blank PDF with one page for each width, so a page has an identity.

    The test is skipped when ``pypdfium2`` is missing. It comes with the docling
    extra, and the other tests of this module do not need it.
    """
    pypdfium2 = pytest.importorskip("pypdfium2")
    with pypdfium2.PdfDocument.new() as pdf:
        for width in widths:
            pdf.new_page(width, 100)
        pdf.save(path)


def _page_widths(path: Path) -> list[int]:
    pypdfium2 = pytest.importorskip("pypdfium2")
    with pypdfium2.PdfDocument(path) as pdf:
        return [round(pdf[i].get_width()) for i in range(len(pdf))]


class TestSelectPages:
    """Cutting chosen pages out of a PDF."""

    def test_writes_the_chosen_pages_in_the_order_given(self, tmp_path):
        """The new PDF holds only the named pages, counted from 0, in that order."""
        source = tmp_path / "source.pdf"
        _write_pdf(source, [100, 200, 300, 400])

        financial.select_pages(source, [2, 0], tmp_path / "chosen.pdf")

        assert _page_widths(tmp_path / "chosen.pdf") == [300, 100]


class TestDocuments:
    """PDFs become prose documents, and the conversion is cached."""

    def _corpus(self, *names: str, pages: list[int] | None = None) -> Corpus:
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
                    pages=pages,
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

    def _patch_pages(self, monkeypatch, tmp_path: Path) -> list[int]:
        """Serve a 4-page PDF and record the width of each page that converts."""
        pytest.importorskip("pypdfium2")
        converted: list[int] = []

        def fetch(url, sha256, dest):
            _write_pdf(dest, [100, 200, 300, 400])
            return dest

        def convert(path, uri):
            (width,) = _page_widths(path)
            converted.append(width)
            return f"page {width}"

        monkeypatch.setattr(financial, "PDF_CACHE", tmp_path)
        monkeypatch.setattr(financial, "fetch_url", fetch)
        monkeypatch.setattr(financial, "convert_pdf", convert)
        return converted

    def test_chosen_pages_convert_one_at_a_time_and_join_in_order(
        self, tmp_path, monkeypatch
    ):
        """Each chosen page converts alone, and the Markdown joins with a blank line."""
        converted = self._patch_pages(monkeypatch, tmp_path)

        (document,) = FinancialAdapter().documents(
            self._corpus("A_2022_10K", pages=[3, 1])
        )

        assert converted == [400, 200]
        assert document.text == "page 400\n\npage 200"

    def test_another_selection_of_the_same_pdf_converts_again(
        self, tmp_path, monkeypatch
    ):
        """Two selections of one PDF never share a cached conversion."""
        converted = self._patch_pages(monkeypatch, tmp_path)

        first = FinancialAdapter().documents(self._corpus("A_2022_10K", pages=[0]))
        second = FinancialAdapter().documents(self._corpus("A_2022_10K", pages=[1]))

        assert converted == [100, 200]
        assert first[0].text != second[0].text

    def test_a_missing_docling_extra_raises_the_missing_extra_error(
        self, tmp_path, monkeypatch
    ):
        """The error names the extra to install instead of the package lookup."""
        self._patch(monkeypatch, tmp_path)

        def not_installed(name):
            raise PackageNotFoundError(name)

        monkeypatch.setattr(financial, "version", not_installed)

        with pytest.raises(MissingExtraError, match="docling"):
            FinancialAdapter().documents(self._corpus("A_2022_10K"))


class _FakeJudge:
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
        """Correctness uses the answer. Context recall adds the evidence text."""
        seen = {}

        async def _fake_answer_quality(
            judge, question, answer, reference, names=("correctness",)
        ):
            seen[names] = reference
            return dict.fromkeys(names, 0.5)

        monkeypatch.setattr(grading, "answer_quality", _fake_answer_quality)

        grade = await FinancialGrader().grade(
            _question(),
            SystemAnswer(text="5,466"),
            _FakeJudge(),  # type: ignore[arg-type]
        )

        assert seen == {
            ("correctness",): "$5466.00",
            ("context_recall",): "$5466.00\nTotal 5,466\nNote 2",
        }
        assert set(grade.scores) == set(FinancialGrader().metrics)
        assert grade.flags == []

    async def test_full_grader_scores_five_metrics_with_the_right_references(
        self, monkeypatch
    ):
        """Full mode adds faithfulness, citation accuracy and context precision."""
        seen = {}

        async def _fake_answer_quality(
            judge, question, answer, reference, names=("correctness",)
        ):
            seen[names] = reference
            return dict.fromkeys(names, 0.5)

        monkeypatch.setattr(grading, "answer_quality", _fake_answer_quality)

        grade = await FinancialGrader(full=True).grade(
            _question(),
            SystemAnswer(text="5,466"),
            _FakeJudge(),  # type: ignore[arg-type]
        )

        assert seen == {
            ("correctness", "faithfulness", "citation_accuracy"): "$5466.00",
            ("context_precision", "context_recall"): "$5466.00\nTotal 5,466\nNote 2",
        }
        assert set(grade.scores) == {
            "correctness",
            "faithfulness",
            "citation_accuracy",
            "context_precision",
            "context_recall",
        }

    def test_domain_uses_the_full_grader_only_in_full_mode(self):
        """Lite scores two metrics and full scores five."""
        assert financial.DOMAIN.grader_for("lite").metrics == (
            "correctness",
            "context_recall",
        )
        assert len(financial.DOMAIN.grader_for("full").metrics) == 5


class TestCorpusDocumentPages:
    """The page selection of a corpus document."""

    @pytest.mark.parametrize("pages", [[], [-1], [2, -3]])
    def test_rejects_an_empty_or_negative_selection(self, pages):
        """A selection must name at least one page, and no page is negative."""
        with pytest.raises(ValidationError):
            CorpusDocument(id="d", uri="d.pdf", sha256="0", source="x", pages=pages)

    @pytest.mark.parametrize("pages", [None, [0], [3, 1]])
    def test_accepts_none_or_page_numbers(self, pages):
        """None selects every page; a list selects those pages."""
        document = CorpusDocument(
            id="d", uri="d.pdf", sha256="0", source="x", pages=pages
        )

        assert document.pages == pages
