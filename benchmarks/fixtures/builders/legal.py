"""Build the Legal fixtures from the pinned LegalBench-RAG mirror.

Rebuilds the mini sample with the upstream rule (up to 194 questions per source,
ordered by a per-document seed), checks that every gold span reads back from its
document, then picks the lite and full questions and writes
``benchmarks/fixtures/legal/{lite,full}.json``.

Usage:
    uv run python -m benchmarks.fixtures.builders.legal
"""

import collections
import hashlib
import json
import random
import unicodedata
from pathlib import Path

import tiktoken
from huggingface_hub import hf_hub_download

from benchmarks.datasets.legal import (
    BENCHMARK_FILES_SHA256,
    DATASET_NAME,
    REPO,
    REVISION,
    SOURCES,
    document_source,
)
from benchmarks.models import (
    BenchmarkQuestion,
    Corpus,
    CorpusDocument,
    CorpusManifest,
    Mode,
)


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "legal"
MINI_PER_SOURCE = 194
FULL_PER_SOURCE = 25
# Documents kept per source in the full set: most questions first, and for MAUD
# the shortest documents.
FULL_DOCUMENTS = {"privacy_qa": 2, "contractnli": 4, "cuad": 7, "maud": 2}
# The lite questions: (source, document name, part of the query). MAUD is left out
# because one MAUD document would be most of the ingest cost.
LITE = [
    ("privacy_qa", "Viber Messenger.txt", "how is my data used?"),
    ("privacy_qa", "Viber Messenger.txt", "how long do you retain meta data?"),
    (
        "contractnli",
        "Kenway-NDA-Form-Blank.txt",
        "obligations of the Agreement may survive",
    ),
    (
        "contractnli",
        "Kenway-NDA-Form-Blank.txt",
        "required by law, regulation, or judic",
    ),
    ("cuad", "DUOSTECHNOLOGIESGROUP", "What is the governing law"),
    ("cuad", "DUOSTECHNOLOGIESGROUP", "Is there a non-compete clause"),
    (
        "cuad",
        "DUOSTECHNOLOGIESGROUP",
        "How is intellectual property ownership assigned",
    ),
    (
        "privacy_qa",
        "Viber Messenger.txt",
        "how is any information collected by viber shared",
    ),
    (
        "contractnli",
        "Kenway-NDA-Form-Blank.txt",
        "retain some Confidential Information even after",
    ),
    (
        "privacy_qa",
        "Viber Messenger.txt",
        "can i submit a request to have my data deleted",
    ),
]


def nfc(text: str) -> str:
    """Return the NFC form of a path."""
    return unicodedata.normalize("NFC", text)


def question_id(source: str, test: dict) -> str:
    """Return ``<source>:<sha1[:8]>`` of the query and its gold spans."""
    key = json.dumps([test["query"], [s["span"] for s in test["snippets"]]])
    return f"{source}:{hashlib.sha1(key.encode()).hexdigest()[:8]}"  # noqa: S324


def _hub(filename: str) -> Path:
    return Path(hf_hub_download(REPO, filename, repo_type="dataset", revision=REVISION))


def _load_mini() -> dict[str, list[dict]]:
    """Return the mini sample: up to 194 questions of each source."""
    mini = {}
    for source in SOURCES:
        tests = json.loads(_hub(f"benchmarks/{source}.json").read_text("utf-8"))[
            "tests"
        ]
        if len(tests) > MINI_PER_SOURCE:
            tests = sorted(
                tests,
                key=lambda t: (
                    random.seed(t["snippets"][0]["file_path"]),
                    random.random(),
                )[1],
            )[:MINI_PER_SOURCE]
        mini[source] = tests
    return mini


def _check_benchmark_files() -> None:
    digest = hashlib.sha256()
    for source in SOURCES:
        digest.update(_hub(f"benchmarks/{source}.json").read_bytes())
    if digest.hexdigest() != BENCHMARK_FILES_SHA256:
        raise SystemExit(f"benchmark files differ: {digest.hexdigest()}")


