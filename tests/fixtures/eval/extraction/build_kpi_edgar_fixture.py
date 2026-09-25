"""Build the extraction gold fixture from a local clone of KPI-EDGAR.

Usage::

    git clone https://github.com/tobideusser/kpi-edgar /tmp/kpi-edgar
    uv run python tests/fixtures/eval/extraction/build_kpi_edgar_fixture.py \
        --source /tmp/kpi-edgar

KPI-EDGAR annotates word-index spans over a tokenized sentence. The script
keeps the sentence text as written and converts each span to character offsets
by scanning the text word by word. The script stops when a picked sentence has
words that do not match its text, or a converted span that does not read back as
the words it came from.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from agrag.common.data_models.extraction import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType
from agrag.eval import ExtractionGold


logger = logging.getLogger(__name__)

HERE = Path(__file__).parent
RELATION_LABEL = "RELATED_VALUE"
SOURCE_RELATION_LABEL = "matches"

# Test-split sentences picked by hand. Together they cover every entity type
# and every entity pair that the test split links, and add common cases (a KPI
# with current, prior and earlier year values) from many filings. The set is
# small because every extractor run costs one LLM call per sentence.
PICKED_IDS = [
    "AMZN_10-K_0001018724-21-000004.txt_59_1",
    "AMZN_10-K_0001018724-20-000004.txt_28_9",
    "CVX_10-K_0000093410-21-000009.txt_86_1",
    "TSLA_10-K_0001564590-20-004475.txt_13_1",
    "TSLA_10-K_0001564590-21-004599.txt_12_1",
    "CVX_10-K_0000093410-21-000009.txt_90_2",
    "TSLA_10-K_0001564590-21-004599.txt_32_0",
    "TSLA_10-K_0001564590-20-004475.txt_86_8",
    "PEP_10-K_0000077476-21-000007.txt_54_11",
    "PFE_10-K_0000078003-21-000038.txt_46_2",
    "UNH_10-K_0000731766-21-000013.txt_8_6",
    "PEP_10-K_0000077476-21-000007.txt_12_1",
    "PFE_10-K_0000078003-21-000038.txt_28_1",
    "MSFT_10-K_0001564590-21-039151.txt_9_2",
    "UNH_10-K_0000731766-21-000013.txt_8_5",
    "DHR_10-K_0000313616-20-000041.txt_11_2",
    "MSFT_10-K_0001564590-21-039151.txt_48_0",
    "ADBE_10-K_0000796343-20-000013.txt_13_1",
]

# Entity definitions follow Table I of Deusser et al., "KPI-EDGAR: A Novel
# Dataset and Accompanying Metric for Relation Extraction from Financial
# Documents" (arXiv 2210.09163) and the annotation guide in kpi_edgar.xlsx.
# The guide marks a value as the number alone, so the descriptions say to leave
# out the currency sign and the scale word. An extractor cannot guess that.
_VALUE = (
    "Only the number, without a currency sign or a scale word such as million. "
    "Not a forecast or a limit that the company sets."
)
ENTITY_DESCRIPTIONS = {
    "kpi": (
        "Key performance indicator expressible in numerical and monetary value, "
        "such as revenue or net sales. Every word of the KPI name."
    ),
    "cy": f"The current year value of a KPI. {_VALUE}",
    "py": f"The prior year value of a KPI (current year minus 1). {_VALUE}",
    "py1": f"The value of a KPI two years before the current year. {_VALUE}",
    "increase": (
        "The number that gives an increase of a KPI from the previous year to "
        "the current year. Only the number, without a currency sign or a scale word."
    ),
    "increase_py": (
        "The number that gives an increase of a KPI from two years back to the "
        "prior year. Only the number, without a currency sign or a scale word."
    ),
    "decrease": (
        "The number that gives a decrease of a KPI from the previous year to "
        "the current year. Only the number, without a currency sign or a scale word."
    ),
    "decrease_py": (
        "The number that gives a decrease of a KPI from two years back to the "
        "prior year. Only the number, without a currency sign or a scale word."
    ),
    "thereof": (
        "A subordinate KPI: a KPI that is part of another, broader KPI. Every "
        "word of its name."
    ),
    "attr": "Words that further describe a KPI and define its exact name.",
    "kpi_coref": "A co-reference to a KPI mentioned in a previous sentence.",
}
# KPI-EDGAR names these labels differently in the source file.
SOURCE_LABELS = {"increase-py": "increase_py", "decrease-py": "decrease_py"}


def word_offsets(text: str, words: list[str]) -> list[tuple[int, int]] | None:
    """Return the character span of each word, or None if the words do not fit."""
    offsets = []
    cursor = 0
    for word in words:
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if text[cursor : cursor + len(word)] != word:
            return None
        offsets.append((cursor, cursor + len(word)))
        cursor += len(word)
    if text[cursor:].strip():
        return None
    return offsets


def convert_sentence(sentence: dict[str, Any]) -> ExtractionGold | None:
    """Convert one KPI-EDGAR sentence, or return None when it does not round-trip."""
    text = sentence["value"]
    words = [word["value"] for word in sentence["words"]]
    offsets = word_offsets(text, words)
    if offsets is None:
        logger.warning("dropped %s: words do not match text", sentence["unique_id"])
        return None
    chunk_id = uuid5(NAMESPACE_URL, sentence["unique_id"])
    entities = []
    for annotation in sentence["entities_anno"]:
        start, end = annotation["start"], annotation["end"]
        char_start, char_end = offsets[start][0], offsets[end - 1][1]
        span = text[char_start:char_end]
        if "".join(span.split()) != "".join(words[start:end]):
            logger.warning(
                "dropped %s: span does not round-trip", sentence["unique_id"]
            )
            return None
        label = SOURCE_LABELS.get(annotation["type_"], annotation["type_"])
        entities.append(
            ExtractedEntity(
                chunk_id=chunk_id,
                label=label,
                text=span,
                char_start=char_start,
                char_end=char_end,
            )
        )
    relations = []
    for annotation in sentence["relations_anno"] or []:
        if annotation["type_"] != SOURCE_RELATION_LABEL:
            logger.warning("dropped %s: unexpected relation", sentence["unique_id"])
            return None
        relations.append(
            ExtractedRelation(
                chunk_id=chunk_id,
                label=RELATION_LABEL,
                source_index=annotation["head_idx"],
                target_index=annotation["tail_idx"],
            )
        )
    gold = ExtractionResult(
        entities=entities, relations=relations, extractor_name="kpi-edgar"
    )
    return ExtractionGold(id=sentence["unique_id"], text=text, gold=gold)


def picked_sentences(filings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the picked sentences in PICKED_IDS order."""
    by_id = {
        sentence["unique_id"]: sentence
        for filing in filings
        for segment in filing["segments"]
        for sentence in segment["sentences"] or []
    }
    return [by_id[unique_id] for unique_id in PICKED_IDS]


