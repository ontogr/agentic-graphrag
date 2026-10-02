"""Tests the GraphRAG-Bench dataset: fixtures, documents, schemas and scores.

The document fetch is patched to local files, so no network is needed.
"""

import json
from collections import Counter

import pytest

from agrag.common.data_models.graph_schema import GraphSchema
from benchmarks.datasets import graphrag_general
from benchmarks.datasets.fetch import HashMismatchError
from benchmarks.datasets.graphrag_general import (
    GraphRagAdapter,
    medical_pieces,
    text_sha256,
)
from benchmarks.grading import graphrag_general as grading
from benchmarks.grading.graphrag_accuracy import answer_accuracy, parse_json
from benchmarks.grading.graphrag_general import GraphRagGrader, rouge_l
from benchmarks.models import BenchmarkQuestion, Corpus, CorpusDocument
from benchmarks.schemas.graphrag_general import MEDICAL, NOVEL
from benchmarks.systems.base import SystemAnswer


TYPES = (
    "Fact Retrieval",
    "Complex Reasoning",
    "Contextual Summarize",
    "Creative Generation",
)


class TestFixtures:
    """The committed lite and full fixtures."""

    def test_full_has_250_questions_with_the_planned_mix(self):
        """Full has 130 Medical and 120 Novel questions, by type and by novel."""
        manifest = GraphRagAdapter().load("full")

        by_corpus = Counter(q.corpus_id for q in manifest.questions)
        medical = Counter(
            q.group for q in manifest.questions if q.corpus_id == "medical-full"
        )
        novel = Counter(
            q.group for q in manifest.questions if q.corpus_id.startswith("novel-")
        )

        assert len(manifest.questions) == 250
        assert by_corpus == {
            "medical-full": 130,
            "novel-2544": 32,
            "novel-8559": 33,
            "novel-25646": 28,
            "novel-41603": 27,
        }
        assert medical == dict(zip(TYPES, (69, 32, 18, 11), strict=True))
        assert novel == dict(zip(TYPES, (57, 37, 21, 5), strict=True))

    def test_lite_has_two_questions_on_the_first_medical_extract(self):
        """Lite has a Fact Retrieval and a Complex Reasoning question on one extract."""
        manifest = GraphRagAdapter().load("lite")

        (corpus,) = manifest.corpora

        assert corpus.id == "medical-lite"
        assert [d.id for d in corpus.documents] == ["medical-00"]
        assert corpus.n_tokens == 1_655
        assert {q.group for q in manifest.questions} == {
            "Fact Retrieval",
            "Complex Reasoning",
        }
        assert len(manifest.questions) == 2

    def test_lite_questions_are_a_subset_of_full_with_the_same_content(self):
        """Every lite question is also a full question with the same content."""
        full = {q.id: q for q in GraphRagAdapter().load("full").questions}

        for question in GraphRagAdapter().load("lite").questions:
            other = full[question.id]
            assert other.messages == question.messages
            assert other.reference == question.reference
            assert other.group == question.group

    def test_ids_are_namespaced_by_corpus_file(self):
        """Ids carry their file, because raw ids repeat across the two files."""
        for question in GraphRagAdapter().load("full").questions:
            kind, _, raw = question.id.partition(":")
            assert kind in {"novel", "medical"}
            assert raw.startswith(kind.capitalize() + "-")
            assert question.corpus_id.startswith(kind)

    def test_every_question_holds_a_reference_answer_and_evidence(self):
        """The grader needs an answer, evidence items and the row hash."""
        for question in GraphRagAdapter().load("full").questions:
            reference = question.reference
            assert reference["answer"]
            assert reference["evidence"]
            assert len(reference["row_sha256"]) == 64

    def test_the_lite_medical_document_is_the_first_extract_of_full(self):
        """The lite document is the first of the 44 full documents."""
        lite = {c.id: c for c in GraphRagAdapter().load("lite").corpora}
        full = {c.id: c for c in GraphRagAdapter().load("full").corpora}

        assert lite["medical-lite"].documents == full["medical-full"].documents[:1]
        assert len(full["medical-full"].documents) == 44

    def test_services_are_unique_per_corpus(self):
        """No two corpora share a service, except one corpus used in both modes."""
        services = {}
        for mode in ("lite", "full"):
            for corpus in GraphRagAdapter().load(mode).corpora:
                assert services.setdefault(corpus.service, corpus.id) == corpus.id


