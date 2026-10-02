"""Tests the BEAM dataset: fixtures, session documents, collapse and schema.

The file fetch is patched to in-memory rows, so no network is needed.
"""

import hashlib

import pytest

from agrag.common.data_models.graph_schema import GraphSchema
from benchmarks.datasets import memory
from benchmarks.datasets.fetch import HashMismatchError
from benchmarks.datasets.memory import (
    MemoryAdapter,
    RunawayMessage,
    collapse_runaway,
    probes,
    session_document_text,
    session_text,
    text_sha256,
)
from benchmarks.models import Corpus, CorpusDocument
from benchmarks.schemas.memory import MEMORY


ABILITIES = {
    "abstention",
    "contradiction_resolution",
    "event_ordering",
    "information_extraction",
    "instruction_following",
    "knowledge_update",
    "multi_session_reasoning",
    "preference_following",
    "summarization",
    "temporal_reasoning",
}


class TestFixtures:
    """The committed lite and full fixtures."""

    def test_lite_is_two_probes_on_three_messages_of_conversation_17(self):
        """Lite has an extraction and a reasoning question on two session slices."""
        manifest = MemoryAdapter().load("lite")

        (corpus,) = manifest.corpora

        assert {q.group for q in manifest.questions} == {
            "information_extraction",
            "multi_session_reasoning",
        }
        assert len(manifest.questions) == 2
        assert corpus.id == "conv17"
        assert [(d.id, d.messages) for d in corpus.documents] == [
            ("conv17-s1", [18]),
            ("conv17-s3", [156, 157]),
        ]

    def test_full_is_twenty_probes_on_each_of_five_conversations(self):
        """Full has 100 questions, 2 per ability on each of 5 conversations."""
        manifest = MemoryAdapter().load("full")

        by_corpus = {c.id: 0 for c in manifest.corpora}
        for question in manifest.questions:
            by_corpus[question.corpus_id] += 1

        assert by_corpus == dict.fromkeys(
            ("conv1", "conv4", "conv6", "conv13", "conv17"), 20
        )
        for ability in ABILITIES:
            assert [q.group for q in manifest.questions].count(ability) == 10

    def test_lite_questions_are_a_subset_of_full_with_the_same_content(self):
        """Every lite question is also a full question on the same conversation."""
        full = MemoryAdapter().load("full")
        lite = MemoryAdapter().load("lite")
        by_id = {q.id: q for q in full.questions}

        for question in lite.questions:
            assert by_id[question.id] == question
        full_corpus = next(c for c in full.corpora if c.id == "conv17")
        assert lite.corpora[0].service == full_corpus.service
        assert all(d.messages is None for d in full_corpus.documents)

    def test_every_question_carries_its_rubric_and_probe_hash(self):
        """The grader reads only the rubric, and the hash pins the source probe."""
        for question in MemoryAdapter().load("full").questions:
            assert question.id.startswith(f"{question.corpus_id}:{question.group}:")
            assert question.reference["rubric"]
            assert len(question.reference["probe_sha256"]) == 64
            assert question.messages == [{"role": "user", "content": question.query}]

    def test_known_bad_probes_are_marked_in_full_and_absent_from_lite(self):
        """Four full probes have a known rubric defect, and none is in lite."""
        full = MemoryAdapter().load("full")
        lite = MemoryAdapter().load("lite")

        marked = {q.id for q in full.questions if "known_bad_rubric" in q.reference}

        assert marked == {
            "conv17:temporal_reasoning:1",
            "conv1:temporal_reasoning:0",
            "conv4:summarization:1",
            "conv4:preference_following:1",
        }
        assert not any("known_bad_rubric" in q.reference for q in lite.questions)

    def test_the_collapsed_message_is_listed_in_the_manifest(self):
        """The one runaway message of the full set is named with its hash."""
        (collapsed,) = MemoryAdapter().load("full").upstream["collapsed_messages"]

        assert (collapsed["conversation"], collapsed["message"]) == ("4", 97)
        assert len(collapsed["original_sha256"]) == 64

    def test_each_conversation_has_its_own_service(self):
        """No two conversations share a service."""
        services = {}
        for corpus in MemoryAdapter().load("full").corpora:
            assert services.setdefault(corpus.service, corpus.id) == corpus.id


def _messages(*texts: str, first_id: int = 0) -> list[dict]:
    return [
        {
            "id": first_id + i,
            "role": "user" if i % 2 == 0 else "assistant",
            "content": text,
            "time_anchor": "March-15-2024" if i == 0 else None,
        }
        for i, text in enumerate(texts)
    ]


