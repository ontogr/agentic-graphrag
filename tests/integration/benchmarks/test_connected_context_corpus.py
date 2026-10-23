"""Checks the connected-context manifest against the pinned source files.

The unit tests read the committed manifest as data. These tests download the
legal files and the BEAM chat file at their pinned revisions, into the benchmark
cache when they are not there yet, and check that the stored offsets and hashes
still read back to the same text.
"""

import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from huggingface_hub import hf_hub_download

from benchmarks.datasets.conversation_history import PARQUET_FILE, session_document_text
from benchmarks.datasets.conversation_history import REPO as BEAM_REPO
from benchmarks.datasets.conversation_history import REVISION as BEAM_REVISION
from benchmarks.datasets.fetch import CACHE_DIR
from benchmarks.datasets.legal import REPO as LEGAL_REPO
from benchmarks.datasets.legal import REVISION as LEGAL_REVISION
from benchmarks.fixtures.builders.connected_context import MANIFEST_PATH


LEGAL_URIS = {
    "privacy_qa/Keep.txt",
    "privacy_qa/Viber Messenger.txt",
    "contractnli/Kenway-NDA-Form-Blank.txt",
}


@pytest.fixture
def manifest() -> dict:
    """Return the committed manifest."""
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _download(repo: str, filename: str, revision: str) -> Path:
    """Return the pinned file, downloading it into the benchmark cache if needed."""
    return Path(
        hf_hub_download(
            repo,
            filename,
            repo_type="dataset",
            revision=revision,
            cache_dir=CACHE_DIR / "hf",
        )
    )


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


def _sha(text: str) -> str:
    """Return the SHA-256 of a text as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _history_texts(manifest: dict) -> dict[str, str]:
    """Return each BEAM session text rebuilt from the downloaded chat file."""
    path = _download(BEAM_REPO, PARQUET_FILE, BEAM_REVISION)
    rows = {
        row["conversation_id"]: row
        for row in pq.read_table(path, columns=["conversation_id", "chat"]).to_pylist()
    }
    texts = {}
    for document in manifest["documents"]:
        if document["corpus"] != "conversation_history":
            continue
        _, conversation, session_label = document["uri"].split("/")
        number = int(session_label.removeprefix("session-"))
        session = rows[conversation]["chat"][number - 1]
        texts[document["uri"]] = session_document_text(
            session, number, conversation, document["messages"]
        )
    return texts


class TestCorpusText:
    """Text-level checks against the pinned files, downloaded on first use."""

    @pytest.mark.parametrize("uri", sorted(LEGAL_URIS))
    @staticmethod
    def test_legal_file_matches_its_content_hash(manifest, uri):
        """The pinned file reads back to the stored hash, unchanged by normalization."""
        path = _download(LEGAL_REPO, f"corpus/{uri}", LEGAL_REVISION)
        text = path.read_text(encoding="utf-8")
        document = next((d for d in manifest["documents"] if d["uri"] == uri), None)
        assert document is not None

        assert _sha(text) == document["content_sha256"]

    @staticmethod
    def test_stored_span_text_hashes_match(manifest):
        """Each span's stored hash and its legal answer match the cached file."""
        texts = {}
        for uri in LEGAL_URIS:
            path = _download(LEGAL_REPO, f"corpus/{uri}", LEGAL_REVISION)
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
            path = _download(LEGAL_REPO, f"corpus/{uri}", LEGAL_REVISION)
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
    def test_history_sessions_match_their_stored_hashes(manifest):
        """Each BEAM session rebuilt from the cached chat file matches its hash."""
        texts = _history_texts(manifest)
        for document in manifest["documents"]:
            if document["corpus"] == "conversation_history":
                assert _sha(texts[document["uri"]]) == document["content_sha256"]

    @staticmethod
    def test_history_spans_read_back_from_their_session(manifest):
        """Each BEAM span lies inside its session and reads back to its hash."""
        texts = _history_texts(manifest)
        for span in _v1_spans(manifest):
            if span["document"] not in texts:
                continue
            text = texts[span["document"]]
            assert 0 <= span["char_start"] < span["char_end"] <= len(text)
            found = text[span["char_start"] : span["char_end"]]
            assert _sha(found) == span["text_sha256"]

    @staticmethod
    def test_history_distractor_counts_match_the_other_session(manifest):
        """Each evidence phrase is counted in the other session as the manifest says."""
        texts = _history_texts(manifest)
        for span in _case(manifest, "cross_session_recall")["support"]:
            found = texts[span["document"]][span["char_start"] : span["char_end"]]
            others = [text for uri, text in texts.items() if uri != span["document"]]
            assert span["distractor_matches_in_other_excerpt"] == sum(
                text.count(found) for text in others
            )