class TestDocuments:
    """Document text is cut from the pinned corpus files and checked by hash."""

    def _fetch(self, tmp_path, monkeypatch, records: list[dict]) -> None:
        path = tmp_path / "corpus.json"
        path.write_text(json.dumps(records), encoding="utf-8")
        monkeypatch.setattr(graphrag_general, "fetch_hf_file", lambda *a, **k: path)

    def _medical(self, *pieces: str) -> Corpus:
        return Corpus(
            id="medical-x",
            service="graphrag-medical-lite",
            schema_name=MEDICAL.name,
            documents=[
                CorpusDocument(
                    id=f"medical-{i:02d}",
                    uri=f"medical/{i:02d}",
                    sha256=text_sha256(piece),
                    source="x",
                )
                for i, piece in enumerate(pieces)
            ],
        )

    def test_medical_splits_into_one_document_per_line(self, tmp_path, monkeypatch):
        """A two-extract blob gives two documents, without the closing newline."""
        self._fetch(
            tmp_path,
            monkeypatch,
            [{"corpus_name": "Medical", "context": "About CML 5 text\nAbout ALL 7\n"}],
        )

        documents = GraphRagAdapter().documents(
            self._medical("About CML 5 text", "About ALL 7")
        )

        assert [d.text for d in documents] == ["About CML 5 text", "About ALL 7"]
        assert [d.uri for d in documents] == ["medical/00", "medical/01"]

    def test_a_novel_is_one_document_and_keeps_its_whitespace(
        self, tmp_path, monkeypatch
    ):
        """Leading space and inner runs of spaces stay as they are."""
        text = " Produced by X   (a note)  "
        self._fetch(
            tmp_path,
            monkeypatch,
            [
                {"corpus_name": "Novel-1", "context": "other"},
                {"corpus_name": "Novel-2", "context": text},
            ],
        )
        corpus = Corpus(
            id="novel-2",
            service="graphrag-novel-2544",
            schema_name=NOVEL.name,
            documents=[
                CorpusDocument(
                    id="Novel-2",
                    uri="novel/Novel-2",
                    sha256=text_sha256(text),
                    source="x",
                )
            ],
        )

        (document,) = GraphRagAdapter().documents(corpus)

        assert document.text == text
        assert document.uri == "novel/Novel-2"

    def test_a_changed_extract_fails_the_hash_check(self, tmp_path, monkeypatch):
        """Text that differs from the fixture hash raises."""
        self._fetch(
            tmp_path, monkeypatch, [{"corpus_name": "Medical", "context": "changed\n"}]
        )

        with pytest.raises(HashMismatchError):
            GraphRagAdapter().documents(self._medical("original"))

    def test_medical_pieces_drop_only_the_closing_empty_line(self):
        """The blob ends with a newline, which is no extract."""
        assert medical_pieces("a\nb\n") == ["a", "b"]
        assert medical_pieces("a\nb") == ["a", "b"]


class TestSchemas:
    """The two graph schemas."""

    @pytest.mark.parametrize(
        ("schema", "entities", "relations"), [(NOVEL, 9, 14), (MEDICAL, 13, 16)]
    )
    def test_schema_has_the_planned_size_and_survives_a_round_trip(
        self, schema, entities, relations
    ):
        """Each schema has its planned size and describes every entity."""
        assert len(schema.entities) == entities
        assert len(schema.relations) == relations
        assert all("description" in e.properties for e in schema.entities)
        assert GraphSchema.model_validate(schema.model_dump(mode="json")) == schema

    def test_each_corpus_gets_its_own_schema(self):
        """Novel corpora use the general schema and Medical uses the oncology one."""
        adapter = GraphRagAdapter()
        corpora = {
            c.id: c for mode in ("lite", "full") for c in adapter.load(mode).corpora
        }

        assert adapter.schema(corpora["novel-25646"]) is NOVEL
        assert adapter.schema(corpora["medical-lite"]) is MEDICAL