class TestSessionText:
    """One session becomes one document."""

    def test_has_a_header_and_one_tagged_block_per_message(self):
        """The header names the session and its date; turns keep their text."""
        messages = _messages("Plan my week ->-> 1,1", "Sure, here is a plan.")

        text = session_text(2, messages)

        assert text == (
            "Session 2, date: March-15-2024\n\n"
            "[msg 0 | user] Plan my week ->-> 1,1\n\n"
            "[msg 1 | assistant] Sure, here is a plan."
        )

    def test_a_selection_keeps_the_session_date_and_only_the_chosen_messages(self):
        """The date comes from the start of the session, not from the first choice."""
        messages = _messages("one", "two", "three")

        text = session_document_text(messages, 4, "9", [1, 2])

        assert text == (
            "Session 4, date: March-15-2024\n\n"
            "[msg 1 | assistant] two\n\n"
            "[msg 2 | user] three"
        )

    def test_a_runaway_message_is_cut_and_marked_while_others_stay(self, monkeypatch):
        """Only the listed message is cut, and the marker counts what it removed."""
        long = "Good start.\n" + "x" * 500
        runaway = RunawayMessage(
            conversation="4",
            message=1,
            keep_chars=12,
            original_chars=len(long),
            original_sha256=hashlib.sha256(long.encode()).hexdigest(),
        )
        monkeypatch.setattr(memory, "RUNAWAY_MESSAGES", [runaway])
        messages = _messages("Question", long, "Next question", first_id=0)

        text = session_text(1, messages, "4")

        assert "[msg 1 | assistant] Good start.\n\n[500 characters of repeated" in text
        assert "x" * 50 not in text
        assert "[msg 2 | user] Next question" in text
        assert "x" * 500 in session_text(1, messages, "5")

    def test_a_message_that_differs_from_the_pinned_original_fails(self):
        """A changed runaway message raises instead of being cut."""
        runaway = RunawayMessage("4", 1, 5, 10, "0" * 64)

        with pytest.raises(HashMismatchError):
            collapse_runaway("some text", runaway)


class TestDocuments:
    """The adapter builds session documents from the fetched rows."""

    def _corpus(self, row: dict) -> Corpus:
        return Corpus(
            id="conv9",
            service="memory-conv17",
            schema_name=MEMORY.name,
            documents=[
                CorpusDocument(
                    id=f"conv9-s{n}",
                    uri=f"beam/9/session-{n}",
                    sha256=text_sha256(session_text(n, messages, "9")),
                    source="x",
                )
                for n, messages in enumerate(row["chat"], start=1)
            ],
        )

    def test_builds_one_document_per_session_in_order(self, monkeypatch):
        """Two sessions give two documents with their uris and session text."""
        row = {"chat": [_messages("a", "b"), _messages("c", "d", first_id=2)]}
        monkeypatch.setattr(memory, "load_rows", lambda columns=None: {"9": row})

        documents = MemoryAdapter().documents(self._corpus(row))

        assert [d.uri for d in documents] == ["beam/9/session-1", "beam/9/session-2"]
        assert documents[1].text.startswith("Session 2, date: March-15-2024")
        assert "[msg 3 | assistant] d" in documents[1].text

    def test_builds_a_document_from_the_chosen_messages_of_a_session(self, monkeypatch):
        """A document with ``messages`` holds only those messages."""
        row = {"chat": [_messages("a", "b", "c")]}
        slice_text = session_document_text(row["chat"][0], 1, "9", [2])
        corpus = Corpus(
            id="conv9",
            service="memory-conv17",
            schema_name=MEMORY.name,
            documents=[
                CorpusDocument(
                    id="conv9-s1",
                    uri="beam/9/session-1",
                    sha256=text_sha256(slice_text),
                    source="x",
                    messages=[2],
                )
            ],
        )
        monkeypatch.setattr(memory, "load_rows", lambda columns=None: {"9": row})

        (document,) = MemoryAdapter().documents(corpus)

        assert document.text == slice_text
        assert "[msg 2 | user] c" in document.text
        assert "[msg 0" not in document.text

    def test_a_changed_session_fails_the_hash_check(self, monkeypatch):
        """Chat text that differs from the fixture hash raises."""
        row = {"chat": [_messages("a", "b")]}
        corpus = self._corpus(row)
        changed = {"chat": [_messages("a", "changed")]}
        monkeypatch.setattr(memory, "load_rows", lambda columns=None: {"9": changed})

        with pytest.raises(HashMismatchError):
            MemoryAdapter().documents(corpus)


class TestCorpusDocument:
    """The message selection of a document."""

    @pytest.mark.parametrize("messages", [[], [-1, 3]])
    def test_an_empty_or_negative_selection_is_refused(self, messages):
        """A selection must name at least one message, by a non-negative id."""
        with pytest.raises(ValueError, match="messages"):
            CorpusDocument(
                id="a", uri="a", sha256="0" * 64, source="x", messages=messages
            )


class TestProbes:
    """The probing questions of a row."""

    def test_parses_the_python_literal_that_json_cannot_read(self):
        """Single quotes and trailing commas parse as a Python literal."""
        row = {
            "probing_questions": (
                "{'abstention': [{'question': 'Why?', 'rubric': ['a'],}]}"
            )
        }

        assert probes(row) == {"abstention": [{"question": "Why?", "rubric": ["a"]}]}


class TestSchema:
    """The memory graph schema."""

    def test_schema_has_the_planned_size_and_survives_a_round_trip(self):
        """It has 11 entity types, 12 relations and a description on every entity."""
        assert len(MEMORY.entities) == 11
        assert len(MEMORY.relations) == 12
        assert all("description" in e.properties for e in MEMORY.entities)
        assert GraphSchema.model_validate(MEMORY.model_dump(mode="json")) == MEMORY

    def test_adapter_returns_the_schema_for_every_conversation(self):
        """All conversations share one schema."""
        for corpus in MemoryAdapter().load("full").corpora:
            assert MemoryAdapter().schema(corpus) is MEMORY
