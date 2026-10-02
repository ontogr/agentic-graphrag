"""Build the Healthcare fixtures from the pinned HealthBench and MedCorp sources.

The questions are a fixed selection of HealthBench Hard prompts. The full corpus is
the union of the best 32 passages that the search rule finds for the last user turn
of each question. The lite set is one question and five passages that the full
corpus holds for it, so a lite run takes a few minutes. The search runs over the
index that ``uv run python -m benchmarks healthcare build-index`` makes. The script
writes ``benchmarks/fixtures/healthcare/{lite,full}.json``.

Usage:
    uv run python -m benchmarks healthcare build-index
    uv run python -m benchmarks.fixtures.builders.healthcare
"""

import collections
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import tiktoken

from benchmarks.datasets.healthcare import (
    DATASET_NAME,
    FIXTURE_DIR,
    SOURCES,
    fetch_source_file,
    iter_rows,
    passage_reference,
    passage_sha256,
)
from benchmarks.datasets.healthcare_index import (
    CLOSURE_K,
    INDEX_PATH,
    closure,
    index_problems,
)
from benchmarks.models import (
    BenchmarkQuestion,
    Corpus,
    CorpusDocument,
    CorpusManifest,
    Mode,
    canonical_sha256,
)
from benchmarks.schemas.healthcare import HEALTHCARE


# The share of passages one search must beat by chance to count as retrievable, at
# 8, 16 and 32 passages. It is the 99th percentile of the gain that a closure gives
# to a question it was not made for.
PASS_BAR = {"8": 0.12096774193548387, "16": 0.15625, "32": 0.18902439024390247}
THEME_COUNTS = {
    "global_health": 42,
    "context_seeking": 27,
    "hedging": 25,
    "health_data_tasks": 17,
    "communication": 17,
    "complex_responses": 12,
    "emergency_referrals": 10,
}
# The lite question asks about a typhoid vaccine before travel to India. Its rubric
# has three items, so grading costs three judge calls. The five passages state the
# unconjugated vaccines and their boosters, the conjugate vaccines, the food and
# water measures, and the use of soap and water.
LITE = ["9bd72186-1665-4639-9346-26279cbd6d28"]
LITE_PASSAGES = [
    "article-30719_98",
    "article-30719_101",
    "article-30720_46",
    "article-28707_17",
    "article-30719_103",
]

