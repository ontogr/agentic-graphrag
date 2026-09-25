"""Build the answer-quality corpus from the FinQA test split.

Run it once to regenerate the committed fixture:

    uv run python tests/fixtures/eval/answer_quality/build_finqa_corpus.py \
        --source path/to/FinQA/dataset/test.json

It writes the pages in ``_CHOSEN_IDS`` as Markdown under ``documents/`` and their
questions to ``questions.jsonl``.

The agent reads only the first 200 characters of each chunk, so each chosen
question must have its gold figures inside one such preview. ``build`` checks
this with the chunker that ingestion uses. The pages have few chunks, which keeps
extraction and resolution short.
"""

import argparse
import json
import re
from pathlib import Path

from agrag.chunking import default_chunker


_HERE = Path(__file__).parent
_PREVIEW_CHARACTERS = 200
_CHOSEN_IDS = (
    "FIS/2012/page_48.pdf-1",
    "FIS/2012/page_48.pdf-2",
)
_NUMBER = re.compile(r"\d[\d,]*\.?\d*")


def _markdown_table(rows: list[list[str]]) -> str:
    """Render a FinQA table, whose first row is the header, as Markdown."""
    header, *body = rows
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines)


def _document(example: dict) -> str:
    """Join the text before the table, the table and the text after it."""
    return "\n\n".join(
        [
            *example["pre_text"],
            _markdown_table(example["table"]),
            *example["post_text"],
        ]
    )


def _reference(question: str, answer: str) -> str:
    """Return the reference sentence for one question."""
    return f'The answer to "{question.strip()}" is {answer.strip()}.'


def _answerable_from_preview(example: dict, text: str) -> bool:
    """Tell whether one chunk preview holds every gold figure of the question."""
    figures = {
        number.strip(",.")
        for evidence in example["qa"]["gold_inds"].values()
        for number in _NUMBER.findall(evidence)
    }
    figures = {figure for figure in figures if len(figure) >= 2}
    previews = [
        chunk.text[:_PREVIEW_CHARACTERS] for chunk in default_chunker().chunk(text)
    ]
    return bool(figures) and any(
        all(figure in preview for figure in figures) for preview in previews
    )


def build(source: Path) -> None:
    """Write the documents and questions from ``source`` into this folder.

    Raises:
        ValueError: A chosen id is missing from ``source``, or its answer is not
            inside a chunk preview.
    """
    by_id = {example["id"]: example for example in json.loads(source.read_text())}
    missing = [item for item in _CHOSEN_IDS if item not in by_id]
    if missing:
        raise ValueError(f"ids not in {source}: {missing}")

    documents = _HERE / "documents"
    documents.mkdir(exist_ok=True)
    for stale in documents.glob("*.md"):
        stale.unlink()
    questions = []
    for example_id in _CHOSEN_IDS:
        example = by_id[example_id]
        text = _document(example)
        if not _answerable_from_preview(example, text):
            raise ValueError(f"{example_id} is not answerable from chunk previews")
        document_id = example["filename"].removesuffix(".pdf").replace("/", "_")
        (documents / f"{document_id}.md").write_text(text + "\n")
        qa = example["qa"]
        questions.append(
            {
                "id": example_id,
                "document": f"{document_id}.md",
                "question": qa["question"],
                "reference": _reference(qa["question"], qa["answer"]),
            }
        )
    (_HERE / "questions.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in questions)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True, help="FinQA test.json")
    build(parser.parse_args().source)
