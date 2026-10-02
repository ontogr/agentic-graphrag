"""A text-search index of MedCorp, used to rebuild and check the corpus selection.

The benchmark corpus is the set of passages that a BM25 search over StatPearls and
the 18 textbooks finds for the last user turn of each selected prompt. The fixture
holds that set, so a run does not need this index. The index rebuilds the set from
the pinned sources, so you can check the fixture against the search rule.
"""

import re
import sqlite3
from collections.abc import Iterable, Sequence
from itertools import zip_longest
from pathlib import Path

from benchmarks.datasets.fetch import CACHE_DIR
from benchmarks.datasets.healthcare import (
    SOURCES,
    HealthcareAdapter,
    fetch_source_file,
    iter_rows,
)
from benchmarks.models import CorpusManifest, Mode


INDEX_PATH = CACHE_DIR / "healthcare" / "medcorp-fts.sqlite"
# The passages of each indexed source, as the pinned revisions hold them.
SOURCE_ROWS = {"textbooks": 125_847, "statpearls": 344_976}
MAX_QUERY_TERMS = 40
BATCH = 5000
# The number of passages kept for each prompt. Lite names its few passages by id,
# and each must be among the passages that full keeps for its question.
CLOSURE_K: dict[Mode, int] = {"full": 32}
# fmt: off
STOP = {
    "a", "about", "above", "after", "again", "all", "also", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "could", "did", "do",
    "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "him", "his", "how", "i", "if", "in", "into", "is", "it", "its", "just",
    "me", "more", "most", "my", "no", "nor", "not", "now", "of", "off", "on",
    "once", "only", "or", "other", "our", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "will", "with", "would",
    "you", "your", "please", "tell", "give", "help", "need", "want", "know",
    "like", "get", "got", "make", "one", "two",
}
# fmt: on


def words(text: str) -> list[str]:
    """Split a text into lowercase words, keeping digits and inner ``:./-``.

    Args:
        text: The text to split.

    Returns:
        The words in the order they occur, repeats included.
    """
    return re.findall(r"[a-z0-9][a-z0-9:./-]*[a-z0-9]|[a-z0-9]", text.lower())


def fts_query(text: str) -> str:
    """Return the search query for a prompt turn.

    The query is the first 40 distinct words of three letters or more that are
    not stop words, each in quotes, joined with ``OR``. Quotes keep punctuation
    from being a syntax error.

    Args:
        text: The text of the prompt turn.

    Returns:
        The query for the FTS5 ``MATCH`` operator, or an empty string when the text
        has no usable word.
    """
    seen: list[str] = []
    for word in words(text):
        if len(word) > 2 and word not in STOP and word not in seen:
            seen.append(word)
    return " OR ".join(f'"{word}"' for word in seen[:MAX_QUERY_TERMS])


def _source_files(source: str) -> list[str]:
    """Return the files of a source in the order that the index reads them."""
    return sorted(SOURCES[source]["files"])


def _passages(source: str) -> Iterable[tuple[str, str]]:
    for file in _source_files(source):
        for _, passage_id, contents in iter_rows(fetch_source_file(source, file)):
            yield passage_id, contents


