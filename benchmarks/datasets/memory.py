"""BEAM: questions about what a long chat said, with one graph per conversation.

The fixture lists the probing questions, their rubrics and the hash of each session
document. The chat text comes from a pinned Hugging Face revision at run time. Each
session of a conversation is one document. Only the chat is ingested, never the
plan, the profile or the reference answers that the dataset holds beside it.
"""

import ast
import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from agrag.common.data_models.document import Document
from agrag.common.data_models.graph_schema import GraphSchema
from benchmarks.datasets.base import DatasetAdapter, Domain, text_document
from benchmarks.datasets.fetch import HashMismatchError, fetch_hf_file
from benchmarks.grading.beam import BeamGrader
from benchmarks.models import Corpus, CorpusManifest, Mode
from benchmarks.schemas.memory import MEMORY


DATASET_NAME = "beam"
REPO = "Mohammadta/BEAM"
REVISION = "3205395e897e7318c7b094ef4e6047b9b82dbb03"
PARQUET_FILE = "data/100K-00000-of-00001.parquet"
PARQUET_SHA256 = "c0519be25907005ba873c927c50877471d550873039d96c041554d0075a78ace"
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "memory"


@dataclass(frozen=True)
class RunawayMessage:
    """An assistant message that degenerated into generated filler.

    Attributes:
        conversation: The conversation id.
        message: The message id within the conversation.
        keep_chars: The characters kept from the start of the message.
        original_chars: The length of the original message.
        original_sha256: The hash of the original message, checked before a cut.
    """

    conversation: str
    message: int
    keep_chars: int
    original_chars: int
    original_sha256: str


# The only runaway message in the conversations that the full set uses. Its ASCII
# drawing turns into 345,211 spaces of indentation.
RUNAWAY_MESSAGES = [
    RunawayMessage(
        conversation="4",
        message=97,
        keep_chars=1470,
        original_chars=348_853,
        original_sha256=(
            "f395a89214d8b2b6f226e6ae3f0e4f3727222d55223fef10ea76405af865ed73"
        ),
    )
]


def collapse_runaway(content: str, runaway: RunawayMessage) -> str:
    """Cut a runaway message after its last sound text and add a short marker.

    Raises:
        HashMismatchError: The message differs from the pinned original.
    """
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if digest != runaway.original_sha256:
        raise HashMismatchError(
            f"message {runaway.message} of conversation {runaway.conversation}: "
            f"expected {runaway.original_sha256}, got {digest}"
        )
    return (
        f"{content[: runaway.keep_chars]}\n"
        f"[{runaway.original_chars - runaway.keep_chars} characters of repeated "
        "output removed]"
    )


def session_text(
    number: int,
    messages: Sequence[dict[str, Any]],
    conversation: str = "",
    *,
    date: str | None = None,
) -> str:
    """Build the text of one session from its messages.

    The first line names the session and its date. Each turn follows as
    ``[msg <id> | <role>] <text>``, in chat order. A message listed in
    ``RUNAWAY_MESSAGES`` is cut. All other text is kept as it is.

    Args:
        number: The session number.
        messages: The messages to include, in chat order.
        conversation: The conversation id, to find runaway messages.
        date: The date of the session. By default it is the date of the first
            message, which is the session date only when ``messages`` starts the
            session. Pass it for a selection of messages from the middle.
    """
    collapsed = {(r.conversation, r.message): r for r in RUNAWAY_MESSAGES}
    lines = [f"Session {number}, date: {date or messages[0]['time_anchor']}"]
    for message in messages:
        content = message["content"]
        runaway = collapsed.get((conversation, message["id"]))
        if runaway:
            content = collapse_runaway(content, runaway)
        lines.append(f"[msg {message['id']} | {message['role']}] {content}")
    return "\n\n".join(lines)


def text_sha256(text: str) -> str:
    """Return the SHA-256 of a document text as UTF-8."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_rows(columns: Sequence[str] | None = None) -> dict[str, dict[str, Any]]:
    """Fetch the BEAM 100K file and return its rows by conversation id.

    Raises:
        HashMismatchError: The fetched file differs from its pinned hash.
    """
    path = fetch_hf_file(REPO, PARQUET_FILE, revision=REVISION, sha256=PARQUET_SHA256)
    table = pq.read_table(path, columns=list(columns) if columns else None)
    return {row["conversation_id"]: row for row in table.to_pylist()}


def probes(row: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return the probing questions of a row, by ability.

    The dataset stores them as the text of a Python literal, not as JSON.
    """
    return ast.literal_eval(row["probing_questions"])


def session_document_text(
    session: Sequence[dict[str, Any]],
    number: int,
    conversation: str,
    message_ids: Sequence[int] | None = None,
) -> str:
    """Build the text of one session, or of chosen messages of it.

    Args:
        session: All the messages of the session.
        number: The session number.
        conversation: The conversation id.
        message_ids: The ids of the messages to keep, or None to keep them all.
    """
    if message_ids is None:
        return session_text(number, session, conversation)
    chosen = [m for m in session if m["id"] in message_ids]
    return session_text(number, chosen, conversation, date=session[0]["time_anchor"])


def document_source(
    conversation: str, session: int, message_ids: Sequence[int] | None = None
) -> str:
    """Return where the fetch step gets one session, or chosen messages of it."""
    source = (
        f"hf://datasets/{REPO}@{REVISION}/{PARQUET_FILE}"
        f"#conversation={conversation};session={session}"
    )
    if message_ids is not None:
        source += ";messages=" + ",".join(map(str, message_ids))
    return source


class MemoryAdapter(DatasetAdapter):
    """The lite and full selections of BEAM."""

    def load(self, mode: Mode) -> CorpusManifest:
        """Return the manifest of one mode from its fixture."""
        text = (FIXTURE_DIR / f"{mode}.json").read_text(encoding="utf-8")
        return CorpusManifest.model_validate_json(text)

    def documents(self, corpus: Corpus) -> Sequence[Document]:
        """Fetch the chat and build one document per session.

        Raises:
            HashMismatchError: The file, a runaway message or a session differs
                from its pinned hash.
        """
        conversation = corpus.id.removeprefix("conv")
        row = load_rows(["conversation_id", "chat"])[conversation]
        documents = []
        for entry in corpus.documents:
            number = int(entry.id.rsplit("-s", 1)[1])
            text = session_document_text(
                row["chat"][number - 1], number, conversation, entry.messages
            )
            if text_sha256(text) != entry.sha256:
                raise HashMismatchError(f"{entry.id}: text differs from the fixture")
            documents.append(text_document(text, uri=entry.uri, title=entry.id))
        return documents

    def schema(self, corpus: Corpus) -> GraphSchema:
        """Return the memory schema, which every conversation shares."""
        return MEMORY


DOMAIN = Domain(
    adapter=MemoryAdapter(),
    grader=BeamGrader(),
    full_grader=BeamGrader(full=True),
)