class TestRougeL:
    """ROUGE-L F-measure on fixed strings."""

    def test_identical_text_scores_one(self):
        """The same text is a perfect match."""
        assert rouge_l("the cat sat", "the cat sat") == 1.0

    def test_no_shared_word_scores_zero(self):
        """Text with no shared word scores 0."""
        assert rouge_l("alpha beta", "gamma delta") == 0.0

    def test_partial_overlap_is_the_f_measure_of_the_longest_common_subsequence(self):
        """Five of six words are in order in both texts, so F is 5/6."""
        score = rouge_l("the cat sat on the mat", "the cat lay on the mat")

        assert score == pytest.approx(5 / 6)

    @pytest.mark.parametrize(("answer", "reference"), [("", "x"), ("x", "  ")])
    def test_a_blank_side_scores_zero(self, answer, reference):
        """A blank answer or reference scores 0 instead of raising."""
        assert rouge_l(answer, reference) == 0.0


class _FakeJudge:
    """Answers the two prompts of the accuracy metric from canned replies."""

    def __init__(self, statements: dict[str, str], classification: str) -> None:
        self.statements = statements
        self.classification = classification

    async def a_generate(self, prompt: str, schema=None) -> str:
        if "Current Analysis" in prompt:
            return self.classification
        text = prompt.split("Input Text:\n", 1)[1].split("\n\nGenerated", 1)[0]
        return self.statements[text]


class _FakeEmbedder:
    """Returns fixed vectors, in the order of the texts."""

    def __init__(self, *vectors: list[float]) -> None:
        self.vectors = list(vectors)

    async def embed(self, texts):
        return self.vectors


def _classes(tp: int, fp: int, fn: int) -> str:
    """Return a judge classification reply with the given class sizes."""
    item = {"statement": "s", "reason": "r"}
    return json.dumps({"TP": [item] * tp, "FP": [item] * fp, "FN": [item] * fn})


class TestAnswerAccuracy:
    """The ported accuracy metric on canned judge replies."""

    async def test_adds_the_weighted_statement_f1_and_embedding_similarity(self):
        """F1 is 0.5 for 1 TP, 1 FP, 1 FN. Equal vectors give similarity 1."""
        judge = _FakeJudge(
            {"ans": '["a", "b"]', "gold": '["a", "c"]'}, _classes(1, 1, 1)
        )

        score, failed = await answer_accuracy(
            judge, _FakeEmbedder([1.0, 0.0], [1.0, 0.0]), "q?", "ans", "gold"
        )

        assert score == pytest.approx(0.75 * 0.5 + 0.25 * 1.0)
        assert failed is False

    async def test_orthogonal_embeddings_give_similarity_one_half(self):
        """Cosine 0 scales to 0.5."""
        judge = _FakeJudge(
            {"ans": '["a"]', "gold": '["a"]'},
            _classes(1, 0, 0),
        )

        score, _ = await answer_accuracy(
            judge, _FakeEmbedder([1.0, 0.0], [0.0, 1.0]), "q?", "ans", "gold"
        )

        assert score == pytest.approx(0.75 * 1.0 + 0.25 * 0.5)

    async def test_a_fenced_reply_is_parsed(self):
        """A reply inside a code fence counts as its JSON."""
        judge = _FakeJudge(
            {"ans": '```json\n["a"]\n```', "gold": '["a"]'},
            f"```json\n{_classes(1, 0, 0)}\n```",
        )

        score, failed = await answer_accuracy(
            judge, _FakeEmbedder([1.0], [1.0]), "q?", "ans", "gold"
        )

        assert score == pytest.approx(1.0)
        assert failed is False

    async def test_a_reply_that_is_not_json_scores_no_statements_and_is_flagged(self):
        """Prose in place of JSON takes the scorer's fallback and sets the flag."""
        judge = _FakeJudge({"ans": "I cannot", "gold": '["a"]'}, "not json")

        score, failed = await answer_accuracy(
            judge, _FakeEmbedder([1.0], [1.0]), "q?", "ans", "gold"
        )

        assert score == pytest.approx(0.25)
        assert failed is True

    async def test_unparsed_statements_score_factuality_zero_and_are_flagged(self):
        """A statement reply that is not a list gets no credit for factuality."""
        judge = _FakeJudge({"ans": "oops", "gold": "oops"}, _classes(1, 0, 0))

        score, failed = await answer_accuracy(
            judge, _FakeEmbedder([1.0], [1.0]), "q?", "ans", "gold"
        )

        assert score == pytest.approx(0.25)
        assert failed is True

    async def test_a_classification_missing_a_class_is_flagged(self):
        """A reply that lists only TP is incomplete, not a perfect match."""
        judge = _FakeJudge({"ans": '["a"]', "gold": '["a"]'}, '{"TP": []}')

        score, failed = await answer_accuracy(
            judge, _FakeEmbedder([1.0], [1.0]), "q?", "ans", "gold"
        )

        assert score == pytest.approx(0.25)
        assert failed is True

    async def test_no_statements_on_either_side_scores_factuality_one(self):
        """Two empty statement lists are a perfect match, as in the scorer."""
        judge = _FakeJudge({"ans": "[]", "gold": "[]"}, "unused")

        score, failed = await answer_accuracy(
            judge, _FakeEmbedder([1.0], [1.0]), "q?", "ans", "gold"
        )

        assert score == pytest.approx(1.0)
        assert failed is False

    def test_parse_json_strips_a_code_fence(self):
        """The fence and its language tag are removed before the parse."""
        assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def _question() -> BenchmarkQuestion:
    return BenchmarkQuestion(
        id="novel:Novel-1",
        corpus_id="novel-1",
        messages=[{"role": "user", "content": "Why?"}],
        group="Fact Retrieval",
        reference={"answer": "gold answer", "evidence": ["one", "two"]},
    )


