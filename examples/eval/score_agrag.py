"""Score agrag answers on a folder of documents and questions.

The folder holds ``documents/`` and ``questions.jsonl``. Each line of the file is
a JSON object with ``question`` and ``answer``. See ``examples/eval/README.md``.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from deepeval.metrics import BaseMetric

from agrag.agents.build import build_agent
from agrag.agents.settings import AgentLLMSettings
from agrag.common.data_models.graph_schema import GENERIC
from agrag.embedding.sentence_transformers import SentenceTransformerEmbedder
from agrag.eval import (
    ChatModelJudge,
    CitationAccuracyMetric,
    EvalJudgeSettings,
    answer_case,
    context_precision,
    context_recall,
    correctness,
    faithfulness,
)
from agrag.graphdb import build_graph_store
from agrag.ingestion import Graph
from agrag.ingestion.extract import BAMLExtractor, ExtractionLLMSettings
from agrag.retrieval.search_engine import SearchEngine


_NEEDS_EVIDENCE = ("faithfulness", "context_precision", "context_recall")
_DEFAULT_DATASET = Path(__file__).parent / "financebench"


async def _score(judge: ChatModelJudge, case: Any) -> dict[str, float]:
    """Score one case with the five metrics at once."""
    metrics: dict[str, BaseMetric] = {
        "correctness": correctness(judge),
        "faithfulness": faithfulness(judge),
        "context_precision": context_precision(judge),
        "context_recall": context_recall(judge),
        "citation_accuracy": CitationAccuracyMetric(judge),
    }
    if not case.retrieval_context:
        # DeepEval rejects an empty context, so these score 0.
        for name in _NEEDS_EVIDENCE:
            del metrics[name]
    await asyncio.gather(*(metric.a_measure(case) for metric in metrics.values()))
    scores = dict.fromkeys(_NEEDS_EVIDENCE, 0.0)
    scores.update({name: metric.score or 0.0 for name, metric in metrics.items()})
    return scores


async def main(dataset: Path) -> None:
    """Ingest the documents, answer each question and print the score table."""
    questions = [
        json.loads(line)
        for line in (dataset / "questions.jsonl").read_text().splitlines()
        if line.strip()
    ]
    store = build_graph_store("neo4j")
    embedder = SentenceTransformerEmbedder()
    graph = await Graph.open(
        schema=GENERIC,
        graph_store=store,
        embedder=embedder,
        extractor=BAMLExtractor(
            settings=ExtractionLLMSettings.from_openai_compatible_env()
        ),
    )
    try:
        await graph.add(source=dataset / "documents")
        engine = SearchEngine(
            graph_store=store, embedder=embedder, graph_schema=GENERIC
        )
        llm_settings = AgentLLMSettings.from_openai_compatible_env()
        judge = ChatModelJudge.from_settings(
            EvalJudgeSettings.from_openai_compatible_env()
        )
        rows = []
        for item in questions:
            # A new agent for each question keeps the run state apart.
            agent = build_agent(
                engine=engine, llm_settings=llm_settings, graph_schema=GENERIC
            )
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": item["question"]}]}
            )
            case = answer_case(item["question"], result, item["answer"])
            rows.append((item["question"], await _score(judge, case)))
    finally:
        await store.close()

    names = list(rows[0][1])
    print(f"{'question':<40}" + "".join(f"{n:>19}" for n in names))
    for question, scores in rows:
        print(f"{question[:38]:<40}" + "".join(f"{scores[n]:>19.2f}" for n in names))
    print(
        f"{'mean':<40}"
        + "".join(f"{sum(s[n] for _, s in rows) / len(rows):>19.2f}" for n in names)
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dataset",
        type=Path,
        default=_DEFAULT_DATASET,
        help="Folder with documents/ and questions.jsonl (default: FinanceBench)",
    )
    asyncio.run(main(parser.parse_args().dataset))
