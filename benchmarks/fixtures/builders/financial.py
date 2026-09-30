"""Build the Financial fixtures from the pinned FinanceBench repository.

Lite is ten questions on three 10-K filings. Full is every open-source question on
eighteen documents: the three lite documents and fifteen more that have the most
questions per token. Writes ``benchmarks/fixtures/financial/{lite,full}.json``.
Needs ``pdftotext`` to count tokens.

Usage:
    uv run python -m benchmarks.fixtures.builders.financial
"""

import hashlib
import json
import subprocess
import tempfile
import urllib.request
from collections import Counter
from pathlib import Path

import tiktoken

from benchmarks.datasets.financial import (
    COMMIT,
    DATASET_NAME,
    QUESTIONS_FILE,
    QUESTIONS_SHA256,
    RAW_URL,
    REPO,
    pdf_url,
)
from benchmarks.models import (
    BenchmarkQuestion,
    Corpus,
    CorpusDocument,
    CorpusManifest,
    Mode,
    canonical_sha256,
)
from benchmarks.schemas.financial import FINANCIAL


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "financial"
LITE_DOCUMENTS = ["BOEING_2022_10K", "AMAZON_2017_10K", "NETFLIX_2017_10K"]
# The lite questions, in order. The three lite documents hold no other question.
LITE_IDS = [
    "financebench_id_00517",
    "financebench_id_01091",
    "financebench_id_00678",
    "financebench_id_01290",
    "financebench_id_00464",
    "financebench_id_00494",
    "financebench_id_00585",
    "financebench_id_06655",
    "financebench_id_08135",
    "financebench_id_03282",
]
# The full documents: the lite documents, then fifteen added by descending
# questions per token until the set holds 53 questions.
FULL_DOCUMENTS = [
    *LITE_DOCUMENTS,
    "ULTABEAUTY_2023Q4_EARNINGS",
    "FOOTLOCKER_2022_8K_dated-2022-05-20",
    "PEPSICO_2023_8K_dated-2023-05-05",
    "MGMRESORTS_2022Q4_EARNINGS",
    "PEPSICO_2023Q1_EARNINGS",
    "AMCOR_2023Q4_EARNINGS",
    "AMCOR_2022_8K_dated-2022-07-01",
    "JOHNSON_JOHNSON_2023_8K_dated-2023-08-30",
    "BESTBUY_2024Q2_10Q",
    "JOHNSON_JOHNSON_2022Q4_EARNINGS",
    "AMD_2022_10K",
    "FOOTLOCKER_2022_8K_dated_2022-08-19",
    "BESTBUY_2023_10K",
    "Pfizer_2023Q2_10Q",
    "AMERICANEXPRESS_2022_10K",
]


def _download(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:  # noqa: S310
        return response.read()


def _count(pdf: bytes, encoder) -> int:
    """Return the tokens of a PDF as ``pdftotext -layout`` reads it."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as file:
        file.write(pdf)
        file.flush()
        text = subprocess.run(  # noqa: S603
            ["pdftotext", "-layout", file.name, "-"],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    return len(encoder.encode(text, disallowed_special=()))


def _question(row: dict, corpus_id: str) -> BenchmarkQuestion:
    return BenchmarkQuestion(
        id=row["financebench_id"],
        corpus_id=corpus_id,
        messages=[{"role": "user", "content": row["question"]}],
        group=row["question_type"],
        reference={
            "answer": row["answer"],
            "justification": row["justification"],
            "doc_name": row["doc_name"],
            "question_reasoning": row["question_reasoning"],
            "evidence": [
                {"text": e["evidence_text"], "page": e["evidence_page_num"]}
                for e in row["evidence"]
            ],
            "row_sha256": canonical_sha256(row),
        },
    )


def _manifest(
    mode: Mode, names: list[str], rows: list[dict], pdfs: dict[str, bytes], encoder
) -> CorpusManifest:
    corpus_id = f"financial-{mode}"
    documents = [
        CorpusDocument(
            id=name,
            uri=f"{name}.pdf",
            sha256=hashlib.sha256(pdfs[name]).hexdigest(),
            source=pdf_url(name),
        )
        for name in names
    ]
    return CorpusManifest(
        name=DATASET_NAME,
        domain="financial",
        mode=mode,
        upstream={
            "repo": REPO,
            "commit": COMMIT,
            "questions_file": QUESTIONS_FILE,
            "questions_sha256": QUESTIONS_SHA256,
        },
        corpora=[
            Corpus(
                id=corpus_id,
                service=corpus_id,
                schema_name=FINANCIAL.name,
                documents=documents,
                n_tokens=sum(_count(pdfs[n], encoder) for n in names),
            )
        ],
        questions=[_question(row, corpus_id) for row in rows],
    )


def main() -> None:
    """Write both fixtures."""
    raw = _download(f"{RAW_URL}/{QUESTIONS_FILE}")
    if hashlib.sha256(raw).hexdigest() != QUESTIONS_SHA256:
        raise SystemExit("the questions file differs from the pinned hash")
    by_id = {
        r["financebench_id"]: r for r in map(json.loads, raw.decode().splitlines())
    }
    rows = {
        name: [r for r in by_id.values() if r["doc_name"] == name]
        for name in FULL_DOCUMENTS
    }
    if {r["financebench_id"] for n in LITE_DOCUMENTS for r in rows[n]} != set(LITE_IDS):
        raise SystemExit("the lite documents hold other questions")
    lite_rows = [by_id[i] for i in LITE_IDS]
    full_rows = sorted(
        (r for name in FULL_DOCUMENTS for r in rows[name]),
        key=lambda r: r["financebench_id"],
    )
    if (len(lite_rows), len(full_rows)) != (10, 53):
        raise SystemExit(f"unexpected sizes: {len(lite_rows)}, {len(full_rows)}")
    pdfs = {name: _download(pdf_url(name)) for name in FULL_DOCUMENTS}
    encoder = tiktoken.get_encoding("cl100k_base")
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    plans: dict[Mode, tuple[list[str], list[dict]]] = {
        "lite": (LITE_DOCUMENTS, lite_rows),
        "full": (FULL_DOCUMENTS, full_rows),
    }
    for mode, (names, picks) in plans.items():
        manifest = _manifest(mode, names, picks, pdfs, encoder)
        (FIXTURE_DIR / f"{mode}.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=1, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        by_type = Counter(q.group for q in manifest.questions)
        print(
            f"{mode}: {len(manifest.questions)} questions {dict(by_type)}, "
            f"{len(names)} documents, {manifest.corpora[0].n_tokens} tokens"
        )


if __name__ == "__main__":
    main()
