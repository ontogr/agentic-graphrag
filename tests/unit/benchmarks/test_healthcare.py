"""Tests the Healthcare dataset: fixtures, passages, search rule, schema and grader.

The passage fetch is patched to local files, so no network is needed.
"""

import collections
import json
import re
import sqlite3
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from agrag.common.data_models.graph_schema import GraphSchema
from benchmarks.datasets import healthcare
from benchmarks.datasets.fetch import HashMismatchError
from benchmarks.datasets.healthcare import (
    SOURCES,
    HealthcareAdapter,
    iter_rows,
    passage_reference,
    passage_sha256,
)
from benchmarks.datasets.healthcare_index import (
    check_manifest,
    closure,
    fts_query,
)
from benchmarks.grading.healthbench import (
    ATTEMPTS,
    HealthBenchGrader,
    calculate_score,
    parse_json_to_dict,
    rubric_text,
)
from benchmarks.models import (
    BenchmarkQuestion,
    Corpus,
    CorpusDocument,
    CorpusManifest,
)
from benchmarks.schemas.healthcare import HEALTHCARE
from benchmarks.systems.base import SystemAnswer


THEMES = {
    "global_health": 42,
    "context_seeking": 27,
    "hedging": 25,
    "health_data_tasks": 17,
    "communication": 17,
    "complex_responses": 12,
    "emergency_referrals": 10,
}


class TestFixtures:
    """The committed lite and full fixtures."""

    def test_full_has_150_questions_with_the_planned_theme_mix(self):
        """Full has 150 questions, split by theme as planned."""
        manifest = HealthcareAdapter().load("full")

        themes = collections.Counter(q.group for q in manifest.questions)

        assert len(manifest.questions) == 150
        assert themes == THEMES

    def test_lite_has_one_question_and_three_passages(self):
        """Lite has one question and the three passages that state its facts."""
        manifest = HealthcareAdapter().load("lite")

        assert len(manifest.questions) == 1
        assert [d.id for d in manifest.corpora[0].documents] == [
            "article-30719_98",
            "article-30719_101",
            "article-30720_46",
        ]

    def test_the_lite_judge_estimate_is_the_rubric_items_of_the_question(self):
        """Lite costs one judge call for each rubric item of its question."""
        (question,) = HealthcareAdapter().load("lite").questions

        grader = healthcare.DOMAIN.grader_for("lite")

        assert grader.judge_calls_per_question == len(question.reference["rubrics"])
        assert healthcare.DOMAIN.grader_for("full").judge_calls_per_question == 11

    def test_full_closure_has_4477_passages(self):
        """Full keeps the 4,477 passages that its questions find."""
        assert len(HealthcareAdapter().load("full").corpora[0].documents) == 4477

    def test_lite_questions_and_passages_are_subsets_of_full(self):
        """Every lite question and passage is also in full, with the same content."""
        lite = HealthcareAdapter().load("lite")
        full = HealthcareAdapter().load("full")
        questions = {q.id: q for q in full.questions}
        passages = {d.id: d for d in full.corpora[0].documents}

        for question in lite.questions:
            other = questions[question.id]
            assert other.messages == question.messages
            assert other.reference == question.reference
            assert other.group == question.group
        for document in lite.corpora[0].documents:
            assert passages[document.id] == document

    def test_every_question_can_be_graded(self):
        """Each question ends on a user turn and has a positive rubric item."""
        for question in HealthcareAdapter().load("full").questions:
            assert {m["role"] for m in question.messages} <= {"user", "assistant"}
            assert question.messages[-1]["role"] == "user"
            rubrics = question.reference["rubrics"]
            assert any(item["points"] > 0 for item in rubrics)
            assert all(item["criterion"] for item in rubrics)
            assert len(question.reference["row_sha256"]) == 64

    def test_multi_turn_questions_keep_every_turn(self):
        """Full has multi-turn conversations and they are kept whole."""
        full = HealthcareAdapter().load("full")

        turns = collections.Counter(len(q.messages) for q in full.questions)

        assert turns == {1: 120, 3: 20, 5: 6, 7: 3, 13: 1}

    def test_passages_are_pinned_by_unique_id_and_hash(self):
        """Each passage has a unique id, a SHA-256 and an address in a pinned file."""
        documents = HealthcareAdapter().load("full").corpora[0].documents
        pattern = re.compile(
            r"^hf://datasets/(?P<repo>[^@]+)@(?P<revision>[0-9a-f]{40})/"
            r"(?P<file>.+)#\d+$"
        )

        assert len({d.id for d in documents}) == len(documents)
        files = {
            (pin["repo"], pin["revision"], file)
            for pin in SOURCES.values()
            for file in pin["files"]
        }
        for document in documents:
            match = pattern.match(document.source)
            assert match is not None
            assert (match["repo"], match["revision"], match["file"]) in files
            assert len(document.sha256) == 64
            assert document.uri == document.id

    def test_the_fixture_names_its_pinned_sources(self):
        """The upstream entry holds the pinned revisions and file hashes."""
        upstream = HealthcareAdapter().load("lite").upstream

        assert upstream["sources"] == SOURCES
        assert all(len(pin["revision"]) == 40 for pin in SOURCES.values())
        assert upstream["closure_passages_per_question"] == {"full": 32}


