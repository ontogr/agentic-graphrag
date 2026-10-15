"""Build the connected-memory evidence fixture from the pinned legal and BEAM sources.

The fixture holds question ids, spans, hashes and authored edits. Source text is
fetched at the pinned revisions and checked against the hashes here. The text the
agent system indexes is produced by the same loader calls that ``Graph.update``
uses for inline text. Every span is checked against that text, and a span that
does not read back is relocated only when its answer occurs exactly once.

Writes ``benchmarks/fixtures/connected_memory/manifest.json``. The NOTICE file in
that folder is written by hand.

Usage:
    uv run python -m benchmarks.fixtures.builders.connected_memory
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, TypedDict

import pyarrow.parquet as pq

from agrag.common.data_models.document import Document, SourceFormat
from agrag.loaders.common import build_prose_document, text_sections
from agrag.loaders.types import ReadOptions, SourceRef
from agrag.loaders.walk import normalize_inline_text
from benchmarks.datasets.fetch import fetch_hf_file
from benchmarks.datasets.legal import REPO as LEGAL_REPO
from benchmarks.datasets.legal import REVISION as LEGAL_REVISION
from benchmarks.datasets.memory import (
    PARQUET_FILE,
    PARQUET_SHA256,
    session_document_text,
)
from benchmarks.datasets.memory import REPO as BEAM_REPO
from benchmarks.datasets.memory import REVISION as BEAM_REVISION


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "connected_memory"
MANIFEST_PATH = FIXTURE_DIR / "manifest.json"
LEGAL_FIXTURE = FIXTURE_DIR.parent / "legal" / "full.json"
MEMORY_FIXTURE = FIXTURE_DIR.parent / "memory" / "lite.json"

KEEP = "privacy_qa/Keep.txt"
VIBER = "privacy_qa/Viber Messenger.txt"
KENWAY = "contractnli/Kenway-NDA-Form-Blank.txt"
LEGAL_URIS = (KEEP, VIBER, KENWAY)
MEMORY_URIS = ("beam/17/session-1", "beam/17/session-3")
# Forbidden words of the no-support case, matched as substrings without case.
TIME_LIMIT_WORDS = ("hours", "days")
BREACH_TIME_LIMIT = re.compile(
    r"\b(hours?|days?|weeks?|months?|within|promptly|immediately)\b", re.IGNORECASE
)
MESSAGE_HEADER = re.compile(r"\[msg (\d+) \| (user|assistant)\]")


# Evidence for the cross-session questions, by question id. Each entry names the
# excerpt that carries the evidence and the phrase that shows each rubric item, as
# the excerpt words it. A unique entry must occur exactly once in that excerpt.
# Only offsets and hashes are stored.
class QuestionEvidence(TypedDict):
    """The excerpt that carries a question's evidence and the phrases that show it."""

    document: str
    unique: bool
    phrases: dict[str, str]


QUESTION_EVIDENCE: dict[str, QuestionEvidence] = {
    "conv17:information_extraction:0": {
        "document": "beam/17/session-1",
        "unique": True,
        "phrases": {"on Tuesdays and Thursdays": "Tuesdays and Thursdays"},
    },
    "conv17:multi_session_reasoning:0": {
        "document": "beam/17/session-3",
        "unique": False,
        "phrases": {
            "had filmed 12 scenes": "12 of 16 scenes filmed",
            "had 4 scenes left to film": "Remaining Scenes:** 4 scenes",
        },
    },
}

# Edits are authored here. Each is applied once to its base version.
MUTATIONS = [
    {
        "id": "M1",
        "base": KEEP,
        "description": (
            "Replaces the sentence on not selling personal information inside the "
            "cited span of the first privacy-sharing answer, with a different length."
        ),
        "old": "we will not sell your personal information",
        "new": "we may share your personal information with advertising partners",
    },
    {
        "id": "M2",
        "base": KEEP,
        "description": "Appends one line after the last line of the policy.",
        "old": "",
        "new": "This line was appended to the policy text for the change check.\n",
    },
    {
        "id": "M3",
        "base": VIBER,
        "description": (
            "Changes the sentence on where recipients are located, near the end of the "
            "policy, after every labelled Viber span. No case cites this document in "
            "the source-change review."
        ),
        "old": "the recipients above may be located outside",
        "new": "the recipients above are located outside",
    },
]