def _select(mini: dict[str, list[dict]], text) -> tuple[list, list]:
    """Return the lite and full picks as ``(source, test)`` pairs."""
    lite: list[tuple[str, dict]] = []
    for source, document, needle in LITE:
        hits = [
            t
            for t in mini[source]
            if document in t["snippets"][0]["file_path"] and needle in t["query"]
        ]
        if not hits:
            raise SystemExit(f"no lite question for {(source, document, needle)}")
        lite.append((source, hits[0]))
    lite_ids = {question_id(s, t) for s, t in lite}

    full: list[tuple[str, dict]] = []
    for source, tests in mini.items():
        per_document = collections.Counter(t["snippets"][0]["file_path"] for t in tests)
        if source == "maud":
            ordered = sorted(per_document, key=lambda d: (len(text(d)), d))
        else:
            ordered = sorted(per_document, key=lambda d: (-per_document[d], d))
        keep = set(ordered[: FULL_DOCUMENTS[source]])
        seen: set[str] = set()
        pool = []
        for test in tests:
            if test["snippets"][0]["file_path"] in keep and test["query"] not in seen:
                seen.add(test["query"])
                pool.append(test)
        forced = [t for t in pool if question_id(source, t) in lite_ids]
        rest = [t for t in pool if question_id(source, t) not in lite_ids]
        random.Random(42).shuffle(rest)
        chosen = (forced + rest)[:FULL_PER_SOURCE]
        if len(chosen) != FULL_PER_SOURCE:
            raise SystemExit(f"{source}: only {len(chosen)} questions")
        full += [(source, t) for t in chosen]
    if not lite_ids <= {question_id(s, t) for s, t in full}:
        raise SystemExit("lite is not a subset of full")
    return lite, full


def _manifest(
    mode: Mode, picks: list, sums: dict[str, str], text, encoder
) -> CorpusManifest:
    paths = sorted({nfc(t["snippets"][0]["file_path"]) for _, t in picks})
    documents = [
        CorpusDocument(
            id=path,
            uri=path,
            sha256=sums[f"corpus/{path}"],
            source=document_source(path),
        )
        for path in paths
    ]
    n_tokens = sum(
        len(encoder.encode(text(path), disallowed_special=())) for path in paths
    )
    questions = [
        BenchmarkQuestion(
            id=question_id(source, test),
            corpus_id=f"legal-{mode}",
            messages=[{"role": "user", "content": test["query"]}],
            group=source,
            reference={
                "snippets": [
                    {
                        "uri": nfc(s["file_path"]),
                        "span": s["span"],
                        "answer": s["answer"],
                    }
                    for s in test["snippets"]
                ]
            },
        )
        for source, test in picks
    ]
    return CorpusManifest(
        name=DATASET_NAME,
        domain="legal",
        mode=mode,
        upstream={
            "repo": REPO,
            "revision": REVISION,
            "benchmark_files_sha256": BENCHMARK_FILES_SHA256,
        },
        corpora=[
            Corpus(
                id=f"legal-{mode}",
                service=f"legal-{mode}",
                schema_name="legal",
                documents=documents,
                n_tokens=n_tokens,
            )
        ],
        questions=questions,
    )


def main() -> None:
    """Write both fixtures."""
    _check_benchmark_files()
    sums = {}
    for line in _hub("SHA256SUMS").read_text("utf-8").splitlines():
        digest, _, name = line.partition("  ")
        sums[nfc(name)] = digest
    texts: dict[str, str] = {}

    def text(path: str) -> str:
        path = nfc(path)
        if path not in texts:
            texts[path] = _hub(f"corpus/{path}").read_text(encoding="utf-8")
        return texts[path]

    mini = _load_mini()
    for tests in mini.values():
        for test in tests:
            for snippet in test["snippets"]:
                start, end = snippet["span"]
                if text(snippet["file_path"])[start:end] != snippet["answer"]:
                    raise SystemExit(f"span does not read back: {test['query']}")
    lite, full = _select(mini, text)
    encoder = tiktoken.get_encoding("cl100k_base")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for mode, picks in (("lite", lite), ("full", full)):
        manifest = _manifest(mode, picks, sums, text, encoder)  # type: ignore[arg-type]
        path = FIXTURE_DIR / f"{mode}.json"
        path.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=1, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        print(
            f"{mode}: {len(manifest.questions)} questions, "
            f"{len(manifest.corpora[0].documents)} documents, "
            f"{manifest.corpora[0].n_tokens} tokens"
        )


if __name__ == "__main__":
    main()
