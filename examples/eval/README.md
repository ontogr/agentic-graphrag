# Score agrag on your own questions

`score_agrag.py` ingests a folder of documents, answers each question with the
agrag agent, and scores every answer with the five answer-quality metrics from
`agrag.eval`. The default dataset is a five-question subset of FinanceBench in
`financebench/`. Read `financebench/NOTICE.md` for its licence. It is
CC-BY-NC-4.0, not Apache-2.0.

## Prerequisites

1. Install the extras:

   ```bash
   uv sync --extra docling --extra llm --extra agents --extra eval --extra neo4j --extra embed-local
   ```

2. Start Neo4j, and set the `NEO4J_*` variables in `.env` to match its password:

   ```bash
   docker compose -f docker/docker-compose.ci.yml up -d neo4j
   ```

3. Set the models in `.env`. `LLM_*` configures the extractor and the agent.
   `EVAL_JUDGE_*` configures the judge. If you leave `EVAL_JUDGE_*` unset, the
   judge falls back to the agent's model, so the model grades its own answers.
   Set `EVAL_JUDGE_*` to a different model for a fair score.

## Run

```bash
uv run python examples/eval/score_agrag.py
uv run python examples/eval/score_agrag.py --dataset path/to/your/folder
```

Your folder must have this layout:

```text
your-folder/
  documents/        PDF, DOCX, Markdown or text files
  questions.jsonl   one JSON object per line: {"question": "...", "answer": "..."}
```

The run writes to the Neo4j database that you configured. Use an empty database.

## Read the table

Each row is one question. Each score is from 0 to 1. A higher score is better.

| Column | Meaning |
| --- | --- |
| `correctness` | The answer agrees with your reference answer. |
| `faithfulness` | The answer does not contradict the evidence the agent read. |
| `context_precision` | The evidence that the agent read ranks the useful items first. |
| `context_recall` | The evidence that the agent read covers your reference answer. |
| `citation_accuracy` | Each cited sentence is supported by the item it cites. |

Each score is one judge run. The agent makes 8 to 21 LLM calls per question, and
the judge adds about 1 call per metric plus 1 per cited sentence, so cost grows
with the number of questions.