class TestGraphRagGrader:
    """Grading one answer."""

    async def test_full_scores_every_metric_and_splits_the_references(
        self, monkeypatch
    ):
        """Quality uses the gold answer, context recall uses the evidence items."""
        seen = {}

        async def fake(judge, question, answer, reference, names=("correctness",)):
            seen[names] = reference
            return dict.fromkeys(names, 0.5)

        monkeypatch.setattr(grading, "answer_quality", fake)
        judge = _FakeJudge(
            {"gold answer": '["a"]'},
            _classes(1, 0, 0),
        )
        grader = GraphRagGrader(
            embedder=_FakeEmbedder([1.0], [1.0]),  # type: ignore[arg-type]
            full=True,
        )

        grade = await grader.grade(
            _question(),
            SystemAnswer(text="gold answer"),
            judge,  # type: ignore[arg-type]
        )

        assert seen == {
            ("correctness", "faithfulness"): "gold answer",
            ("context_recall",): "one\ntwo",
        }
        assert set(grade.scores) == set(grader.metrics)
        assert len(grader.metrics) == 5
        assert grader.judge_calls_per_question == 10
        assert grade.scores["rouge_l"] == 1.0
        assert grade.scores["official_accuracy"] == pytest.approx(1.0)
        assert grade.flags == []

    async def test_lite_scores_three_metrics_and_skips_the_evidence_judge(
        self, monkeypatch
    ):
        """Lite judges correctness and accuracy only, so recall is never asked."""
        seen = {}

        async def fake(judge, question, answer, reference, names=("correctness",)):
            seen[names] = reference
            return dict.fromkeys(names, 0.5)

        monkeypatch.setattr(grading, "answer_quality", fake)
        judge = _FakeJudge({"gold answer": '["a"]'}, _classes(1, 0, 0))
        grader = GraphRagGrader(embedder=_FakeEmbedder([1.0], [1.0]))  # type: ignore[arg-type]

        grade = await grader.grade(
            _question(),
            SystemAnswer(text="gold answer"),
            judge,  # type: ignore[arg-type]
        )

        assert seen == {("correctness",): "gold answer"}
        assert set(grade.scores) == {"correctness", "rouge_l", "official_accuracy"}
        assert set(grade.scores) == set(grader.metrics)
        assert grader.judge_calls_per_question == 4

    async def test_a_judge_parse_failure_sets_the_flag(self, monkeypatch):
        """A judge reply that is not JSON shows as a flag on the question."""

        async def fake(judge, question, answer, reference, names=("correctness",)):
            return dict.fromkeys(names, 1.0)

        monkeypatch.setattr(grading, "answer_quality", fake)
        judge = _FakeJudge({"gold answer": "oops"}, "oops")
        grader = GraphRagGrader(embedder=_FakeEmbedder([1.0], [1.0]))  # type: ignore[arg-type]

        grade = await grader.grade(
            _question(),
            SystemAnswer(text="gold answer"),
            judge,  # type: ignore[arg-type]
        )

        assert grade.flags == ["parse_error"]
