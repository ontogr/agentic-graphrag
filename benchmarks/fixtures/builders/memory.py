"""Build the BEAM fixtures from the pinned Hugging Face revision.

Lite is ten probing questions, one per ability, on conversation 17. Full is all
twenty probing questions of each of conversations 1, 4, 6, 13 and 17. Writes
``benchmarks/fixtures/memory/{lite,full}.json``.

Usage:
    uv run python -m benchmarks.fixtures.builders.memory
"""

import dataclasses
import json
from pathlib import Path
from typing import Any

import tiktoken

from benchmarks.datasets.memory import (
    DATASET_NAME,
    PARQUET_FILE,
    PARQUET_SHA256,
    REPO,
    REVISION,
    RUNAWAY_MESSAGES,
    document_source,
    load_rows,
    probes,
    session_text,
    text_sha256,
)
from benchmarks.models import (
    BenchmarkQuestion,
    Corpus,
    CorpusDocument,
    CorpusManifest,
    Mode,
    canonical_sha256,
)
from benchmarks.schemas.memory import MEMORY


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "memory"
FULL_CONVERSATIONS = ["1", "4", "6", "13", "17"]
LITE_CONVERSATION = "17"
# One probe per ability on conversation 17: (ability, index within the ability).
LITE_PROBES = [
    ("abstention", 1),
    ("contradiction_resolution", 0),
    ("event_ordering", 0),
    ("information_extraction", 0),
    ("instruction_following", 1),
    ("knowledge_update", 0),
    ("multi_session_reasoning", 0),
    ("preference_following", 1),
    ("summarization", 1),
    ("temporal_reasoning", 0),
]
# Probes whose rubric has a known defect, by (conversation, ability, index).
KNOWN_BAD = {
    ("17", "temporal_reasoning", 1): (
        "The rubric says 46 days from April 20 to July 5, which is 76 days."
    ),
    ("1", "temporal_reasoning", 0): (
        "The reference answer says 4 weeks and the rubric says 8 weeks."
    ),
    ("4", "summarization", 1): "A rubric item has a dropped letter.",
    ("4", "preference_following", 1): "A rubric item has a dropped letter.",
}


def _corpus(conversation: str, row: dict[str, Any], encoder) -> Corpus:
    documents = []
    n_tokens = 0
    for number, messages in enumerate(row["chat"], start=1):
        text = session_text(number, messages, conversation)
        n_tokens += len(encoder.encode(text, disallowed_special=()))
        documents.append(
            CorpusDocument(
                id=f"conv{conversation}-s{number}",
                uri=f"beam/{conversation}/session-{number}",
                sha256=text_sha256(text),
                source=document_source(conversation, number),
            )
        )
    return Corpus(
        id=f"conv{conversation}",
        service=f"memory-conv{conversation}",
        schema_name=MEMORY.name,
        documents=documents,
        n_tokens=n_tokens,
    )


def _question(
    conversation: str, ability: str, index: int, probe: dict[str, Any]
) -> BenchmarkQuestion:
    reference: dict[str, Any] = {
        "rubric": probe["rubric"],
        "probe_sha256": canonical_sha256(probe),
    }
    bad = KNOWN_BAD.get((conversation, ability, index))
    if bad:
        reference["known_bad_rubric"] = bad
    return BenchmarkQuestion(
        id=f"conv{conversation}:{ability}:{index}",
        corpus_id=f"conv{conversation}",
        messages=[{"role": "user", "content": probe["question"]}],
        group=ability,
        reference=reference,
    )


def _manifest(
    mode: Mode, conversations: list[str], rows: dict[str, dict[str, Any]], encoder
) -> CorpusManifest:
    corpora = []
    questions = []
    for conversation in conversations:
        row = rows[conversation]
        corpora.append(_corpus(conversation, row, encoder))
        by_ability = probes(row)
        picks = (
            LITE_PROBES
            if mode == "lite"
            else [(a, i) for a in sorted(by_ability) for i in range(2)]
        )
        questions += [
            _question(conversation, ability, index, by_ability[ability][index])
            for ability, index in picks
        ]
    return CorpusManifest(
        name=DATASET_NAME,
        domain="memory",
        mode=mode,
        upstream={
            "repo": REPO,
            "revision": REVISION,
            "file": PARQUET_FILE,
            "file_sha256": PARQUET_SHA256,
            "collapsed_messages": [dataclasses.asdict(r) for r in RUNAWAY_MESSAGES],
        },
        corpora=corpora,
        questions=questions,
    )


def main() -> None:
    """Write both fixtures."""
    rows = load_rows()
    encoder = tiktoken.get_encoding("cl100k_base")
    plans: list[tuple[Mode, list[str]]] = [
        ("lite", [LITE_CONVERSATION]),
        ("full", FULL_CONVERSATIONS),
    ]
    for mode, conversations in plans:
        manifest = _manifest(mode, conversations, rows, encoder)
        (FIXTURE_DIR / f"{mode}.json").parent.mkdir(parents=True, exist_ok=True)
        (FIXTURE_DIR / f"{mode}.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=1, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        print(
            f"{mode}: {len(manifest.questions)} questions, "
            f"{sum(len(c.documents) for c in manifest.corpora)} documents in "
            f"{len(manifest.corpora)} corpora, "
            f"{sum(c.n_tokens or 0 for c in manifest.corpora)} tokens"
        )


if __name__ == "__main__":
    main()