FULL = [
    "a179a30f-398e-4af3-adca-ceab830f8f14",
    "59c68d10-55c1-4629-b05a-bedde7f343b5",
    "3da1daef-cf3e-4b8a-828d-e124d4d4ae88",
    "d345e898-1e52-48fb-af86-08fdc3384235",
    "fe5e8a24-eac2-497e-9846-f316733937f9",
    "1f71ae36-4fbb-4ca0-bbe4-e0afc01230fe",
    "1b37c2fb-030f-4c43-8f7f-d137a324b92c",
    "3dc41419-2565-428e-b9b9-02e3fd93c470",
    "4e8aab11-f0d4-490f-b0a1-0b68a9143331",
    "36c6e780-d4a8-47b2-8a36-90ee4b97607f",
    "e620f43b-2d6d-47e6-9465-6a9c8954c926",
    "481dc8eb-6490-42b4-826f-a4df9bff8c2b",
    "a43894bf-73e9-4e1e-8883-b243e3b678ed",
    "4fbaea7f-17ad-4daf-8795-e6720b811d5b",
    "f1e6f4ba-ec6f-46b3-8cf0-13e9f0f6140c",
    "044e49eb-8a9f-4044-b65e-f2fce5ec7c4b",
    "4a6dd904-9295-47a9-88d8-45272be3be50",
    "c45130e5-d0a9-4eb0-90ac-d4d8b56ac94f",
    "7695f7e3-d71f-4c29-9140-d0dad6555247",
    "4f50a30d-990d-4056-9131-eea4e85ec06c",
    "d1f2964f-1d45-4e38-807f-94e5b14611f4",
    "d175d5c4-91c8-466c-9955-ef6d4d7a39ac",
    "347568c2-8660-4a86-b0a2-a9393039a413",
    "323ae04e-63f7-4a23-9c30-cf55b4bf930c",
    "6bc43acb-3f76-47b2-8822-20edd1f0969c",
    "c2a13836-1117-447c-935a-e2c2abe38da4",
    "e5fbf908-f674-4e25-9dbf-3b4d3f2726e4",
    "6f7a472b-0b9b-42f1-8df4-54fcbee7e842",
    "ced9860d-fbcb-4044-9675-133f233bdb57",
    "0d0e9e7a-cb26-4c7b-af8b-78427f36ba3b",
    "b577b19f-1cf0-41ae-b32b-6c0099b3b752",
    "e87d2339-b72f-4cd3-8274-ccb052a21af3",
    "951e6025-a7eb-4dfc-9224-e09d3e177b66",
    "0e073591-b3e7-4dc8-94d0-dc5aa93ca35c",
    "eff8ed60-7329-4d2e-bf74-f22aa3861bee",
    "2cb527e0-3123-4dfd-bf16-1bd2cc4cf9bb",
    "f2d394ca-2496-4827-9e6a-92364200011d",
    "3a8782de-e12e-4664-af07-4a9eed24ebc8",
    "44f8bb1d-6bc4-4ca4-a365-d84b54f82384",
    "0bdbf3af-6bb6-4395-a73f-498fccaf8aba",
    "1648e538-f8ce-4b03-a1ee-10311f6489cd",
    "dbcc1530-cc71-4555-9603-e440647db591",
    "7bf7df45-5f64-40c7-8528-f35061257fd0",
    "70aa6173-24ed-4ff8-81fc-34c5fe7f84fb",
    "64fbdbf2-836e-4517-9476-016bb35950dd",
    "905949d2-7a0a-4461-8f4b-257de6be6eed",
    "8404a07b-4ba1-476c-a22c-a20e084b4153",
    "2f62707c-2c7f-4e1a-b8fc-af0fdb2edb27",
    "279a2765-8f53-4f3d-84e6-8c5983c8dc2e",
    "6e9b5700-cd5a-43df-99f7-299128888f1f",
    "781e7387-ed86-45d8-b65f-d853ca202cbe",
    "bddd8168-f229-487f-bae7-215331e4330b",
    "7004df36-1a02-4ce6-b47a-d65c66232243",
    "7c63b3f5-dbac-4ac0-9928-7e5a3c780852",
    "9bd72186-1665-4639-9346-26279cbd6d28",
    "6c2af010-b144-49a3-9872-6cefd534beb9",
    "db12fd52-01b7-4e0a-80ae-8fddd268f97d",
    "419c6ff1-a7a0-4d1c-9594-92c0e1b84264",
    "56a1608f-47af-42f0-bc88-7d7f5d9eccda",
    "59c18c75-2774-4939-abab-0da869419e24",
    "e3053c9b-60b6-48f3-aed3-b28d604981e9",
    "fd59b9c2-4750-453a-a3de-a995220cce04",
    "a4ee8bb5-b871-44b0-8e50-0f1abc804754",
    "591ba557-39cb-46a0-82e9-a58510c997a6",
    "357bfe1a-c083-4376-892f-adda7b63f968",
    "a18ec69b-f123-4a5c-8c67-65a812452236",
    "bcc107fc-4ab3-42e7-b042-e1a78c3b8b16",
    "c82df3ea-3afc-4fa9-bdea-1a1039039301",
    "9b98fb94-8a98-4c31-8bba-db9385a6b8a0",
    "fdf703c7-46af-4607-add2-7b2935b6ec2e",
    "16409e23-0444-40eb-842e-b4488db6a9e4",
    "5b323cdf-e322-4416-9f26-ec780960f0c8",
    "cc2902e3-38d3-40cc-83cc-639313d0e897",
    "1f13075f-6492-460a-b3ef-9ded58e16ee2",
    "90a127ff-db1f-4abf-997a-8d8e6721fddc",
    "3dace2dd-0b18-4b1c-9889-b1f1ebabe7ee",
    "c0b42f25-0159-4129-86bf-9bd2c05dba08",
    "6a6ca8f7-92ee-4d37-b6e7-92e1dfd220ed",
    "b160df9f-be98-4a4d-9cc8-11a612ffaf87",
    "70afd1ac-85ea-4455-a5a2-15b35378e10a",
    "023b34ed-28a7-4f23-b012-8f041b423f6e",
    "71cbeed6-0584-4153-b5f0-526484eea071",
    "f93b0850-2c60-479d-831b-b8c8f9493d61",
    "57ff71e1-335f-4e87-9f44-46326ba66038",
    "9e19ac1b-e8d7-4a1e-8392-7f98f7ade805",
    "ab2362e7-e5a0-45e3-9928-b5f92a4c3780",
    "78c02ee0-52f2-47d2-b5dc-d7c312727448",
    "41c29eee-7626-4e22-99aa-b17be3705338",
    "b2905d1a-80ea-4e2e-ba63-724bcc65743f",
    "9f70268e-9e18-4305-a049-c76a6efa71bc",
    "d3c8df71-177a-40fe-9715-2a975e4f9fab",
    "4f7a2755-1a95-4b14-b1df-14799ef4741a",
    "c8cce1a6-1094-4fbc-9b23-57d56570912c",
    "fa64556e-ff85-42c5-810b-7ee65c47cf57",
    "0a51d024-97a2-4a01-a946-0c7abe025cdc",
    "8734ac13-4149-41ef-b18c-d3fd8d49bbf8",
    "436fe4f1-1fa0-4269-bfe4-0832eec1c913",
    "c33322cc-49a2-47f9-a541-a4dc5505c5f7",
    "36e0d4da-8a8a-4e40-b39a-15098b61608e",
    "c28ac978-31e6-463d-b97b-3dadcf059db4",
    "c4d8b028-f148-47ca-b1bc-c5c4675231b7",
    "b867822b-cbeb-4533-a51e-6e35813b5f15",
    "45b7cc5e-b5a8-481c-a801-5d0556677154",
    "1658053e-9978-43b9-aa50-0dde20644cc4",
    "9ffdac07-5961-4317-a42f-b9439abb9c65",
    "bbcca251-520a-42ff-8532-d9b05752fb42",
    "a961e1db-5105-47f7-8473-ad7173442a16",
    "0f6de01c-c6fc-460e-b016-87e3bfd8147f",
    "2da6e600-a930-4ee4-86de-50de59610ca3",
    "7eac31ac-7940-4dcd-bd10-571dd08c5be2",
    "0ebc8350-10d2-46ce-86b6-80800253ec76",
    "9ef9bb72-d661-4aa8-827f-7b07aa7f9309",
    "8ea39d90-34ec-4f3e-b09e-8f6262166028",
    "b6a74ec0-2607-448e-982c-3d5ef01fcc0a",
    "4d441d96-f214-46de-9f01-60bdfb8fcd4c",
    "3298bc47-b2f2-4fbf-9e88-e7376488ddab",
    "e503b0a5-f853-466b-b405-8771bbec524e",
    "b0ae4413-edaf-4a62-937f-0815805a6e67",
    "b445504c-da13-4b98-9d5e-c0af00c36a81",
    "eb1d97c2-659f-4331-89df-5a24c40b1a09",
    "72125034-4bd0-4418-a573-4baeaeadea6f",
    "062e3a49-07e0-4b5c-a941-ceb8cc4111e4",
    "20a34218-c24b-4fe0-9b69-5d3ed9faf801",
    "a1fa2e61-0185-42fb-849e-62129bf598d9",
    "8aadd85d-1aa2-4046-a854-884c6ec4ff34",
    "478c07bf-4c15-4639-96b8-46bc8508d073",
    "b303227d-8ad1-4dc5-80d5-92e4be25983e",
    "ffecc929-428a-4884-b8f3-76bd7147fb15",
    "26298a9e-b28d-4988-9118-f4487a51966f",
    "1bb2b561-2226-467d-b087-55e7d778ca21",
    "4bef196d-54dc-4a9d-8fc3-fc6a595c5ddc",
    "6afbbe65-a91a-4d9a-b834-a3f2dad4e488",
    "40a43006-486c-4d7a-8e16-641a76896765",
    "bc228d6d-e38b-45d2-8fd1-299554492592",
    "54fda87c-0d03-4427-84da-f50a5f267c3c",
    "aa7a760a-5173-4a39-af83-48d6ae2230f0",
    "83942372-2713-47b8-ba54-32d516286f36",
    "d7fd5cb8-7f2f-4678-ba41-2361e2ab3a40",
    "025d3bca-2544-4161-ab15-e2474d02e171",
    "613b5587-6c18-4174-a184-3a527f4bc5ef",
    "08c48e78-acda-4051-92ff-a6e99ee122d9",
    "a14c7ed6-6927-42bc-9384-7f74c866f93d",
    "f7d6994d-4e80-463f-bd0d-5aebacb75f0a",
    "122f0795-5f3f-43dd-8d69-a75253d03fb6",
    "b4bfd457-635f-46b1-8f78-6a029f30e402",
    "2c915b71-0c36-4f70-a5c0-31c99e45d549",
    "3599cfcc-27fd-4149-802f-9ea7723a0ad7",
    "b92904d7-917d-40f7-94d4-6401c23ec908",
    "00656524-cc51-47a3-bfb5-85e7096ee1c8",
    "0e819a9c-851d-4a7a-9263-62cfc8ce1b48",
]


