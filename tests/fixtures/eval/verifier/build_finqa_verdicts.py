"""Build the verifier calibration items from the FinQA test split.

Run it once to regenerate the committed fixture:

    uv run python tests/fixtures/eval/verifier/build_finqa_verdicts.py \
        --source path/to/FinQA/dataset/test.json

It writes ``verdict_items.jsonl`` (60 items, 20 per verdict) and ``REVIEW.md``, a
sample of the items to check by hand. The FinQA examples are hand-picked: the ids
in the three tuples below are the whole selection, so change a tuple to change
the set. Each item has one question, and its findings state the answer and cite
numbered evidence lines.

- ``PASS``: the cited lines are FinQA's own gold evidence.
- ``INSUFFICIENT``: the same answer claim, but the cited lines are sentences from
  the same page that are not gold evidence and share no number with it.
- ``CONTRADICTORY``: the gold evidence plus one more line that restates the last
  value of a table row with the number scaled by 1.1 to 1.5, so two cited lines
  disagree about the same item.

Every item starts with ``human_reviewed`` false.
"""

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any


_HERE = Path(__file__).parent
_SAMPLE_PER_CLASS = 6
_DISTRACTOR_MIN_CHARS = 60
_DISTRACTOR_MAX_CHARS = 400
_NUMBER = re.compile(r"\d[\d,]*\.?\d*")
_LAST_VALUE = re.compile(r"^(.* is (?:\$ )?)(\d[\d,]*(?:\.\d+)?)( %)? ;$")

_PASS_IDS = (
    "MAS/2012/page_26.pdf-3",
    "BLK/2012/page_33.pdf-1",
    "PPG/2006/page_42.pdf-1",
    "MMM/2013/page_75.pdf-2",
    "ZBH/2009/page_58.pdf-3",
    "GS/2017/page_132.pdf-4",
    "LMT/2014/page_91.pdf-3",
    "JPM/2008/page_117.pdf-1",
    "FIS/2012/page_48.pdf-4",
    "FBHS/2017/page_22.pdf-1",
    "UNP/2009/page_35.pdf-2",
    "PNC/2012/page_68.pdf-3",
    "ANSS/2012/page_93.pdf-1",
    "PPG/2018/page_85.pdf-1",
    "GS/2013/page_85.pdf-1",
    "MAS/2017/page_27.pdf-4",
    "HOLX/2009/page_127.pdf-3",
    "CDW/2015/page_93.pdf-3",
    "MRK/2013/page_125.pdf-4",
    "APD/2018/page_121.pdf-2",
)
_INSUFFICIENT_IDS = (
    "STT/2009/page_127.pdf-4",
    "CMCSA/2008/page_36.pdf-2",
    "AAPL/2003/page_48.pdf-1",
    "ABMD/2007/page_78.pdf-4",
    "DVN/2015/page_79.pdf-2",
    "RSG/2012/page_93.pdf-1",
    "AWK/2013/page_122.pdf-4",
    "DRE/2007/page_56.pdf-2",
    "MS/2013/page_139.pdf-1",
    "INTC/2015/page_41.pdf-2",
    "JKHY/2019/page_18.pdf-3",
    "GPN/2014/page_92.pdf-2",
    "TMUS/2017/page_29.pdf-2",
    "GPN/2010/page_89.pdf-1",
    "CE/2009/page_65.pdf-2",
    "UNP/2016/page_52.pdf-3",
    "SNA/2013/page_83.pdf-3",
    "WRK/2018/page_107.pdf-4",
    "PKG/2013/page_88.pdf-1",
    "ADBE/1999/page_64.pdf-2",
)
_CONTRADICTORY_IDS = (
    "HST/2018/page_135.pdf-1",
    "HOLX/2006/page_71.pdf-1",
    "DISCA/2011/page_49.pdf-3",
    "GPN/2010/page_87.pdf-2",
    "FIS/2016/page_31.pdf-2",
    "ADBE/2008/page_74.pdf-1",
    "BLL/2010/page_37.pdf-4",
    "LMT/2016/page_49.pdf-3",
    "SNA/2012/page_110.pdf-2",
    "MRO/2013/page_19.pdf-1",
    "PNC/2012/page_100.pdf-2",
    "DISCA/2011/page_49.pdf-2",
    "GS/2012/page_121.pdf-2",
    "INTC/2013/page_31.pdf-2",
    "GPN/2013/page_92.pdf-3",
    "JKHY/2019/page_18.pdf-1",
    "UNP/2006/page_15.pdf-4",
    "ADBE/2008/page_89.pdf-2",
    "MMM/2007/page_23.pdf-2",
    "PKG/2002/page_52.pdf-1",
)

_CLASSES = (
    ("PASS", _PASS_IDS),
    ("INSUFFICIENT", _INSUFFICIENT_IDS),
    ("CONTRADICTORY", _CONTRADICTORY_IDS),
)


def _numbers(text: str) -> set[str]:
    """Return the number tokens of a text, without trailing punctuation."""
    return {token.strip(",.") for token in _NUMBER.findall(text)}