def build_schema(filings: list[dict[str, Any]]) -> GraphSchema:
    """Build the schema. Patterns hold each entity pair the test split links.

    The pairs come from the whole test split, not only the picked sentences, so
    the schema does not change with the pick. Each pair is listed both ways
    because the relation has no direction.
    """
    pairs = set()
    for filing in filings:
        for segment in filing["segments"]:
            for sentence in segment["sentences"] or []:
                if sentence["split_type"] != "test" or not sentence["entities_anno"]:
                    continue
                labels = [
                    SOURCE_LABELS.get(e["type_"], e["type_"])
                    for e in sentence["entities_anno"]
                ]
                for relation in sentence["relations_anno"] or []:
                    source = labels[relation["head_idx"]]
                    target = labels[relation["tail_idx"]]
                    pairs |= {(source, target), (target, source)}
    return GraphSchema(
        name="kpi_edgar",
        version="1",
        entities=[
            EntityType(label=label, description=description)
            for label, description in ENTITY_DESCRIPTIONS.items()
        ],
        relations=[
            RelationType(
                label=RELATION_LABEL,
                description=(
                    "Links a KPI to a value or change that belongs to it. "
                    "The link has no direction."
                ),
                patterns=sorted(pairs),
            )
        ],
    )


def main() -> None:
    """Write the slice and the schema next to this script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="KPI-EDGAR clone")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    filings = json.loads((args.source / "data" / "kpi_edgar.json").read_text())
    items = []
    for sentence in picked_sentences(filings):
        item = convert_sentence(sentence)
        if item is None:
            raise SystemExit(f"cannot convert {sentence['unique_id']}")
        items.append(item)

    (HERE / "kpi_edgar_test_slice.jsonl").write_text(
        "".join(item.model_dump_json() + "\n" for item in items)
    )
    schema = build_schema(filings)
    (HERE / "schema.json").write_text(schema.model_dump_json(indent=2) + "\n")
    logger.info("wrote %d sentences", len(items))


if __name__ == "__main__":
    main()