def _theme(row: dict) -> str:
    return next(t[6:] for t in row["example_tags"] if t.startswith("theme:"))


def _healthbench_rows() -> dict[str, dict]:
    (file,) = SOURCES["healthbench"]["files"]
    path = fetch_source_file("healthbench", file)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return {row["prompt_id"]: row for row in rows}


def _passages(wanted: set[str]) -> dict[str, tuple[str, str, int, str]]:
    """Find each wanted id in the source files: ``(source, file, row, contents)``."""
    found: dict[str, tuple[str, str, int, str]] = {}
    for source in ("textbooks", "statpearls"):
        for file in sorted(SOURCES[source]["files"]):
            for row, passage_id, contents in iter_rows(fetch_source_file(source, file)):
                if passage_id in wanted:
                    if passage_id in found:
                        raise SystemExit(f"{passage_id} is in two places")
                    found[passage_id] = (source, file, row, contents)
    if wanted - found.keys():
        raise SystemExit(
            f"{len(wanted - found.keys())} passages are not in the sources"
        )
    return found


def _question(row: dict, mode: Mode) -> BenchmarkQuestion:
    messages = [{"role": m["role"], "content": m["content"]} for m in row["prompt"]]
    if not any(item["points"] > 0 for item in row["rubrics"]):
        raise SystemExit(f"{row['prompt_id']} has no positive rubric item")
    return BenchmarkQuestion(
        id=row["prompt_id"],
        corpus_id=f"healthcare-{mode}",
        messages=messages,
        group=_theme(row),
        reference={
            "rubrics": [
                {"criterion": item["criterion"], "points": item["points"]}
                for item in row["rubrics"]
            ],
            "row_sha256": canonical_sha256(row),
        },
    )