def build_index(path: Path = INDEX_PATH) -> int:
    """Build the index of StatPearls and the textbooks, or finish a partial one.

    A source is skipped only when a past run read all of its rows. The rows of a
    source that a run left half read are removed, and the source is read again.

    Args:
        path: Where the SQLite file goes.

    Returns:
        The number of passages in the index.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS complete (source TEXT PRIMARY KEY)")
    db.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS docs USING fts5("
        "doc_id UNINDEXED, source UNINDEXED, contents, tokenize='porter unicode61')"
    )
    done = {row[0] for row in db.execute("SELECT source FROM complete")}
    for source in ("textbooks", "statpearls"):
        if source in done:
            continue
        db.execute("DELETE FROM docs WHERE source = ?", (source,))
        db.commit()
        batch: list[tuple[str, str, str]] = []
        for passage_id, contents in _passages(source):
            batch.append((passage_id, source, contents))
            if len(batch) == BATCH:
                db.executemany("INSERT INTO docs VALUES (?,?,?)", batch)
                db.commit()
                batch = []
        db.executemany("INSERT INTO docs VALUES (?,?,?)", batch)
        db.execute("INSERT INTO complete VALUES (?)", (source,))
        db.commit()
    db.execute("INSERT INTO docs(docs) VALUES ('optimize')")
    db.commit()
    count = db.execute("SELECT count(*) FROM docs").fetchone()[0]
    db.close()
    return count


def index_problems(db: sqlite3.Connection) -> list[str]:
    """Return what makes an index differ from the pinned sources.

    A source must have its full passage count with a distinct id for each passage.
    An index that a build did not finish, or that has a changed row, fails.

    Args:
        db: The open index.

    Returns:
        A message for each source that differs. The list is empty for a sound index.
    """
    problems = []
    for source, expected in SOURCE_ROWS.items():
        rows, distinct = db.execute(
            "SELECT count(*), count(DISTINCT doc_id) FROM docs WHERE source = ?",
            (source,),
        ).fetchone()
        if rows != expected:
            problems.append(f"{source} has {rows} passages, not {expected}")
        if distinct != rows:
            problems.append(f"{source} has {rows - distinct} repeated passage ids")
    return problems


def content_problems(db: sqlite3.Connection) -> list[str]:
    """Return the sources whose indexed passages differ from the pinned ones.

    Each source must hold the same ids and texts, in the same order, as its pinned
    files. This reads the pinned files, which are fetched when not cached.

    Args:
        db: The open index.

    Returns:
        A message for each source that differs. The list is empty for a faithful
        index.
    """
    problems = []
    for source in SOURCE_ROWS:
        indexed = db.execute(
            "SELECT doc_id, contents FROM docs WHERE source = ? ORDER BY rowid",
            (source,),
        )
        if any(a != b for a, b in zip_longest(indexed, _passages(source))):
            problems.append(f"{source} differs from the pinned passages")
    return problems


def closure(db: sqlite3.Connection, turn: str, k: int) -> list[str]:
    """Return the ids of the best ``k`` passages for a prompt turn, best first.

    Args:
        db: The open index.
        turn: The text of the prompt turn.
        k: The most passages to return.

    Returns:
        The passage ids in rank order. The list is empty when the turn gives no query.
    """
    query = fts_query(turn)
    if not query:
        return []
    rows = db.execute(
        "SELECT doc_id FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?", (query, k)
    ).fetchall()
    return [row[0] for row in rows]


def check_manifest(
    db: sqlite3.Connection, manifest: CorpusManifest, k: int, *, subset: bool = False
) -> Sequence[str]:
    """Return what differs between a manifest's corpus and the search rule.

    Args:
        db: The open index.
        manifest: A healthcare manifest.
        k: The number of passages kept for each question.
        subset: Whether the corpus may hold fewer passages than the union.

    Returns:
        A message for each difference. The list is empty when the corpus is the
        union of the best ``k`` passages of every question, or, with ``subset``,
        a part of that union.
    """
    expected: set[str] = set()
    for question in manifest.questions:
        expected.update(closure(db, question.query, k))
    actual = {document.id for document in manifest.corpora[0].documents}
    problems = []
    if expected - actual and not subset:
        problems.append(f"{len(expected - actual)} passages are missing")
    if actual - expected:
        problems.append(f"{len(actual - expected)} passages are not in any closure")
    return problems


def check_index(path: Path = INDEX_PATH) -> tuple[int, list[str]]:
    """Check an index against the committed fixtures.

    The index must hold every passage of the pinned sources, with the pinned id and
    text. The full corpus must be the union of the best passages for its questions,
    and the lite corpus must be a part of the union for its questions.

    Args:
        path: The SQLite file of the index.

    Returns:
        The number of passages in the index, and a message for each difference.
    """
    db = sqlite3.connect(path)
    rows = db.execute("SELECT count(*) FROM docs").fetchone()[0]
    problems = index_problems(db) or content_problems(db)
    k = CLOSURE_K["full"]
    for mode in ("lite", "full"):
        manifest = HealthcareAdapter().load(mode)
        found = check_manifest(db, manifest, k, subset=mode == "lite")
        problems += [f"{mode}: {p}" for p in found]
    db.close()
    return rows, problems
