"""Build the GraphRAG-Bench fixtures from the pinned Hugging Face revision.

Lite is five Novel-25646 questions and five Medical questions on the first three
guideline extracts. Full is 130 Medical and 120 Novel questions on the whole Medical
corpus and four novels, sampled with seed 42 in proportion to the question types of
each population, with the lite questions forced in. Writes
``benchmarks/fixtures/graphrag_general/{lite,full}.json``.

Usage:
    uv run python -m benchmarks.fixtures.builders.graphrag_general
"""

import hashlib
import json
import random
from collections import Counter
from pathlib import Path

import tiktoken
from huggingface_hub import hf_hub_download

from benchmarks.datasets.graphrag_general import (
    CORPUS_FILES,
    DATASET_NAME,
    FILE_SHA256,
    QUESTION_FILES,
    REPO,
    REVISION,
    document_source,
    medical_piece_id,
    medical_pieces,
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
from benchmarks.schemas.graphrag_general import MEDICAL, NOVEL


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "graphrag_general"
SEED = 42
LITE_NOVEL = "Novel-25646"
# Body-text questions only: none rests on the Gutenberg credits or contents list.
LITE_NOVEL_IDS = [
    "Novel-8cc0478d",
    "Novel-0c5272d1",
    "Novel-c8928151",
    "Novel-71646b3e",
    "Novel-1f8fc3b0",
]
# The lite Medical text is the first three extracts: basal cell skin cancer, adrenal
# tumors and squamous cell skin cancer. The end is the start of the fourth extract.
LITE_MEDICAL_PIECES = 3
LITE_MEDICAL_END = 81_651
LITE_MEDICAL_IDS = [
    "Medical-6baf8bff",
    "Medical-a9a52704",
    "Medical-8fe8663f",
    "Medical-338ef222",
    "Medical-2e1ccbe9",
]
FULL_NOVELS = ["Novel-2544", "Novel-8559", "Novel-25646", "Novel-41603"]
FULL_COUNTS = {"medical": 130, "novel": 120}


def _load(filename: str) -> list[dict]:
    """Return a dataset file, after checking its hash."""
    path = Path(hf_hub_download(REPO, filename, repo_type="dataset", revision=REVISION))
    if hashlib.sha256(path.read_bytes()).hexdigest() != FILE_SHA256[filename]:
        raise SystemExit(f"{filename} differs from the pinned hash")
    return json.loads(path.read_text(encoding="utf-8"))


def _allocate(counts: dict[str, int], target: int) -> dict[str, int]:
    """Split ``target`` across keys in proportion to ``counts``, largest remainder."""
    total = sum(counts.values())
    quota = {k: target * n / total for k, n in counts.items()}
    allocation = {k: int(q) for k, q in quota.items()}
    by_remainder = sorted(quota, key=lambda k: (allocation[k] - quota[k], k))
    for key in by_remainder[: target - sum(allocation.values())]:
        allocation[key] += 1
    return allocation


def _sample(pool: list[dict], target: int, forced_ids: list[str]) -> list[dict]:
    """Sample ``target`` questions that match the pool's type mix.

    The forced questions come first and count toward their type's quota. Each type
    draws from a seeded shuffle of the pool in file order.
    """
    rng = random.Random(SEED)
    by_id = {q["id"]: q for q in pool}
    if len(by_id) != len(pool):
        raise SystemExit("question ids repeat inside a pool")
    forced = [by_id[i] for i in forced_ids]
    quota = _allocate(Counter(q["question_type"] for q in pool), target)
    forced_by_type = Counter(q["question_type"] for q in forced)
    picked = list(forced)
    for qtype in sorted(quota):
        need = quota[qtype] - forced_by_type[qtype]
        if need < 0:
            raise SystemExit(f"too many forced {qtype} questions")
        rest = [
            q for q in pool if q["question_type"] == qtype and q["id"] not in forced_ids
        ]
        rng.shuffle(rest)
        picked.extend(rest[:need])
    return picked


def _question(row: dict, kind: str, corpus_id: str) -> BenchmarkQuestion:
    return BenchmarkQuestion(
        id=f"{kind}:{row['id']}",
        corpus_id=corpus_id,
        messages=[{"role": "user", "content": row["question"]}],
        group=row["question_type"],
        reference={
            "answer": row["answer"],
            "evidence": row["evidence"],
            "row_sha256": canonical_sha256(row),
        },
    )


def _novel_corpus(name: str, text: str, tokens: int) -> Corpus:
    number = name.removeprefix("Novel-")
    return Corpus(
        id=f"novel-{number}",
        service=f"graphrag-novel-{number}",
        schema_name=NOVEL.name,
        documents=[
            CorpusDocument(
                id=name,
                uri=f"novel/{name}",
                sha256=text_sha256(text),
                source=document_source(CORPUS_FILES["novel"], name),
            )
        ],
        n_tokens=tokens,
    )


def _medical_corpus(mode: Mode, pieces: list[str], encoder) -> Corpus:
    return Corpus(
        id=f"medical-{mode}",
        service=f"graphrag-medical-{mode}",
        schema_name=MEDICAL.name,
        documents=[
            CorpusDocument(
                id=medical_piece_id(i),
                uri=f"medical/{i:02d}",
                sha256=text_sha256(piece),
                source=document_source(CORPUS_FILES["medical"], f"piece-{i:02d}"),
            )
            for i, piece in enumerate(pieces)
        ],
        n_tokens=sum(len(encoder.encode(p, disallowed_special=())) for p in pieces),
    )


def main() -> None:
    """Write both fixtures."""
    medical_rows = _load(QUESTION_FILES["medical"])
    novel_rows = _load(QUESTION_FILES["novel"])
    blob = _load(CORPUS_FILES["medical"])[0]["context"]
    novels = {r["corpus_name"]: r["context"] for r in _load(CORPUS_FILES["novel"])}
    pieces = medical_pieces(blob)
    if len(pieces) != 44 or not all(pieces):
        raise SystemExit(f"expected 44 non-empty extracts, got {len(pieces)}")
    lite_segment = blob[:LITE_MEDICAL_END]
    if lite_segment != "\n".join(pieces[:LITE_MEDICAL_PIECES]) + "\n":
        raise SystemExit("the lite segment is not the first three extracts")

    medical_by_id = {r["id"]: r for r in medical_rows}
    novel_by_id = {r["id"]: r for r in novel_rows if r["source"] == LITE_NOVEL}
    lite_medical = [medical_by_id[i] for i in LITE_MEDICAL_IDS]
    lite_novel = [novel_by_id[i] for i in LITE_NOVEL_IDS]
    novel_pool = [r for r in novel_rows if r["source"] in FULL_NOVELS]
    full_medical = _sample(medical_rows, FULL_COUNTS["medical"], LITE_MEDICAL_IDS)
    full_novel = _sample(novel_pool, FULL_COUNTS["novel"], LITE_NOVEL_IDS)

    encoder = tiktoken.get_encoding("cl100k_base")
    tokens = {n: len(encoder.encode(novels[n], disallowed_special=())) for n in novels}
    upstream = {
        "repo": REPO,
        "revision": REVISION,
        "files": FILE_SHA256,
        "medical_lite_segment": {
            "start": 0,
            "end": LITE_MEDICAL_END,
            "sha256": text_sha256(lite_segment),
        },
    }
    lite_corpora = [
        _novel_corpus(LITE_NOVEL, novels[LITE_NOVEL], tokens[LITE_NOVEL]),
        _medical_corpus("lite", pieces[:LITE_MEDICAL_PIECES], encoder),
    ]
    full_corpora = [
        _medical_corpus("full", pieces, encoder),
        *(_novel_corpus(n, novels[n], tokens[n]) for n in FULL_NOVELS),
    ]
    novel_corpus = {
        f"Novel-{c.id.removeprefix('novel-')}": c.id for c in full_corpora[1:]
    }
    plans: dict[Mode, tuple[list[Corpus], list[BenchmarkQuestion]]] = {
        "lite": (
            lite_corpora,
            [_question(r, "novel", "novel-25646") for r in lite_novel]
            + [_question(r, "medical", "medical-lite") for r in lite_medical],
        ),
        "full": (
            full_corpora,
            [_question(r, "medical", "medical-full") for r in full_medical]
            + [_question(r, "novel", novel_corpus[r["source"]]) for r in full_novel],
        ),
    }
    lite_ids = {q.id for q in plans["lite"][1]}
    if not lite_ids <= {q.id for q in plans["full"][1]}:
        raise SystemExit("lite is not a subset of full")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for mode, (corpora, questions) in plans.items():
        manifest = CorpusManifest(
            name=DATASET_NAME,
            domain="graphrag_general",
            mode=mode,
            upstream=upstream,
            corpora=corpora,
            questions=questions,
        )
        (FIXTURE_DIR / f"{mode}.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=1, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        by_type = Counter(q.group for q in questions)
        print(
            f"{mode}: {len(questions)} questions {dict(by_type)}, "
            f"{sum(c.n_tokens or 0 for c in corpora)} tokens in {len(corpora)} corpora"
        )


if __name__ == "__main__":
    main()