def _answer(qa: dict[str, Any]) -> str | None:
    """Return the answer as FinQA states it, or ``None`` when it has none."""
    if qa["answer"]:
        return qa["answer"]
    if qa.get("exe_ans") in (None, ""):
        return None
    return f"{qa['exe_ans']:.4g}"


def _findings(qa: dict[str, Any], answer: str, evidence: list[str]) -> str:
    """Write findings that claim the answer and cite every evidence line."""
    keys = "".join(f"[E{n}]" for n in range(1, len(evidence) + 1))
    lines = "\n".join(f"[E{n}] {text}" for n, text in enumerate(evidence, 1))
    return (
        f"The answer is {answer}, computed as {qa['program']} {keys}.\n\n"
        f"Evidence:\n{lines}"
    )


def _scaled_line(gold: list[str], rng: random.Random) -> str | None:
    """Restate the last value of a gold table row with the number scaled."""
    for text in reversed(gold):
        found = _LAST_VALUE.match(text)
        if not found:
            continue
        prefix, value, percent = found.groups()
        number = float(value.replace(",", ""))
        if number < 1 or (float(number).is_integer() and 1900 <= number <= 2100):
            continue
        decimals = len(value.split(".")[1]) if "." in value else 0
        commas = "," if "," in value else ""
        scaled = f"{number * rng.uniform(1.1, 1.5):{commas}.{decimals}f}"
        if scaled == value:
            continue
        return f"{prefix}{scaled}{percent or ''} ;"
    return None


def _distractors(
    example: dict[str, Any], gold: list[str], answer: str, rng: random.Random
) -> list[str] | None:
    """Pick one or two page sentences that are not gold and share no number."""
    qa = example["qa"]
    gold_numbers = set().union(*(_numbers(text) for text in gold)) | _numbers(answer)
    candidates = [
        sentence
        for sentence in example["pre_text"] + example["post_text"]
        if _DISTRACTOR_MIN_CHARS <= len(sentence) <= _DISTRACTOR_MAX_CHARS
        and sentence not in qa["gold_inds"].values()
        and not _numbers(sentence) & gold_numbers
    ]
    if len(candidates) < 2:
        return None
    return rng.sample(candidates, rng.choice((1, 2)))


def make_item(example: dict[str, Any], label: str) -> dict[str, Any] | None:
    """Build one item of a class from a FinQA example, or ``None`` if unfit."""
    qa = example["qa"]
    gold = list(qa["gold_inds"].values())
    answer = _answer(qa)
    if answer is None or not 1 <= len(gold) <= 3 or not qa["program"]:
        return None
    rng = random.Random(f"{example['id']}#{label}")
    if label == "PASS":
        evidence = gold
    elif label == "INSUFFICIENT":
        evidence = _distractors(example, gold, answer, rng)
    else:
        extra = _scaled_line(gold, rng)
        evidence = None if extra is None else [*gold, extra]
    if evidence is None:
        return None
    return {
        "id": example["id"],
        "question": qa["question"],
        "sub_questions": [qa["question"]],
        "findings": _findings(qa, answer, evidence),
        "gold": label,
        "human_reviewed": False,
    }


def _review(items: list[dict[str, Any]]) -> str:
    """Write a table of a seeded sample of each class for a hand check."""
    rng = random.Random(0)
    rows = []
    for label, _ in _CLASSES:
        of_class = [item for item in items if item["gold"] == label]
        rows += rng.sample(of_class, _SAMPLE_PER_CLASS)

    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", "<br>")

    lines = [
        "# Review sample",
        "",
        "Check that each gold label is right for the question and findings. Fix or",
        "drop an item in `build_finqa_verdicts.py`, regenerate, and set",
        "`human_reviewed` to true in `verdict_items.jsonl` for the items you confirm.",
        "",
        "| Id | Gold | Question | Findings |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {cell(r['id'])} | {r['gold']} | {cell(r['question'])} "
        f"| {cell(r['findings'])} |"
        for r in rows
    ]
    return "\n".join(lines) + "\n"


def build(source: Path) -> None:
    """Write ``verdict_items.jsonl`` and ``REVIEW.md`` from ``source``.

    Raises:
        ValueError: A chosen id is missing from ``source``, is used twice, or is
            unfit for its class.
    """
    by_id = {example["id"]: example for example in json.loads(source.read_text())}
    chosen = [item for _, ids in _CLASSES for item in ids]
    if len(set(chosen)) != len(chosen):
        raise ValueError("an example id is used more than once")
    missing = [item for item in chosen if item not in by_id]
    if missing:
        raise ValueError(f"ids not in {source}: {missing}")

    items = []
    for label, ids in _CLASSES:
        for example_id in ids:
            item = make_item(by_id[example_id], label)
            if item is None:
                raise ValueError(f"{example_id} is unfit for {label}")
            items.append(item)
    (_HERE / "verdict_items.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in items)
    )
    (_HERE / "REVIEW.md").write_text(_review(items))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, required=True, help="FinQA test.json")
    build(parser.parse_args().source)