CASE_QUESTIONS = {
    "multi_source_evidence": (
        "Do the Keep and Viber Messenger privacy policies say whether personal "
        "information is sold or shared with third parties?"
    ),
    "multi_source_evidence_holdout": (
        "Do the Keep and Viber Messenger privacy policies say users' personal "
        "information may be shared with other parties?"
    ),
    "insufficient_evidence": (
        "Consider Keep's privacy policy: within how many hours must Keep tell me about "
        "a data breach?"
    ),
    "insufficient_evidence_holdout": (
        "Does Keep's privacy policy give a deadline for notifying me after a data "
        "breach?"
    ),
    "cross_session_recall_holdout": (
        "By July 5, how many scenes had I already filmed, and how many remained?"
    ),
    "interruption_and_resume": "Assess what Keep shares.",
    "interruption_and_resume_holdout": (
        "Assess what Keep shares with third parties, one step at a time."
    ),
}
DECISIONS = {
    "D1": "Keep does not sell personal information.",
    "D2": "Kenway's confidentiality obligations survive termination.",
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _occurrences(text: str, needle: str) -> list[int]:
    """Return the start of every occurrence of a non-empty needle.

    Occurrences may overlap, so ``"aa"`` occurs twice in ``"aaa"``.
    """
    return [m.start() for m in re.finditer(f"(?={re.escape(needle)})", text)]


def locate_answer(
    text: str, char_start: int, char_end: int, answer: str
) -> tuple[int, int]:
    """Return the range of an answer in a text, keeping the stored range if it fits.

    Args:
        text: The text the span indexes.
        char_start: The stored start of the span.
        char_end: The stored end of the span.
        answer: The answer string the span is labelled with.

    Returns:
        The stored range when ``text[char_start:char_end]`` equals the answer,
        otherwise the range of the single occurrence of the answer.

    Raises:
        ValueError: The answer occurs zero times or more than once.
    """
    if text[char_start:char_end] == answer:
        return char_start, char_end
    occurrences = _occurrences(text, answer)
    if len(occurrences) != 1:
        raise ValueError(
            f"answer occurs {len(occurrences)} times, expected exactly one"
        )
    start = occurrences[0]
    return start, start + len(answer)


def move_span(
    char_start: int,
    char_end: int,
    answer: str,
    *,
    edit_start: int,
    old: str,
    new: str,
) -> tuple[int, int, str]:
    """Return a span and its answer after one replacement in its text.

    A span that ends at or before the edit keeps its place. A span that starts at or
    after the edit shifts by the change in length. A span that contains the edit keeps
    its start, its end moves, and its answer takes the replacement.

    Raises:
        ValueError: The edit overlaps the span only partly, or the answer does not
            contain the replaced text exactly once.
    """
    edit_end = edit_start + len(old)
    delta = len(new) - len(old)
    if char_end <= edit_start:
        return char_start, char_end, answer
    if char_start >= edit_end:
        return char_start + delta, char_end + delta, answer
    if char_start <= edit_start and char_end >= edit_end and old:
        if len(_occurrences(answer, old)) != 1:
            raise ValueError("the replaced text occurs in the answer not exactly once")
        return char_start, char_end + delta, answer.replace(old, new)
    raise ValueError("an edit partly overlaps a span")


def apply_edit(text: str, old: str, new: str) -> tuple[str, int]:
    """Apply one replacement and return the new text and where the edit starts.

    An empty ``old`` appends ``new`` at the end. Both forms require that ``new`` does
    not already occur in the text, and a replaced ``old`` occurs exactly once.

    Raises:
        ValueError: ``old`` does not occur once, or ``new`` already occurs.
    """
    if old:
        occurrences = _occurrences(text, old)
        if len(occurrences) != 1:
            raise ValueError(
                f"the edited text occurs {len(occurrences)} times, expected once"
            )
        start = occurrences[0]
    else:
        start = len(text)
    if new in text:
        raise ValueError("the new text already occurs in the document")
    return text[:start] + new + text[start + len(old) :], start


def loader_document(uri: str, text: str) -> Document:
    """Build the document the agent system indexes for inline text.

    This follows ``Graph.update(text=...)`` in ``agrag/ingestion/_ingest.py``.
    """
    opts = ReadOptions()
    normalized, normalization = normalize_inline_text(text, opts)
    document = build_prose_document(
        source=SourceRef(uri=uri, extension=".txt"),
        text=normalized,
        encoding="utf-8",
        source_format=SourceFormat.TXT,
        loader_name="inline",
        opts=opts,
        title="inline",
        sections=text_sections(normalized),
    )
    return document.model_copy(
        update={"normalization": normalization, "document_key": uri}
    )


def _query(labels: dict[str, dict[str, Any]], question_id: str) -> str:
    """Return the question text of a labelled question, as it is sent to a system."""
    return labels[question_id]["messages"][0]["content"]


def _label_support(
    labels: dict[str, dict[str, Any]],
    question_id: str,
    uri: str,
    text: str,
    spans: list[tuple[int, int]],
    *,
    role: str,
) -> list[dict[str, Any]]:
    """Return the spans of one labelled question, checked against the text."""
    records = []
    for label_start, label_end in spans:
        snippet = next(
            (
                s
                for s in labels[question_id]["reference"]["snippets"]
                if s["uri"] == uri and s["span"] == [label_start, label_end]
            ),
            None,
        )
        if snippet is None:
            raise SystemExit(f"{question_id} has no span {(label_start, label_end)}")
        answer = snippet["answer"]
        start, end = locate_answer(text, label_start, label_end, answer)
        records.append(
            {
                "role": role,
                "question_id": question_id,
                "document": uri,
                "char_start": start,
                "char_end": end,
                "label_char_start": label_start,
                "label_char_end": label_end,
                "shift": start - label_start,
                "text_sha256": _sha(text[start:end]),
                "answer": answer,
                "snippet_start": answer[:40],
            }
        )
    return records


def _phrase_matches(text: str, phrase: str) -> list[dict[str, Any]]:
    """Return each occurrence of a phrase with the message that holds it."""
    headers = [
        (m.start(), int(m.group(1)), m.group(2)) for m in MESSAGE_HEADER.finditer(text)
    ]
    matches = []
    for start in _occurrences(text, phrase):
        end = start + len(phrase)
        _, message_id, speaker = max(h for h in headers if h[0] <= start)
        matches.append(
            {
                "message_id": message_id,
                "speaker": speaker,
                "char_start": start,
                "char_end": end,
                "text_sha256": _sha(text[start:end]),
            }
        )
    return matches


def _question_support(texts: dict[str, str]) -> list[dict[str, Any]]:
    """Locate each question's evidence in its own excerpt, one record per occurrence.

    A unique entry must occur exactly once. Every other phrase needs at least one
    occurrence. Each record also counts the phrase in the other excerpt, which the
    distractor check relies on.
    """
    records = []
    for question_id, evidence in QUESTION_EVIDENCE.items():
        home = evidence["document"]
        others = [uri for uri in MEMORY_URIS if uri != home]
        for rubric_item, phrase in evidence["phrases"].items():
            matches = _phrase_matches(texts[home], phrase)
            if not matches:
                raise SystemExit(f"evidence not in {home}: {rubric_item}")
            if evidence["unique"] and len(matches) != 1:
                raise SystemExit(f"evidence is not unique in {home}: {rubric_item}")
            other_count = sum(len(_phrase_matches(texts[u], phrase)) for u in others)
            records += [
                {
                    "role": rubric_item,
                    "question_id": question_id,
                    "document": home,
                    "distractor_matches_in_other_excerpt": other_count,
                    **match,
                }
                for match in matches
            ]
    return records


def _cases(
    labels: dict[str, dict[str, Any]],
    texts: dict[str, str],
    memory_questions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return the six cases with their support and hold-out variants."""
    keep, viber, kenway = texts[KEEP], texts[VIBER], texts[KENWAY]
    return [
        {
            "id": "source_span_retrieval",
            "question": _query(labels, "privacy_qa:fdf155d3"),
            "original_question_ids": ["privacy_qa:fdf155d3", "privacy_qa:c96be584"],
            "support": _label_support(
                labels,
                "privacy_qa:fdf155d3",
                KEEP,
                keep,
                [(1221, 1361)],
                role="primary",
            )
            + _label_support(
                labels,
                "privacy_qa:c96be584",
                KEEP,
                keep,
                [(4004, 4911), (4956, 5177)],
                role="second",
            ),
            "holdout": {
                "question_id": "privacy_qa:57d091ce",
                "question": _query(labels, "privacy_qa:57d091ce"),
                "support": _label_support(
                    labels,
                    "privacy_qa:57d091ce",
                    KEEP,
                    keep,
                    [(4004, 4517), (4807, 5177)],
                    role="primary",
                ),
            },
        },
        {
            "id": "multi_source_evidence",
            "question": CASE_QUESTIONS["multi_source_evidence"],
            "original_question_ids": ["privacy_qa:c96be584", "privacy_qa:58624fcb"],
            "support": _label_support(
                labels, "privacy_qa:c96be584", KEEP, keep, [(4004, 4911)], role="keep"
            )
            + _label_support(
                labels,
                "privacy_qa:58624fcb",
                VIBER,
                viber,
                [(11655, 15357)],
                role="viber",
            ),
            "holdout": {
                "question": CASE_QUESTIONS["multi_source_evidence_holdout"],
                "original_question_ids": [
                    "privacy_qa:57d091ce",
                    "privacy_qa:440fda49",
                ],
                "support": _label_support(
                    labels,
                    "privacy_qa:57d091ce",
                    KEEP,
                    keep,
                    [(4004, 4517), (4807, 5177)],
                    role="keep",
                )
                + _label_support(
                    labels,
                    "privacy_qa:440fda49",
                    VIBER,
                    viber,
                    [(11655, 14803)],
                    role="viber",
                ),
            },
        },
        {
            "id": "insufficient_evidence",
            "question": CASE_QUESTIONS["insufficient_evidence"],
            "original_question_ids": [],
            "support": [],
            "holdout": {
                "question": CASE_QUESTIONS["insufficient_evidence_holdout"],
                "support": [],
            },
        },
        {
            "id": "cross_session_recall",
            "questions": [
                {
                    "question_id": question_id,
                    "question": memory_questions[question_id]["messages"][0]["content"],
                    "rubric": memory_questions[question_id]["reference"]["rubric"],
                    "support_document": evidence["document"],
                    "must_not_cite": [
                        uri for uri in MEMORY_URIS if uri != evidence["document"]
                    ],
                }
                for question_id, evidence in QUESTION_EVIDENCE.items()
            ],
            "original_question_ids": list(QUESTION_EVIDENCE),
            "support": _question_support(texts),
            "holdout": {"question": CASE_QUESTIONS["cross_session_recall_holdout"]},
        },
        {
            "id": "interruption_and_resume",
            "question": CASE_QUESTIONS["interruption_and_resume"],
            "original_question_ids": [],
            "steps": {
                "A": "reads the first Keep span of the first question",
                "B": "reads the second Keep span of the second question",
            },
            "checkpoint": {"completed": ["A"], "pending": ["B"]},
            "support": _label_support(
                labels, "privacy_qa:fdf155d3", KEEP, keep, [(1221, 1361)], role="A"
            )
            + _label_support(
                labels, "privacy_qa:c96be584", KEEP, keep, [(4956, 5177)], role="B"
            ),
            "holdout": {"question": CASE_QUESTIONS["interruption_and_resume_holdout"]},
        },
        {
            "id": "source_change_review",
            "decisions": DECISIONS,
            "original_question_ids": ["privacy_qa:c96be584", "contractnli:15378f01"],
            "support": _label_support(
                labels, "privacy_qa:c96be584", KEEP, keep, [(4004, 4911)], role="D1"
            )
            + _label_support(
                labels,
                "contractnli:15378f01",
                KENWAY,
                kenway,
                [(10289, 10403), (13679, 13900), (14063, 14179)],
                role="D2",
            ),
            "mutations": ["M1", "M2", "M3"],
            "unrelated_mutation": "M3",
            "holdout": {"mutation": "M2"},
        },
    ]


def _spans_of(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every span of a case, the main variant and its hold-out."""
    spans = list(case["support"])
    if "support" in case["holdout"]:
        spans += case["holdout"]["support"]
    return spans


def _after_edit(
    mutation: dict[str, Any], base_text: str, cases: list[dict[str, Any]]
) -> tuple[str, list[dict[str, Any]]]:
    """Apply a mutation and recompute every span of its base document."""
    edited, edit_start = apply_edit(base_text, mutation["old"], mutation["new"])
    spans_after = []
    for case in cases:
        for span in _spans_of(case):
            if span["document"] != mutation["base"]:
                continue
            start, end, answer_after = move_span(
                span["char_start"],
                span["char_end"],
                span.get("answer") or "",
                edit_start=edit_start,
                old=mutation["old"],
                new=mutation["new"],
            )
            if span.get("answer") is not None and edited[start:end] != answer_after:
                raise SystemExit(f"recomputed span does not read back: {case['id']}")
            spans_after.append(
                {
                    "case": case["id"],
                    "role": span["role"],
                    "document": span["document"],
                    "v1_char_start": span["char_start"],
                    "v1_char_end": span["char_end"],
                    "char_start": start,
                    "char_end": end,
                    "moved": (start, end) != (span["char_start"], span["char_end"]),
                    "answer_after": answer_after if span.get("answer") else None,
                    "text_sha256_after": _sha(edited[start:end]),
                }
            )
    return edited, spans_after


def _check_unrelated_edits(
    cases: list[dict[str, Any]], mutations: list[dict[str, Any]]
) -> None:
    """Raise when an edit declared unrelated touches a cited document or span.

    A case names its unrelated edit with ``unrelated_mutation``. The edited document
    must not be cited by that case, and the edit must lie outside every span that
    any case cites from that document.
    """
    mutations_by_id = {mutation["id"]: mutation for mutation in mutations}
    for case in cases:
        if "unrelated_mutation" not in case:
            continue
        mutation = mutations_by_id[case["unrelated_mutation"]]
        if mutation["base"] in {span["document"] for span in _spans_of(case)}:
            raise SystemExit(
                f"{mutation['id']} edits a document that {case['id']} cites"
            )
        edit = mutation["edit"]
        edit_end = edit["char_start"] + len(edit["old"])
        for other in cases:
            for span in _spans_of(other):
                if span["document"] != mutation["base"]:
                    continue
                overlaps = (
                    span["char_start"] < edit_end
                    and edit["char_start"] < span["char_end"]
                )
                if overlaps:
                    raise SystemExit(
                        f"{mutation['id']} overlaps a span of {other['id']}"
                    )


def _breach_lines(uri: str, text: str) -> list[dict[str, Any]]:
    """Return each line that mentions breach, with any time-limit words it has."""
    line_ranges: dict[int, int] = {}
    for match in re.finditer("breach", text, flags=re.IGNORECASE):
        start = text.rfind("\n", 0, match.start()) + 1
        end = text.find("\n", match.end())
        line_ranges[start] = len(text) if end == -1 else end
    lines = []
    for start, end in sorted(line_ranges.items()):
        line = text[start:end]
        words = sorted({m.group(0).lower() for m in BREACH_TIME_LIMIT.finditer(line)})
        lines.append(
            {
                "document": uri,
                "char_start": start,
                "char_end": end,
                "text_sha256": _sha(line),
                "time_limit_terms": words,
            }
        )
    return lines


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    """Write the manifest after every self-check passes."""
    legal = _load_json(LEGAL_FIXTURE)
    legal_entries = {d["uri"]: d for d in legal["corpora"][0]["documents"]}
    labels = {q["id"]: q for q in legal["questions"]}
    memory = _load_json(MEMORY_FIXTURE)
    memory_entries = {d["uri"]: d for d in memory["corpora"][0]["documents"]}
    memory_questions = {
        q["id"]: q for q in memory["questions"] if q["id"] in QUESTION_EVIDENCE
    }

    texts: dict[str, str] = {}
    documents = []
    for uri in LEGAL_URIS:
        path = fetch_hf_file(
            LEGAL_REPO,
            f"corpus/{uri}",
            revision=LEGAL_REVISION,
            sha256=legal_entries[uri]["sha256"],
        )
        text = path.read_text(encoding="utf-8")
        document = loader_document(uri, text)
        if document.text != text:
            raise SystemExit(f"loader path changes the text of {uri}")
        texts[uri] = text
        documents.append(
            {
                "uri": uri,
                "corpus": "legal",
                "source": legal_entries[uri]["source"],
                "sha256": legal_entries[uri]["sha256"],
                "content_sha256": document.content_hash,
                "char_count": len(text),
            }
        )

    chat_rows = {
        row["conversation_id"]: row
        for row in pq.read_table(
            fetch_hf_file(
                BEAM_REPO,
                PARQUET_FILE,
                revision=BEAM_REVISION,
                sha256=PARQUET_SHA256,
            ),
            columns=["conversation_id", "chat"],
        ).to_pylist()
    }
    for uri in MEMORY_URIS:
        entry = memory_entries[uri]
        _, conversation, session_label = uri.split("/")
        number = int(session_label.removeprefix("session-"))
        text = session_document_text(
            chat_rows[conversation]["chat"][number - 1],
            number,
            conversation,
            entry["messages"],
        )
        document = loader_document(uri, text)
        if document.text != text or _sha(text) != entry["sha256"]:
            raise SystemExit(f"session text differs from its fixture: {uri}")
        texts[uri] = text
        documents.append(
            {
                "uri": uri,
                "corpus": "memory",
                "source": entry["source"],
                "sha256": entry["sha256"],
                "content_sha256": document.content_hash,
                "char_count": len(text),
                "messages": entry["messages"],
            }
        )

    for word in TIME_LIMIT_WORDS:
        for uri in LEGAL_URIS:
            if word in texts[uri].lower():
                raise SystemExit(f"{word!r} occurs in {uri}; the no-support case fails")
    if "breach" in texts[KEEP].lower():
        raise SystemExit("'breach' occurs in Keep; the no-support case fails")
    breach_lines = [
        line for uri in (VIBER, KENWAY) for line in _breach_lines(uri, texts[uri])
    ]
    if any(line["time_limit_terms"] for line in breach_lines):
        raise SystemExit("a breach line names a time limit; read it before the case")

    cases = _cases(labels, texts, memory_questions)
    mutations = []
    for spec in MUTATIONS:
        base = texts[spec["base"]]
        edited, spans_after = _after_edit(spec, base, cases)
        if loader_document(spec["base"], edited).text != edited:
            raise SystemExit(f"loader path changes the edited text of {spec['id']}")
        _, edit_start = apply_edit(base, spec["old"], spec["new"])
        mutations.append(
            {
                "id": spec["id"],
                "base": spec["base"],
                "base_content_sha256": _sha(base),
                "description": spec["description"],
                "edit": {
                    "char_start": edit_start,
                    "old": spec["old"],
                    "new": spec["new"],
                    "delta": len(spec["new"]) - len(spec["old"]),
                },
                "content_sha256": _sha(edited),
                "char_count": len(edited),
                "spans_after": spans_after,
            }
        )
    _check_unrelated_edits(cases, mutations)
    relocated = [
        {
            "question_id": span["question_id"],
            "label_char_start": span["label_char_start"],
            "char_start": span["char_start"],
            "shift": span["shift"],
        }
        for case in cases
        for span in _spans_of(case)
        if span.get("shift")
    ]
    manifest = {
        "name": "connected-memory-evidence",
        "upstream": {
            "legal": {"repo": LEGAL_REPO, "revision": LEGAL_REVISION},
            "memory": {
                "repo": BEAM_REPO,
                "revision": BEAM_REVISION,
                "file": PARQUET_FILE,
                "file_sha256": PARQUET_SHA256,
            },
        },
        "documents": documents,
        "cases": cases,
        "mutations": mutations,
        "self_checks": {
            "word_counts": {
                uri: {word: texts[uri].lower().count(word) for word in TIME_LIMIT_WORDS}
                | {"breach": texts[uri].lower().count("breach")}
                for uri in LEGAL_URIS
            },
            "breach_lines": breach_lines,
            "relocated_spans": relocated,
        },
    }
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"{len(documents)} documents, {len(cases)} cases, {len(mutations)} mutations")


if __name__ == "__main__":
    main()