def _textbook(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "book.jsonl"
    path.write_bytes(b"".join(json.dumps(row).encode() + b"\n" for row in rows))
    return path


def _statpearls(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "train.parquet"
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


class TestPassages:
    """Passage text is read from the pinned files and checked by hash."""

    def _corpus(self, rows: dict[str, tuple[str, str, int, str]]) -> Corpus:
        return Corpus(
            id="healthcare-x",
            service="healthcare-lite",
            schema_name=HEALTHCARE.name,
            documents=[
                CorpusDocument(
                    id=passage_id,
                    uri=passage_id,
                    sha256=passage_sha256(contents),
                    source=passage_reference(source, file, row),
                )
                for passage_id, (source, file, row, contents) in rows.items()
            ],
        )

    def _fetch(self, monkeypatch, files: dict[str, Path]) -> None:
        monkeypatch.setattr(
            healthcare, "fetch_source_file", lambda source, file: files[file]
        )

    def test_reads_the_addressed_row_of_each_source_file(self, tmp_path, monkeypatch):
        """A textbook row and a StatPearls row become documents with their text."""
        book = _textbook(
            tmp_path,
            [{"id": f"B_{i}", "contents": f"Title {i}. Text {i}"} for i in range(3)],
        )
        pearls = _statpearls(
            tmp_path,
            [
                {"id": f"article-{i}_1", "contents": f"Pearl {i}. Text"}
                for i in range(4)
            ],
        )
        file_book = next(iter(SOURCES["textbooks"]["files"]))
        file_pearls = next(iter(SOURCES["statpearls"]["files"]))
        self._fetch(monkeypatch, {file_book: book, file_pearls: pearls})
        corpus = self._corpus(
            {
                "B_2": ("textbooks", file_book, 2, "Title 2. Text 2"),
                "article-3_1": ("statpearls", file_pearls, 3, "Pearl 3. Text"),
            }
        )

        documents = HealthcareAdapter().documents(corpus)

        assert [d.text for d in documents] == ["Title 2. Text 2", "Pearl 3. Text"]
        assert [d.uri for d in documents] == ["B_2", "article-3_1"]

    def test_a_changed_passage_fails_the_hash_check(self, tmp_path, monkeypatch):
        """Text that differs from the pinned hash raises."""
        file_book = next(iter(SOURCES["textbooks"]["files"]))
        book = _textbook(tmp_path, [{"id": "B_0", "contents": "changed"}])
        self._fetch(monkeypatch, {file_book: book})
        corpus = self._corpus({"B_0": ("textbooks", file_book, 0, "original")})

        with pytest.raises(HashMismatchError):
            HealthcareAdapter().documents(corpus)

    def test_a_row_with_another_id_fails(self, tmp_path, monkeypatch):
        """A row whose id is not the pinned id raises, even if the text matches."""
        file_book = next(iter(SOURCES["textbooks"]["files"]))
        book = _textbook(tmp_path, [{"id": "B_9", "contents": "same"}])
        self._fetch(monkeypatch, {file_book: book})
        corpus = self._corpus({"B_0": ("textbooks", file_book, 0, "same")})

        with pytest.raises(HashMismatchError):
            HealthcareAdapter().documents(corpus)

    def test_a_missing_row_fails(self, tmp_path, monkeypatch):
        """A row past the end of the file raises."""
        file_book = next(iter(SOURCES["textbooks"]["files"]))
        book = _textbook(tmp_path, [{"id": "B_0", "contents": "x"}])
        self._fetch(monkeypatch, {file_book: book})
        corpus = self._corpus({"B_5": ("textbooks", file_book, 5, "x")})

        with pytest.raises(HashMismatchError):
            HealthcareAdapter().documents(corpus)

    def test_a_line_separator_inside_a_passage_does_not_split_a_row(self, tmp_path):
        """Only a line feed ends a JSONL row, so U+2028 stays in the text."""
        path = tmp_path / "book.jsonl"
        path.write_bytes(
            json.dumps({"id": "B_0", "contents": "a b"}, ensure_ascii=False).encode()
            + b"\n"
        )

        assert list(iter_rows(path)) == [(0, "B_0", "a b")]


class TestSearch:
    """The search rule that selects the passages of a question."""

    def test_the_query_quotes_distinct_content_words(self):
        """Punctuation, stop words, short words and repeats drop out."""
        query = fts_query(
            "Hi! What is the dose of ibuprofen (ibuprofen) for a 5-year-old?"
        )

        assert query == '"dose" OR "ibuprofen" OR "5-year-old"'

    def test_the_query_keeps_at_most_forty_terms(self):
        """A long prompt gives 40 terms."""
        text = " ".join(f"term{i}x" for i in range(100))

        assert fts_query(text).count(" OR ") == 39

    def test_a_turn_of_stop_words_gives_an_empty_query(self):
        """A turn with no content word has no query."""
        assert fts_query("What is this? Tell me.") == ""

    def _db(self) -> sqlite3.Connection:
        db = sqlite3.connect(":memory:")
        db.execute(
            "CREATE VIRTUAL TABLE docs USING fts5("
            "doc_id UNINDEXED, source UNINDEXED, contents, tokenize='porter unicode61')"
        )
        db.executemany(
            "INSERT INTO docs VALUES (?,?,?)",
            [
                ("a", "t", "asthma inhaler asthma dose"),
                ("b", "t", "asthma"),
                ("c", "t", "kidney stone pain"),
            ],
        )
        return db

    def test_closure_returns_the_best_passages_first_up_to_k(self):
        """The passage that matches most comes first, and k limits the list."""
        db = self._db()

        assert closure(db, "asthma inhaler dose", 1) == ["a"]
        assert closure(db, "asthma inhaler dose", 5) == ["a", "b"]

    def test_closure_of_a_turn_without_content_words_is_empty(self):
        """An empty query finds nothing."""
        assert closure(self._db(), "what is this", 5) == []

    def test_check_manifest_reports_missing_and_extra_passages(self):
        """A corpus that is not the union of the closures is reported."""
        db = self._db()
        question = BenchmarkQuestion(
            id="q",
            corpus_id="c",
            messages=[{"role": "user", "content": "asthma inhaler dose"}],
            group="g",
        )

        def manifest(ids: list[str]) -> CorpusManifest:
            docs = [CorpusDocument(id=i, uri=i, sha256="0", source="x") for i in ids]
            corpus = Corpus(
                id="c", service="s", schema_name="healthcare", documents=docs
            )
            return CorpusManifest(
                name="n",
                domain="healthcare",
                mode="lite",
                corpora=[corpus],
                questions=[question],
            )

        assert check_manifest(db, manifest(["a", "b"]), 5) == []
        assert check_manifest(db, manifest(["a"]), 5, subset=True) == []
        assert check_manifest(db, manifest(["a", "z"]), 5, subset=True) == [
            "1 passages are not in any closure"
        ]
        assert check_manifest(db, manifest(["a", "z"]), 5) == [
            "1 passages are missing",
            "1 passages are not in any closure",
        ]


class TestSchema:
    """The healthcare graph schema."""

    def test_schema_has_the_planned_size_and_survives_a_round_trip(self):
        """The schema has 11 entity types and 18 relations, each with a description."""
        assert len(HEALTHCARE.entities) == 11
        assert len(HEALTHCARE.relations) == 18
        assert all("description" in e.properties for e in HEALTHCARE.entities)
        rebuilt = GraphSchema.model_validate(HEALTHCARE.model_dump(mode="json"))
        assert rebuilt == HEALTHCARE

    def test_adapter_returns_the_schema(self):
        """The adapter returns the healthcare schema for its corpus."""
        corpus = HealthcareAdapter().load("lite").corpora[0]

        assert HealthcareAdapter().schema(corpus) is HEALTHCARE


RUBRICS = [
    {"criterion": "Names the drug", "points": 5},
    {"criterion": "Gives the dose", "points": 5},
    {"criterion": "Invents a side effect", "points": -4},
]


class TestScoring:
    """The score of a question and the reading of judge replies."""

    def test_met_points_divide_by_the_positive_points(self):
        """One of two positive items met, and no negative item met, scores 0.5."""
        assert calculate_score(RUBRICS, [True, False, False]) == 0.5

    def test_a_met_negative_item_lowers_the_score(self):
        """A met negative item subtracts its points, and the score can be below 0."""
        assert calculate_score(RUBRICS, [True, True, True]) == pytest.approx(0.6)
        assert calculate_score(RUBRICS, [False, False, True]) == pytest.approx(-0.4)

    def test_a_rubric_without_positive_points_has_no_score(self):
        """A zero denominator gives None and not a division error."""
        assert calculate_score([{"criterion": "x", "points": -2}], [True]) is None

    def test_the_prompt_shows_points_and_criterion(self):
        """An item reads as ``[points] criterion``."""
        assert rubric_text(RUBRICS[2]) == "[-4] Invents a side effect"

    @pytest.mark.parametrize(
        ("reply", "expected"),
        [
            ('```json\n{"criteria_met": true}\n```', {"criteria_met": True}),
            ('```\n{"criteria_met": false}\n```', {"criteria_met": False}),
            ('{"criteria_met": true}', {"criteria_met": True}),
            ("no json here", {}),
            ("[1, 2]", {}),
        ],
    )
    def test_parse_reads_a_fenced_object_and_rejects_the_rest(self, reply, expected):
        """A fence is removed, and anything that is not an object gives {}."""
        assert parse_json_to_dict(reply) == expected


class _Judge:
    """Answers each rubric prompt from a queue of replies for its criterion."""

    def __init__(self, replies: dict[str, list[str]]) -> None:
        self.replies = replies
        self.prompts: list[str] = []

    async def a_generate(self, prompt: str, schema=None) -> str:
        self.prompts.append(prompt)
        rubric = prompt.split("# Rubric item\n", 1)[1].split("\n\n# Instructions", 1)[0]
        criterion = rubric.split("] ", 1)[1]
        return self.replies[criterion].pop(0)


def _verdict(met: bool) -> str:
    return json.dumps({"explanation": "x", "criteria_met": met})


def _question(rubrics=RUBRICS) -> BenchmarkQuestion:
    return BenchmarkQuestion(
        id="q",
        corpus_id="c",
        messages=[
            {"role": "user", "content": "What is the dose?"},
            {"role": "assistant", "content": "Which drug?"},
            {"role": "user", "content": "Ibuprofen."},
        ],
        group="hedging",
        reference={"rubrics": rubrics},
    )


class TestHealthBenchGrader:
    """Grading one answer against its rubric."""

    async def test_scores_the_met_items_and_reads_fenced_replies(self):
        """The judge is asked once for each item, and verdicts set the score."""
        judge = _Judge(
            {
                "Names the drug": [f"```json\n{_verdict(True)}\n```"],
                "Gives the dose": [_verdict(False)],
                "Invents a side effect": [_verdict(False)],
            }
        )

        grade = await HealthBenchGrader().grade(
            _question(),
            SystemAnswer(text="Take ibuprofen."),
            judge,  # type: ignore[arg-type]
        )

        assert grade.scores == {"score": 0.5}
        assert grade.flags == []
        assert len(judge.prompts) == 3

    async def test_the_judge_sees_every_turn_and_the_answer(self):
        """The conversation in the prompt holds all turns, then the answer."""
        judge = _Judge({c["criterion"]: [_verdict(False)] for c in RUBRICS})

        await HealthBenchGrader().grade(
            _question(),
            SystemAnswer(text="Take ibuprofen."),
            judge,  # type: ignore[arg-type]
        )

        assert (
            "user: What is the dose?\n\nassistant: Which drug?\n\n"
            "user: Ibuprofen.\n\nassistant: Take ibuprofen."
        ) in judge.prompts[0]

    async def test_a_bad_reply_is_asked_again_then_counts_as_not_met_and_is_flagged(
        self,
    ):
        """After three bad replies the item is not met and the question is flagged."""
        judge = _Judge(
            {
                "Names the drug": ["oops"] * ATTEMPTS,
                "Gives the dose": [_verdict(True)],
                "Invents a side effect": [_verdict(False)],
            }
        )

        grade = await HealthBenchGrader().grade(
            _question(),
            SystemAnswer(text="a"),
            judge,  # type: ignore[arg-type]
        )

        assert grade.scores == {"score": 0.5}
        assert grade.flags == ["parse_error"]

    async def test_a_reply_that_is_valid_on_the_second_try_needs_no_flag(self):
        """A retry that succeeds leaves the question unflagged."""
        judge = _Judge(
            {
                "Names the drug": ["oops", _verdict(True)],
                "Gives the dose": [_verdict(True)],
                "Invents a side effect": [_verdict(False)],
            }
        )

        grade = await HealthBenchGrader().grade(
            _question(),
            SystemAnswer(text="a"),
            judge,  # type: ignore[arg-type]
        )

        assert grade.scores == {"score": 1.0}
        assert grade.flags == []

    async def test_a_question_without_positive_items_scores_zero_and_is_flagged(self):
        """A zero denominator gives score 0 and the flag."""
        rubrics = [{"criterion": "Invents a side effect", "points": -4}]
        judge = _Judge({"Invents a side effect": [_verdict(True)]})

        grade = await HealthBenchGrader().grade(
            _question(rubrics),
            SystemAnswer(text="a"),
            judge,  # type: ignore[arg-type]
        )

        assert grade.scores == {"score": 0.0}
        assert grade.flags == ["no_positive_points"]
