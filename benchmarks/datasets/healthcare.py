"""HealthBench: health conversations answered from StatPearls and medical textbooks.

The questions are prompts of the HealthBench Hard set, and each has its own rubric.
The corpus is the set of passages that a text search finds for the selected prompts.
A passage is a StatPearls paragraph or a textbook chunk from the MedCorp datasets.
The fixture lists the questions, their rubrics, and the place and hash of each
passage. The passage text comes from pinned Hugging Face revisions at run time.
"""

import hashlib
import json
import re
from collections.abc import Iterator, Sequence
from pathlib import Path

import pyarrow.parquet as pq

from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_schema import GraphSchema
from benchmarks.datasets.base import DatasetAdapter, Domain, text_document
from benchmarks.datasets.fetch import HashMismatchError, fetch_hf_file
from benchmarks.grading.healthbench import HealthBenchGrader
from benchmarks.models import Corpus, CorpusManifest, Mode
from benchmarks.schemas.healthcare import HEALTHCARE


DATASET_NAME = "healthbench-hard"
# The rubric items of the one lite question, which is one judge call each.
LITE_RUBRIC_ITEMS = 3
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "healthcare"
# The pinned repos, revisions, files and file hashes of the three source datasets.
SOURCES: dict[str, dict] = json.loads(
    Path(__file__).with_name("healthcare_sources.json").read_text(encoding="utf-8")
)
_REFERENCE = re.compile(
    r"^hf://datasets/(?P<repo>[^@]+)@(?P<revision>[0-9a-f]{40})/(?P<file>.+)#(?P<row>\d+)$"
)


def passage_reference(source: str, file: str, row: int) -> str:
    """Return the address of one passage: repo, revision, file and row.

    Args:
        source: The name of a source in ``SOURCES``.
        file: The file of the source that holds the passage.
        row: The zero-based row of the passage in the file.

    Returns:
        An ``hf://datasets/<repo>@<revision>/<file>#<row>`` reference.
    """
    pin = SOURCES[source]
    return f"hf://datasets/{pin['repo']}@{pin['revision']}/{file}#{row}"


def passage_sha256(contents: str) -> str:
    """Return the SHA-256 of a passage text as UTF-8.

    Args:
        contents: The passage text.

    Returns:
        The hash as a lowercase hexadecimal string.
    """
    return hashlib.sha256(contents.encode("utf-8")).hexdigest()


def fetch_source_file(source: str, file: str) -> Path:
    """Fetch one file of a source at its pinned revision and check its hash.

    Args:
        source: The name of a source in ``SOURCES``.
        file: The file to fetch, as listed for the source.

    Returns:
        The path of the file in the local cache.

    Raises:
        HashMismatchError: The fetched file differs from its pinned hash.
    """
    pin = SOURCES[source]
    return fetch_hf_file(
        pin["repo"], file, revision=pin["revision"], sha256=pin["files"][file]
    )


def iter_rows(path: Path) -> Iterator[tuple[int, str, str]]:
    """Yield ``(row, id, contents)`` for each passage of a MedCorp file, in order.

    Reads a Parquet file in batches, so the whole file is never in memory. A JSONL
    file is read as bytes, so only a line feed ends a row.

    Args:
        path: A Parquet or JSONL file of a MedCorp source.

    Yields:
        The zero-based row, the passage id and the passage text.
    """
    if path.suffix == ".parquet":
        row = 0
        for batch in pq.ParquetFile(path).iter_batches(columns=["id", "contents"]):
            for passage_id, contents in zip(
                batch.column("id").to_pylist(),
                batch.column("contents").to_pylist(),
                strict=True,
            ):
                yield row, passage_id, contents
                row += 1
        return
    with path.open("rb") as lines:
        for row, line in enumerate(lines):
            record = json.loads(line)
            yield row, record["id"], record["contents"]


class HealthcareAdapter(DatasetAdapter):
    """The lite and full selections of HealthBench Hard."""

    def load(self, mode: Mode) -> CorpusManifest:
        """Return the manifest of one mode from its fixture.

        Args:
            mode: The mode to load, ``lite`` or ``full``.

        Returns:
            The questions, rubrics and passage references of the mode.
        """
        text = (FIXTURE_DIR / f"{mode}.json").read_text(encoding="utf-8")
        return CorpusManifest.model_validate_json(text)

    def documents(self, corpus: Corpus) -> Sequence[Document]:
        """Fetch each passage and build one document for it.

        The text is the ``contents`` field of the source row, which is the title,
        a period and a space, and the passage. It is used as it is.

        Args:
            corpus: The corpus whose passages to fetch.

        Returns:
            One document for each passage of the corpus, in corpus order.

        Raises:
            HashMismatchError: A file or a passage differs from its pinned hash.
        """
        by_file: dict[tuple[str, str], dict[int, tuple[str, str]]] = {}
        for entry in corpus.documents:
            match = _REFERENCE.match(entry.source)
            if match is None:
                raise ValueError(f"{entry.id}: bad source {entry.source!r}")
            source = next(
                name for name, pin in SOURCES.items() if pin["repo"] == match["repo"]
            )
            by_file.setdefault((source, match["file"]), {})[int(match["row"])] = (
                entry.id,
                entry.sha256,
            )
        texts: dict[str, str] = {}
        for (source, file), wanted in by_file.items():
            found = 0
            for row, passage_id, contents in iter_rows(fetch_source_file(source, file)):
                if row not in wanted:
                    continue
                expected_id, sha256 = wanted[row]
                if passage_id != expected_id or passage_sha256(contents) != sha256:
                    raise HashMismatchError(f"{expected_id}: passage differs")
                texts[expected_id] = contents
                found += 1
                if found == len(wanted):
                    break
            if found != len(wanted):
                raise HashMismatchError(f"{file}: rows are missing")
        return [
            text_document(texts[entry.id], uri=entry.uri, title=entry.id)
            for entry in corpus.documents
        ]

    def schema(self, corpus: Corpus) -> GraphSchema:
        """Return the healthcare schema.

        Args:
            corpus: The corpus. The schema does not depend on it.

        Returns:
            The graph schema for healthcare.
        """
        return HEALTHCARE


DOMAIN = Domain(
    adapter=HealthcareAdapter(),
    grader=HealthBenchGrader(judge_calls_per_question=LITE_RUBRIC_ITEMS),
    full_grader=HealthBenchGrader(),
)
