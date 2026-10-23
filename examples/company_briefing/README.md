# Company research briefing

This example uses Boeing's FY2022 Form 10-K to build an evidence-backed company briefing. It links the company, its reportable business segments, reported revenue, and the commercial-airline exposure described in the filing. The figures and claims are historical and apply to FY2022. The briefing is not an investment recommendation.

The example uses one annual report. It does not claim independent corroboration or compare multiple companies. Its source and SHA-256 are recorded in [`sources.json`](sources.json). The canonical filing is available from the [SEC](https://www.sec.gov/Archives/edgar/data/12927/000001292723000007/ba-20221231.htm). The pinned PDF copy is downloaded at setup time and is not included in this repository.

## Requirements

- A disposable Neo4j database configured with the `NEO4J_*` settings.
- The `docling`, `extract`, `neo4j`, and `agents` extras.
- An OpenAI-compatible model endpoint configured with `AGENT_LLM_BASE_URL`, `AGENT_LLM_API_KEY`, and `AGENT_LLM_MODEL_ID` for the `investigate` and `resume` stages.
- Network access to the pinned PDF and model downloads on the first run.

Install the extras in a repository checkout:

```bash
uv sync --extra docling --extra extract --extra neo4j --extra agents
```

Set `AGRAG_EXAMPLE_DATA_DIR` to change the runtime directory. The default is `~/.cache/agentic-graphrag/company-briefing`. The example stores the downloaded PDF and parsed document there, outside the repository.

## Run the stages

Run each stage from the repository root against a disposable graph. The stages are safe to repeat: `Graph.add` updates the same document key when its content changes, and the named task is resumed rather than recreated.

```bash
uv run python -m examples.company_briefing.workflow prepare
uv run python -m examples.company_briefing.workflow investigate
uv run python -m examples.company_briefing.workflow resume
uv run python -m examples.company_briefing.workflow review
```

`prepare` verifies the pinned report and adds it to the graph. `investigate` searches the graph and runs the built-in agent's first task invocation. `resume` invokes the same task again, prints its stored events and step-reuse assessments, and records a decision with fetched report evidence. `review` ingests a clearly labeled derivative that omits one risk paragraph, then restores the original report under the same document key. The source change flags the decision for review; the stage fetches current evidence and supersedes the decision while retaining the old support history.

The agent writes actual message and tool events through its middleware. The workflow does not create pretend tool events. Stored decision rationale is an explicit record supported by report passages. It is not model chain-of-thought.

Every stage prints the graph backend, project, and task before writing. Use a disposable database because the example writes graph data, conversation history, and decision traces. No stage clears the graph.