def main() -> None:
    """Write both fixtures."""
    if not INDEX_PATH.exists():
        raise SystemExit(
            "run `uv run python -m benchmarks healthcare build-index` first"
        )
    rows = _healthbench_rows()
    with closing(sqlite3.connect(INDEX_PATH)) as index:
        problems = index_problems(index)
    if problems:
        raise SystemExit(f"the index is not complete: {'; '.join(problems)}")
    themes = collections.Counter(_theme(rows[i]) for i in FULL)
    if themes != THEME_COUNTS or not set(LITE) <= set(FULL):
        raise SystemExit(f"unexpected selection: {dict(themes)}")
    db = sqlite3.connect(INDEX_PATH)
    encoder = tiktoken.get_encoding("cl100k_base")
    picks: dict[Mode, list[str]] = {"lite": LITE, "full": FULL}
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    for mode, ids in picks.items():
        questions = [_question(rows[i], mode) for i in ids]
        wanted: set[str] = set()
        for question in questions:
            wanted.update(closure(db, question.query, CLOSURE_K["full"]))
        if mode == "lite":
            if not set(LITE_PASSAGES) <= wanted:
                raise SystemExit("a lite passage is not in the closure of its question")
            wanted = set(LITE_PASSAGES)
        found = _passages(wanted)
        ordered = sorted(found.items(), key=lambda kv: kv[1][:3])
        documents = [
            CorpusDocument(
                id=passage_id,
                uri=passage_id,
                sha256=passage_sha256(contents),
                source=passage_reference(source, file, row),
            )
            for passage_id, (source, file, row, contents) in ordered
        ]
        n_tokens = sum(
            len(encoder.encode(contents, disallowed_special=()))
            for *_, contents in found.values()
        )
        manifest = CorpusManifest(
            name=DATASET_NAME,
            domain="healthcare",
            mode=mode,
            upstream={
                "sources": SOURCES,
                "closure_passages_per_question": CLOSURE_K,
                "pass_bar": PASS_BAR,
            },
            corpora=[
                Corpus(
                    id=f"healthcare-{mode}",
                    service=f"healthcare-{mode}",
                    schema_name=HEALTHCARE.name,
                    documents=documents,
                    n_tokens=n_tokens,
                )
            ],
            questions=questions,
        )
        Path(FIXTURE_DIR / f"{mode}.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=1, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        print(
            f"{mode}: {len(questions)} questions, {len(documents)} passages, "
            f"{n_tokens} tokens"
        )


if __name__ == "__main__":
    main()
