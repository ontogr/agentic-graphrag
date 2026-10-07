---
title: agrag.eval
sidebar_position: 6
---

## `agrag.eval` \{#agrag-eval}

Public evaluation metrics for agrag, built on DeepEval and AgentEvals.

Needs the `eval` extra: `pip install 'agentic-graphrag[eval]'`.

**Modules:**

- [**adapter**](#agrag-eval-adapter) – Adapters that let plain scoring functions report through DeepEval.
- [**answer**](#agrag-eval-answer) – Answer-quality metrics for agrag, scored from questions and reference answers.
- [**extraction**](#agrag-eval-extraction) – Extraction quality: entity and relation-triple F1 against gold annotations.
- [**judge**](#agrag-eval-judge) – A DeepEval judge model backed by an agrag chat model.
- [**resolution**](#agrag-eval-resolution) – Resolution quality: B-cubed and pairwise scores of mention clusters.
- [**settings**](#agrag-eval-settings) – Env-backed configuration for the eval judge model.
- [**trajectory**](#agrag-eval-trajectory) – Agent trajectory evaluation: read runs, check structure, judge quality.
- [**verifier**](#agrag-eval-verifier) – Verifier calibration: does the verifier give the right verdict?

**Classes:**

- [**ChatModelJudge**](#agrag-eval-ChatModelJudge) – Wrap a LangChain chat model as a DeepEval judge.
- [**CitationAccuracyMetric**](#agrag-eval-CitationAccuracyMetric) – Score whether each cited sentence follows from the evidence it cites.
- [**CitationScoreBreakdown**](#agrag-eval-CitationScoreBreakdown) – Available precision, recall, and sentence-count fields for one score.
- [**CitationSentenceRow**](#agrag-eval-CitationSentenceRow) – One cited sentence and its support verdict, for the report.
- [**ClusterAssignment**](#agrag-eval-ClusterAssignment) – A grouping of mentions, listed by position in the mention list.
- [**EvalJudgeSettings**](#agrag-eval-EvalJudgeSettings) – LLM client config for the eval judge.
- [**ExtractionGold**](#agrag-eval-ExtractionGold) – One gold-annotated chunk of text.
- [**MicroScores**](#agrag-eval-MicroScores) – Dataset scores pooled over every item, for entities and relations.
- [**ScoreMetric**](#agrag-eval-ScoreMetric) – A DeepEval metric backed by a plain scoring function.
- [**ScoreResult**](#agrag-eval-ScoreResult) – The outcome of one scoring function call.
- [**Scores**](#agrag-eval-Scores) – Precision, recall and F1.
- [**SpanCapture**](#agrag-eval-SpanCapture) – Capture one agent run's spans for `read_trajectory`.
- [**Trajectory**](#agrag-eval-Trajectory) – The ordered steps of one agent run.
- [**VerdictItem**](#agrag-eval-VerdictItem) – One fixed verifier input with its gold verdict.
- [**VerdictReport**](#agrag-eval-VerdictReport) – Scores of predicted verdicts against gold verdicts.

**Functions:**

- [**answer_case**](#agrag-eval-answer_case) – Build the test case that every answer-quality metric scores.
- [**cluster_quality_metric**](#agrag-eval-cluster_quality_metric) – Build a metric for cluster quality on one test case.
- [**context_precision**](#agrag-eval-context_precision) – Build the metric for useful evidence ranked before noise.
- [**context_recall**](#agrag-eval-context_recall) – Build the metric for reference facts that the evidence covers.
- [**correctness**](#agrag-eval-correctness) – Build the answer correctness metric against the reference.
- [**entity_quality_metric**](#agrag-eval-entity_quality_metric) – Build a metric for entity F1 on one test case.
- [**expected_tools_metric**](#agrag-eval-expected_tools_metric) – Build the metric that the run called every expected tool.
- [**extraction_case**](#agrag-eval-extraction_case) – Build a test case that holds a predicted and a gold extraction.
- [**faithfulness**](#agrag-eval-faithfulness) – Build the metric for claims that the evidence the agent saw does not contradict.
- [**final_answer**](#agrag-eval-final_answer) – Return the text of the last assistant message in an agent run.
- [**micro_scores**](#agrag-eval-micro_scores) – Pool measured entity and relation metrics into dataset scores.
- [**parse_json_case**](#agrag-eval-parse_json_case) – Read the `(actual, expected)` models back from a JSON test case.
- [**read_trajectory**](#agrag-eval-read_trajectory) – Read the tool and model steps from finished spans.
- [**relation_quality_metric**](#agrag-eval-relation_quality_metric) – Build a metric for relation triple F1 on one test case.
- [**resolution_case**](#agrag-eval-resolution_case) – Build a test case that holds predicted and gold clusters.
- [**retry_budget_metric**](#agrag-eval-retry_budget_metric) – Build the metric that retries stay within budget.
- [**run_extractor**](#agrag-eval-run_extractor) – Run an extractor over gold items and build one test case per item.
- [**run_resolver**](#agrag-eval-run_resolver) – Resolve mention strings and return the clusters the resolver forms.
- [**run_resolver_detailed**](#agrag-eval-run_resolver_detailed) – Resolve mention strings and return the clusters plus raw evidence.
- [**run_verifier**](#agrag-eval-run_verifier) – Run the verifier over items and return one label per item.
- [**task_completion**](#agrag-eval-task_completion) – Build the judged metric for task completion.
- [**to_json_case**](#agrag-eval-to_json_case) – Build a test case that carries structured data as JSON.
- [**trajectory_case**](#agrag-eval-trajectory_case) – Build the test case every trajectory metric scores.
- [**trajectory_quality**](#agrag-eval-trajectory_quality) – Build the judged metric for trajectory quality.
- [**verdict_case**](#agrag-eval-verdict_case) – Build a test case with the predicted and the gold verdict.
- [**verdict_match_metric**](#agrag-eval-verdict_match_metric) – Build a metric that scores 1.0 when the verdict equals the gold verdict.
- [**verdict_report**](#agrag-eval-verdict_report) – Score predicted verdicts against gold verdicts.
- [**verifier_before_answer_metric**](#agrag-eval-verifier_before_answer_metric) – Build the metric that the verifier ran before the answer.

### `agrag.eval.ChatModelJudge` \{#agrag-eval-ChatModelJudge}

```python
ChatModelJudge(chat_model:Any, name:str, *, tracer:Tracer | None = None) -> None
```

Bases: <code>DeepEvalBaseLLM</code>

Wrap a LangChain chat model as a DeepEval judge.

Pass an instance as `model=` to any DeepEval metric. With a `schema`,
`generate` returns an instance of it. Without one, it returns the reply
text. Provider errors surface unchanged.

**Functions:**

- [**a_generate**](#agrag-eval-ChatModelJudge-a_generate) – Run one judge call asynchronously. See `generate`.
- [**from_settings**](#agrag-eval-ChatModelJudge-from_settings) – Build a judge from settings.
- [**generate**](#agrag-eval-ChatModelJudge-generate) – Run one judge call, returning a `schema` instance or the reply text.
- [**get_model_name**](#agrag-eval-ChatModelJudge-get_model_name) – Return the judge's model id.
- [**load_model**](#agrag-eval-ChatModelJudge-load_model) – Return the wrapped chat model.

#### `agrag.eval.ChatModelJudge.a_generate` \{#agrag-eval-ChatModelJudge-a_generate}

```python
a_generate(prompt:str, schema:type[BaseModel] | None = None) -> Any
```

Run one judge call asynchronously. See `generate`.

#### `agrag.eval.ChatModelJudge.from_settings` \{#agrag-eval-ChatModelJudge-from_settings}

```python
from_settings(settings:EvalJudgeSettings, *, tracer:Tracer | None = None) -> ChatModelJudge
```

Build a judge from settings.

The chat model is copied with `settings.temperature` set. When that
is `None`, no temperature is set. A model that rejects the
parameter then needs `EVAL_JUDGE_TEMPERATURE` empty.

**Parameters:**

- **settings** (<code>[EvalJudgeSettings](#agrag-eval-settings-EvalJudgeSettings)</code>) – The judge client config and temperature.
- **tracer** (<code>Tracer | None</code>) – Receives OpenInference spans for every judge call.
  None emits no spans.

#### `agrag.eval.ChatModelJudge.generate` \{#agrag-eval-ChatModelJudge-generate}

```python
generate(prompt:str, schema:type[BaseModel] | None = None) -> Any
```

Run one judge call, returning a `schema` instance or the reply text.

#### `agrag.eval.ChatModelJudge.get_model_name` \{#agrag-eval-ChatModelJudge-get_model_name}

```python
get_model_name() -> str
```

Return the judge's model id.

#### `agrag.eval.ChatModelJudge.load_model` \{#agrag-eval-ChatModelJudge-load_model}

```python
load_model() -> Any
```

Return the wrapped chat model.

### `agrag.eval.CitationAccuracyMetric` \{#agrag-eval-CitationAccuracyMetric}

```python
CitationAccuracyMetric(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> None
```

Bases: <code>BaseMetric</code>

Score whether each cited sentence follows from the evidence it cites.

The unit is the sentence. A sentence counts as cited when it carries a
citation key. A judge decides whether the text of the cited evidence supports
the sentence. It scores each sentence with one `GEval` run. A cited key that
the run's ledger did not assign is fabricated: the sentence is unsupported and
no judge call happens.

The score is the F1 of two ratios. Precision is supported cited sentences
over cited sentences. Recall is supported cited sentences over all sentences
of at least four words, plus any shorter cited sentence. `score_breakdown`
holds both and the sentence counts. An answer with no citations scores 0. An
abstention, the exact text `No relevant evidence found.`, scores 1.
`score_breakdown` also holds one row per cited sentence with its keys,
fabricated flag, support verdict and judge reason.

The test case must come from `answer_case`, which puts the evidence under
`metadata["citations"]`. A judge failure on any sentence raises.

**Attributes:**

- [**judge**](#agrag-eval-CitationAccuracyMetric-judge) – The judge model.
- [**threshold**](#agrag-eval-CitationAccuracyMetric-threshold) – The minimum score that counts as success, and the minimum
  support score for one sentence.
- [**score_breakdown**](#agrag-eval-CitationAccuracyMetric-score_breakdown) (<code>[CitationScoreBreakdown](#agrag-eval-answer-CitationScoreBreakdown)</code>) – Precision, recall, and sentence counts for the score.

**Functions:**

- [**a_measure**](#agrag-eval-CitationAccuracyMetric-a_measure) – Judge the cited sentences with up to eight concurrent calls.
- [**measure**](#agrag-eval-CitationAccuracyMetric-measure) – Judge the cited sentences one after the other.

#### `agrag.eval.CitationAccuracyMetric.a_measure` \{#agrag-eval-CitationAccuracyMetric-a_measure}

```python
a_measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Judge the cited sentences with up to eight concurrent calls.

**Parameters:**

- **test_case** (<code>LLMTestCase</code>) – The test case built by `answer_case`.
- \***args** (<code>Any</code>) – Additional positional arguments accepted by DeepEval.
- \*\***kwargs** (<code>Any</code>) – Additional keyword arguments accepted by DeepEval.

**Returns:**

- <code>float</code> – The citation accuracy score.

#### `agrag.eval.CitationAccuracyMetric.judge` \{#agrag-eval-CitationAccuracyMetric-judge}

```python
judge = judge
```

#### `agrag.eval.CitationAccuracyMetric.measure` \{#agrag-eval-CitationAccuracyMetric-measure}

```python
measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Judge the cited sentences one after the other.

**Parameters:**

- **test_case** (<code>LLMTestCase</code>) – The test case built by `answer_case`.
- \***args** (<code>Any</code>) – Additional positional arguments accepted by DeepEval.
- \*\***kwargs** (<code>Any</code>) – Additional keyword arguments accepted by DeepEval.

**Returns:**

- <code>float</code> – The citation accuracy score.

#### `agrag.eval.CitationAccuracyMetric.score_breakdown` \{#agrag-eval-CitationAccuracyMetric-score_breakdown}

```python
score_breakdown: CitationScoreBreakdown
```

#### `agrag.eval.CitationAccuracyMetric.threshold` \{#agrag-eval-CitationAccuracyMetric-threshold}

```python
threshold = threshold
```

### `agrag.eval.CitationScoreBreakdown` \{#agrag-eval-CitationScoreBreakdown}

Bases: <code>TypedDict</code>

Available precision, recall, and sentence-count fields for one score.

All fields are optional because abstentions and uncited answers have partial
breakdowns.

**Attributes:**

- [**citation_precision**](#agrag-eval-CitationScoreBreakdown-citation_precision) (<code>float</code>) – Fraction of cited sentences supported by evidence.
- [**citation_recall**](#agrag-eval-CitationScoreBreakdown-citation_recall) (<code>float</code>) – Fraction of eligible sentences supported by evidence.
- [**cited_sentences**](#agrag-eval-CitationScoreBreakdown-cited_sentences) (<code>int</code>) – Number of sentences with citations.
- [**supported_sentences**](#agrag-eval-CitationScoreBreakdown-supported_sentences) (<code>int</code>) – Number of cited sentences supported by evidence.
- [**sentences**](#agrag-eval-CitationScoreBreakdown-sentences) (<code>int</code>) – Number of eligible sentences in the answer.
- [**sentence_rows**](#agrag-eval-CitationScoreBreakdown-sentence_rows) (<code>list\[[CitationSentenceRow](#agrag-eval-answer-CitationSentenceRow)\]</code>) – One row per cited sentence with its keys and verdict.

#### `agrag.eval.CitationScoreBreakdown.citation_precision` \{#agrag-eval-CitationScoreBreakdown-citation_precision}

```python
citation_precision: float
```

#### `agrag.eval.CitationScoreBreakdown.citation_recall` \{#agrag-eval-CitationScoreBreakdown-citation_recall}

```python
citation_recall: float
```

#### `agrag.eval.CitationScoreBreakdown.cited_sentences` \{#agrag-eval-CitationScoreBreakdown-cited_sentences}

```python
cited_sentences: int
```

#### `agrag.eval.CitationScoreBreakdown.sentence_rows` \{#agrag-eval-CitationScoreBreakdown-sentence_rows}

```python
sentence_rows: list[CitationSentenceRow]
```

#### `agrag.eval.CitationScoreBreakdown.sentences` \{#agrag-eval-CitationScoreBreakdown-sentences}

```python
sentences: int
```

#### `agrag.eval.CitationScoreBreakdown.supported_sentences` \{#agrag-eval-CitationScoreBreakdown-supported_sentences}

```python
supported_sentences: int
```

### `agrag.eval.CitationSentenceRow` \{#agrag-eval-CitationSentenceRow}

Bases: <code>TypedDict</code>

One cited sentence and its support verdict, for the report.

**Attributes:**

- [**text**](#agrag-eval-CitationSentenceRow-text) (<code>str</code>) – The sentence with its citation keys removed.
- [**keys**](#agrag-eval-CitationSentenceRow-keys) (<code>list\[str\]</code>) – The keys the sentence cites, including bracketed keys the run
  never assigned. Empty only when the sentence cites no key-shaped
  token at all.
- [**fabricated**](#agrag-eval-CitationSentenceRow-fabricated) (<code>bool</code>) – Whether the sentence cites a key the run never assigned.
- [**supported**](#agrag-eval-CitationSentenceRow-supported) (<code>bool</code>) – Whether the cited evidence supports the sentence.
- [**reason**](#agrag-eval-CitationSentenceRow-reason) (<code>str</code>) – The support judge's reason, or why no judge call happened.

#### `agrag.eval.CitationSentenceRow.fabricated` \{#agrag-eval-CitationSentenceRow-fabricated}

```python
fabricated: bool
```

#### `agrag.eval.CitationSentenceRow.keys` \{#agrag-eval-CitationSentenceRow-keys}

```python
keys: list[str]
```

#### `agrag.eval.CitationSentenceRow.reason` \{#agrag-eval-CitationSentenceRow-reason}

```python
reason: str
```

#### `agrag.eval.CitationSentenceRow.supported` \{#agrag-eval-CitationSentenceRow-supported}

```python
supported: bool
```

#### `agrag.eval.CitationSentenceRow.text` \{#agrag-eval-CitationSentenceRow-text}

```python
text: str
```

### `agrag.eval.ClusterAssignment` \{#agrag-eval-ClusterAssignment}

Bases: <code>BaseModel</code>

A grouping of mentions, listed by position in the mention list.

**Attributes:**

- [**size**](#agrag-eval-ClusterAssignment-size) (<code>int</code>) – The number of mentions.
- [**clusters**](#agrag-eval-ClusterAssignment-clusters) (<code>list\[list\[int\]\]</code>) – Groups of mention indices. An index in no group is a cluster
  of one.
- [**matches_by_tier**](#agrag-eval-ClusterAssignment-matches_by_tier) (<code>dict\[str, int\]</code>) – How many confirmed non-exact matches each comparator
  made. Empty for gold clusters.
- [**failed_llm_requests**](#agrag-eval-ClusterAssignment-failed_llm_requests) (<code>int</code>) – LLM verification requests that errored and were
  mapped to "no match". Zero on gold clusters.

#### `agrag.eval.ClusterAssignment.clusters` \{#agrag-eval-ClusterAssignment-clusters}

```python
clusters: list[list[int]]
```

#### `agrag.eval.ClusterAssignment.failed_llm_requests` \{#agrag-eval-ClusterAssignment-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

#### `agrag.eval.ClusterAssignment.matches_by_tier` \{#agrag-eval-ClusterAssignment-matches_by_tier}

```python
matches_by_tier: dict[str, int] = {}
```

#### `agrag.eval.ClusterAssignment.size` \{#agrag-eval-ClusterAssignment-size}

```python
size: int
```

### `agrag.eval.EvalJudgeSettings` \{#agrag-eval-EvalJudgeSettings}

Bases: <code>BaseSettings</code>

LLM client config for the eval judge.

**Attributes:**

- [**client**](#agrag-eval-EvalJudgeSettings-client) (<code>LLMClientConfig</code>) – The judge model's client config.
- [**temperature**](#agrag-eval-EvalJudgeSettings-temperature) (<code>Annotated\[float | None, NoDecode\]</code>) – The sampling temperature the judge sends. `None` sends
  none, for models that reject the parameter. Set
  `EVAL_JUDGE_TEMPERATURE` empty to get `None`.
  Env: `EVAL_JUDGE_TEMPERATURE`.

Env prefix: `EVAL_JUDGE_`.

**Functions:**

- [**from_openai_compatible_env**](#agrag-eval-EvalJudgeSettings-from_openai_compatible_env) – Build settings from OpenAI-compatible env vars.

#### `agrag.eval.EvalJudgeSettings.client` \{#agrag-eval-EvalJudgeSettings-client}

```python
client: LLMClientConfig
```

#### `agrag.eval.EvalJudgeSettings.from_openai_compatible_env` \{#agrag-eval-EvalJudgeSettings-from_openai_compatible_env}

```python
from_openai_compatible_env() -> EvalJudgeSettings
```

Build settings from OpenAI-compatible env vars.

Loads `.env` first, then resolves `EVAL_JUDGE_BASE_URL`,
`EVAL_JUDGE_API_KEY` and `EVAL_JUDGE_MODEL_ID` through
pydantic-settings. Each falls back to the shared `LLM_*` variable
when unset or empty, so the judge is the agent's own model unless
`EVAL_JUDGE_*` is set. That model grades its own answers, which
biases scores upward. There is no default model.

**Returns:**

- <code>[EvalJudgeSettings](#agrag-eval-settings-EvalJudgeSettings)</code> – EvalJudgeSettings with one openai-generic client.

**Raises:**

- <code>ValueError</code> – No model id resolves from either set of variables.

#### `agrag.eval.EvalJudgeSettings.model_config` \{#agrag-eval-EvalJudgeSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EVAL_JUDGE_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

#### `agrag.eval.EvalJudgeSettings.temperature` \{#agrag-eval-EvalJudgeSettings-temperature}

```python
temperature: Annotated[float | None, NoDecode] = 0.0
```

### `agrag.eval.ExtractionGold` \{#agrag-eval-ExtractionGold}

Bases: <code>BaseModel</code>

One gold-annotated chunk of text.

**Attributes:**

- [**id**](#agrag-eval-ExtractionGold-id) (<code>str</code>) – A stable id for the item. It seeds the chunk and document ids.
- [**text**](#agrag-eval-ExtractionGold-text) (<code>str</code>) – The chunk text the extractor reads.
- [**gold**](#agrag-eval-ExtractionGold-gold) (<code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code>) – The annotation. Entity offsets index into `text`.

#### `agrag.eval.ExtractionGold.gold` \{#agrag-eval-ExtractionGold-gold}

```python
gold: ExtractionResult
```

#### `agrag.eval.ExtractionGold.id` \{#agrag-eval-ExtractionGold-id}

```python
id: str
```

#### `agrag.eval.ExtractionGold.text` \{#agrag-eval-ExtractionGold-text}

```python
text: str
```

### `agrag.eval.MicroScores` \{#agrag-eval-MicroScores}

Bases: <code>BaseModel</code>

Dataset scores pooled over every item, for entities and relations.

**Attributes:**

- [**entities_exact**](#agrag-eval-MicroScores-entities_exact) (<code>[Scores](#agrag-eval-extraction-Scores)</code>) – Entity scores with exact span matching.
- [**entities_relaxed**](#agrag-eval-MicroScores-entities_relaxed) (<code>[Scores](#agrag-eval-extraction-Scores)</code>) – Entity scores with overlap of at least 0.5.
- [**relations_exact**](#agrag-eval-MicroScores-relations_exact) (<code>[Scores](#agrag-eval-extraction-Scores)</code>) – Relation triple scores over exact entity alignment.
- [**relations_relaxed**](#agrag-eval-MicroScores-relations_relaxed) (<code>[Scores](#agrag-eval-extraction-Scores)</code>) – Relation triple scores over relaxed entity alignment.

#### `agrag.eval.MicroScores.entities_exact` \{#agrag-eval-MicroScores-entities_exact}

```python
entities_exact: Scores
```

#### `agrag.eval.MicroScores.entities_relaxed` \{#agrag-eval-MicroScores-entities_relaxed}

```python
entities_relaxed: Scores
```

#### `agrag.eval.MicroScores.relations_exact` \{#agrag-eval-MicroScores-relations_exact}

```python
relations_exact: Scores
```

#### `agrag.eval.MicroScores.relations_relaxed` \{#agrag-eval-MicroScores-relations_relaxed}

```python
relations_relaxed: Scores
```

### `agrag.eval.ScoreMetric` \{#agrag-eval-ScoreMetric}

```python
ScoreMetric(name:str, scorer:Callable[[LLMTestCase], ScoreResult], threshold:float = 0.5) -> None
```

Bases: <code>BaseMetric</code>

A DeepEval metric backed by a plain scoring function.

Use it for scores that DeepEval does not compute, such as F1 from
scikit-learn, so they report through the same `evaluate()` call.
If the scorer raises, the error is stored in `error` and raised again.

**Attributes:**

- [**name**](#agrag-eval-ScoreMetric-name) – The metric name shown in reports.
- [**scorer**](#agrag-eval-ScoreMetric-scorer) – The function that turns a test case into a `ScoreResult`.
- [**threshold**](#agrag-eval-ScoreMetric-threshold) – The minimum score that counts as success.

**Functions:**

- [**a_measure**](#agrag-eval-ScoreMetric-a_measure) – Run `measure`; scoring functions are synchronous.
- [**measure**](#agrag-eval-ScoreMetric-measure) – Run the scorer and record its score, reason and breakdown.

#### `agrag.eval.ScoreMetric.a_measure` \{#agrag-eval-ScoreMetric-a_measure}

```python
a_measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Run `measure`; scoring functions are synchronous.

#### `agrag.eval.ScoreMetric.measure` \{#agrag-eval-ScoreMetric-measure}

```python
measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Run the scorer and record its score, reason and breakdown.

#### `agrag.eval.ScoreMetric.name` \{#agrag-eval-ScoreMetric-name}

```python
name = name
```

#### `agrag.eval.ScoreMetric.scorer` \{#agrag-eval-ScoreMetric-scorer}

```python
scorer = scorer
```

#### `agrag.eval.ScoreMetric.threshold` \{#agrag-eval-ScoreMetric-threshold}

```python
threshold = threshold
```

### `agrag.eval.ScoreResult` \{#agrag-eval-ScoreResult}

Bases: <code>NamedTuple</code>

The outcome of one scoring function call.

**Attributes:**

- [**score**](#agrag-eval-ScoreResult-score) (<code>float</code>) – The score, normally between 0 and 1.
- [**reason**](#agrag-eval-ScoreResult-reason) (<code>str</code>) – A short explanation shown in DeepEval reports.
- [**breakdown**](#agrag-eval-ScoreResult-breakdown) (<code>dict\[str, Any\]</code>) – Extra numbers behind the score, such as per-class values.

#### `agrag.eval.ScoreResult.breakdown` \{#agrag-eval-ScoreResult-breakdown}

```python
breakdown: dict[str, Any]
```

#### `agrag.eval.ScoreResult.reason` \{#agrag-eval-ScoreResult-reason}

```python
reason: str
```

#### `agrag.eval.ScoreResult.score` \{#agrag-eval-ScoreResult-score}

```python
score: float
```

### `agrag.eval.Scores` \{#agrag-eval-Scores}

Bases: <code>BaseModel</code>

Precision, recall and F1.

**Attributes:**

- [**precision**](#agrag-eval-Scores-precision) (<code>float</code>) – Correct predictions over all predictions.
- [**recall**](#agrag-eval-Scores-recall) (<code>float</code>) – Correct predictions over all gold items.
- [**f1**](#agrag-eval-Scores-f1) (<code>float</code>) – The harmonic mean of precision and recall.

#### `agrag.eval.Scores.f1` \{#agrag-eval-Scores-f1}

```python
f1: float
```

#### `agrag.eval.Scores.precision` \{#agrag-eval-Scores-precision}

```python
precision: float
```

#### `agrag.eval.Scores.recall` \{#agrag-eval-Scores-recall}

```python
recall: float
```

### `agrag.eval.SpanCapture` \{#agrag-eval-SpanCapture}

```python
SpanCapture() -> None
```

Capture one agent run's spans for `read_trajectory`.

Use as a context manager around `agent.ainvoke` and read the run with
`trajectory()` after. Each capture has its own provider and exporter,
so captures never share spans and the global provider is unchanged.

<details open>
<summary>Example</summary>

```python
with SpanCapture() as capture:
    agent = build_agent(engine, settings, tracer=capture.tracer)
    result = await agent.ainvoke({"messages": [...]})
trajectory = capture.trajectory()
```

</details>

**Functions:**

- [**trajectory**](#agrag-eval-SpanCapture-trajectory) – Read the captured spans as a trajectory.

**Attributes:**

- [**tracer**](#agrag-eval-SpanCapture-tracer) (<code>Tracer</code>) – The tracer to pass as `tracer=` to `build_agent`.

#### `agrag.eval.SpanCapture.tracer` \{#agrag-eval-SpanCapture-tracer}

```python
tracer: Tracer
```

The tracer to pass as `tracer=` to `build_agent`.

**Returns:**

- <code>Tracer</code> – A tracer bound to this capture's private provider.

#### `agrag.eval.SpanCapture.trajectory` \{#agrag-eval-SpanCapture-trajectory}

```python
trajectory() -> Trajectory
```

Read the captured spans as a trajectory.

**Returns:**

- <code>[Trajectory](#agrag-eval-trajectory-Trajectory)</code> – The trajectory read from the spans captured so far.

### `agrag.eval.Trajectory` \{#agrag-eval-Trajectory}

Bases: <code>BaseModel</code>

The ordered steps of one agent run.

**Attributes:**

- [**steps**](#agrag-eval-Trajectory-steps) (<code>list\[[Step](#agrag-eval-trajectory-Step)\]</code>) – The run's tool and model steps in start order.

#### `agrag.eval.Trajectory.steps` \{#agrag-eval-Trajectory-steps}

```python
steps: list[Step]
```

### `agrag.eval.VerdictItem` \{#agrag-eval-VerdictItem}

Bases: <code>BaseModel</code>

One fixed verifier input with its gold verdict.

**Attributes:**

- [**id**](#agrag-eval-VerdictItem-id) (<code>str</code>) – A stable id for the item.
- [**question**](#agrag-eval-VerdictItem-question) (<code>str</code>) – The original question.
- [**sub_questions**](#agrag-eval-VerdictItem-sub_questions) (<code>list\[str\]</code>) – The sub-questions the question was split into.
- [**findings**](#agrag-eval-VerdictItem-findings) (<code>str</code>) – The findings text with citation keys such as `E1`.
- [**gold**](#agrag-eval-VerdictItem-gold) (<code>Literal['PASS', 'INSUFFICIENT', 'CONTRADICTORY']</code>) – The verdict the verifier should give.
- [**human_reviewed**](#agrag-eval-VerdictItem-human_reviewed) (<code>bool</code>) – True when a person confirmed the gold label.

#### `agrag.eval.VerdictItem.findings` \{#agrag-eval-VerdictItem-findings}

```python
findings: str
```

#### `agrag.eval.VerdictItem.gold` \{#agrag-eval-VerdictItem-gold}

```python
gold: Literal['PASS', 'INSUFFICIENT', 'CONTRADICTORY']
```

#### `agrag.eval.VerdictItem.human_reviewed` \{#agrag-eval-VerdictItem-human_reviewed}

```python
human_reviewed: bool = False
```

#### `agrag.eval.VerdictItem.id` \{#agrag-eval-VerdictItem-id}

```python
id: str
```

#### `agrag.eval.VerdictItem.question` \{#agrag-eval-VerdictItem-question}

```python
question: str
```

#### `agrag.eval.VerdictItem.sub_questions` \{#agrag-eval-VerdictItem-sub_questions}

```python
sub_questions: list[str]
```

### `agrag.eval.VerdictReport` \{#agrag-eval-VerdictReport}

Bases: <code>BaseModel</code>

Scores of predicted verdicts against gold verdicts.

**Attributes:**

- [**labels**](#agrag-eval-VerdictReport-labels) (<code>list\[str\]</code>) – The class order of `confusion_matrix`.
- [**per_class**](#agrag-eval-VerdictReport-per_class) (<code>dict\[str, [ClassScores](#agrag-eval-verifier-ClassScores)\]</code>) – Scores for each class.
- [**macro_f1**](#agrag-eval-VerdictReport-macro_f1) (<code>float</code>) – The mean F1 over the three classes.
- [**confusion_matrix**](#agrag-eval-VerdictReport-confusion_matrix) (<code>list\[list\[int\]\]</code>) – Counts with gold classes as rows and predicted classes
  as columns. A prediction of `ERROR` is in no column.
- [**errors**](#agrag-eval-VerdictReport-errors) (<code>int</code>) – The number of `ERROR` predictions. Each one is a miss for
  the gold class of its item.

#### `agrag.eval.VerdictReport.confusion_matrix` \{#agrag-eval-VerdictReport-confusion_matrix}

```python
confusion_matrix: list[list[int]]
```

#### `agrag.eval.VerdictReport.errors` \{#agrag-eval-VerdictReport-errors}

```python
errors: int
```

#### `agrag.eval.VerdictReport.labels` \{#agrag-eval-VerdictReport-labels}

```python
labels: list[str]
```

#### `agrag.eval.VerdictReport.macro_f1` \{#agrag-eval-VerdictReport-macro_f1}

```python
macro_f1: float
```

#### `agrag.eval.VerdictReport.per_class` \{#agrag-eval-VerdictReport-per_class}

```python
per_class: dict[str, ClassScores]
```

### `agrag.eval.adapter` \{#agrag-eval-adapter}

Adapters that let plain scoring functions report through DeepEval.

**Classes:**

- [**ScoreMetric**](#agrag-eval-adapter-ScoreMetric) – A DeepEval metric backed by a plain scoring function.
- [**ScoreResult**](#agrag-eval-adapter-ScoreResult) – The outcome of one scoring function call.

**Functions:**

- [**parse_json_case**](#agrag-eval-adapter-parse_json_case) – Read the `(actual, expected)` models back from a JSON test case.
- [**to_json_case**](#agrag-eval-adapter-to_json_case) – Build a test case that carries structured data as JSON.

**Attributes:**

- [**ModelT**](#agrag-eval-adapter-ModelT) –

#### `agrag.eval.adapter.ModelT` \{#agrag-eval-adapter-ModelT}

```python
ModelT = TypeVar('ModelT', bound=BaseModel)
```

#### `agrag.eval.adapter.ScoreMetric` \{#agrag-eval-adapter-ScoreMetric}

```python
ScoreMetric(name:str, scorer:Callable[[LLMTestCase], ScoreResult], threshold:float = 0.5) -> None
```

Bases: <code>BaseMetric</code>

A DeepEval metric backed by a plain scoring function.

Use it for scores that DeepEval does not compute, such as F1 from
scikit-learn, so they report through the same `evaluate()` call.
If the scorer raises, the error is stored in `error` and raised again.

**Attributes:**

- [**name**](#agrag-eval-adapter-ScoreMetric-name) – The metric name shown in reports.
- [**scorer**](#agrag-eval-adapter-ScoreMetric-scorer) – The function that turns a test case into a `ScoreResult`.
- [**threshold**](#agrag-eval-adapter-ScoreMetric-threshold) – The minimum score that counts as success.

**Functions:**

- [**a_measure**](#agrag-eval-adapter-ScoreMetric-a_measure) – Run `measure`; scoring functions are synchronous.
- [**measure**](#agrag-eval-adapter-ScoreMetric-measure) – Run the scorer and record its score, reason and breakdown.

##### `agrag.eval.adapter.ScoreMetric.a_measure` \{#agrag-eval-adapter-ScoreMetric-a_measure}

```python
a_measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Run `measure`; scoring functions are synchronous.

##### `agrag.eval.adapter.ScoreMetric.measure` \{#agrag-eval-adapter-ScoreMetric-measure}

```python
measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Run the scorer and record its score, reason and breakdown.

##### `agrag.eval.adapter.ScoreMetric.name` \{#agrag-eval-adapter-ScoreMetric-name}

```python
name = name
```

##### `agrag.eval.adapter.ScoreMetric.scorer` \{#agrag-eval-adapter-ScoreMetric-scorer}

```python
scorer = scorer
```

##### `agrag.eval.adapter.ScoreMetric.threshold` \{#agrag-eval-adapter-ScoreMetric-threshold}

```python
threshold = threshold
```

#### `agrag.eval.adapter.ScoreResult` \{#agrag-eval-adapter-ScoreResult}

Bases: <code>NamedTuple</code>

The outcome of one scoring function call.

**Attributes:**

- [**score**](#agrag-eval-adapter-ScoreResult-score) (<code>float</code>) – The score, normally between 0 and 1.
- [**reason**](#agrag-eval-adapter-ScoreResult-reason) (<code>str</code>) – A short explanation shown in DeepEval reports.
- [**breakdown**](#agrag-eval-adapter-ScoreResult-breakdown) (<code>dict\[str, Any\]</code>) – Extra numbers behind the score, such as per-class values.

##### `agrag.eval.adapter.ScoreResult.breakdown` \{#agrag-eval-adapter-ScoreResult-breakdown}

```python
breakdown: dict[str, Any]
```

##### `agrag.eval.adapter.ScoreResult.reason` \{#agrag-eval-adapter-ScoreResult-reason}

```python
reason: str
```

##### `agrag.eval.adapter.ScoreResult.score` \{#agrag-eval-adapter-ScoreResult-score}

```python
score: float
```

#### `agrag.eval.adapter.parse_json_case` \{#agrag-eval-adapter-parse_json_case}

```python
parse_json_case(test_case:LLMTestCase, model:type[ModelT]) -> tuple[ModelT, ModelT]
```

Read the `(actual, expected)` models back from a JSON test case.

**Parameters:**

- **test_case** (<code>LLMTestCase</code>) – A case built by `to_json_case`.
- **model** (<code>type\[[ModelT](#agrag-eval-adapter-ModelT)\]</code>) – The pydantic model both outputs were serialized from.

#### `agrag.eval.adapter.to_json_case` \{#agrag-eval-adapter-to_json_case}

```python
to_json_case(input:str, actual:BaseModel, expected:BaseModel) -> LLMTestCase
```

Build a test case that carries structured data as JSON.

`LLMTestCase` has no field for structured gold data, so both models are
serialized to JSON in `actual_output` and `expected_output`. The JSON
also shows in DeepEval reports.

**Parameters:**

- **input** (<code>str</code>) – The input text, such as a question or a chunk.
- **actual** (<code>BaseModel</code>) – The system output.
- **expected** (<code>BaseModel</code>) – The gold data.

### `agrag.eval.answer` \{#agrag-eval-answer}

Answer-quality metrics for agrag, scored from questions and reference answers.

`answer_case` turns one agent run into a DeepEval test case. The four factories
build DeepEval metrics that run the judge once. `CitationAccuracyMetric` checks
each cited sentence against the evidence its citation keys point to.

All metrics judge against the evidence text the agent saw, as `Ledger.render`
shows it. A chunk shows in full, whatever its size.

**Classes:**

- [**CitationAccuracyMetric**](#agrag-eval-answer-CitationAccuracyMetric) – Score whether each cited sentence follows from the evidence it cites.
- [**CitationScoreBreakdown**](#agrag-eval-answer-CitationScoreBreakdown) – Available precision, recall, and sentence-count fields for one score.
- [**CitationSentenceRow**](#agrag-eval-answer-CitationSentenceRow) – One cited sentence and its support verdict, for the report.

**Functions:**

- [**answer_case**](#agrag-eval-answer-answer_case) – Build the test case that every answer-quality metric scores.
- [**context_precision**](#agrag-eval-answer-context_precision) – Build the metric for useful evidence ranked before noise.
- [**context_recall**](#agrag-eval-answer-context_recall) – Build the metric for reference facts that the evidence covers.
- [**correctness**](#agrag-eval-answer-correctness) – Build the answer correctness metric against the reference.
- [**faithfulness**](#agrag-eval-answer-faithfulness) – Build the metric for claims that the evidence the agent saw does not contradict.
- [**final_answer**](#agrag-eval-answer-final_answer) – Return the text of the last assistant message in an agent run.

**Attributes:**

- [**ABSTENTION**](#agrag-eval-answer-ABSTENTION) –

#### `agrag.eval.answer.ABSTENTION` \{#agrag-eval-answer-ABSTENTION}

```python
ABSTENTION = 'No relevant evidence found.'
```

#### `agrag.eval.answer.CitationAccuracyMetric` \{#agrag-eval-answer-CitationAccuracyMetric}

```python
CitationAccuracyMetric(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> None
```

Bases: <code>BaseMetric</code>

Score whether each cited sentence follows from the evidence it cites.

The unit is the sentence. A sentence counts as cited when it carries a
citation key. A judge decides whether the text of the cited evidence supports
the sentence. It scores each sentence with one `GEval` run. A cited key that
the run's ledger did not assign is fabricated: the sentence is unsupported and
no judge call happens.

The score is the F1 of two ratios. Precision is supported cited sentences
over cited sentences. Recall is supported cited sentences over all sentences
of at least four words, plus any shorter cited sentence. `score_breakdown`
holds both and the sentence counts. An answer with no citations scores 0. An
abstention, the exact text `No relevant evidence found.`, scores 1.
`score_breakdown` also holds one row per cited sentence with its keys,
fabricated flag, support verdict and judge reason.

The test case must come from `answer_case`, which puts the evidence under
`metadata["citations"]`. A judge failure on any sentence raises.

**Attributes:**

- [**judge**](#agrag-eval-answer-CitationAccuracyMetric-judge) – The judge model.
- [**threshold**](#agrag-eval-answer-CitationAccuracyMetric-threshold) – The minimum score that counts as success, and the minimum
  support score for one sentence.
- [**score_breakdown**](#agrag-eval-answer-CitationAccuracyMetric-score_breakdown) (<code>[CitationScoreBreakdown](#agrag-eval-answer-CitationScoreBreakdown)</code>) – Precision, recall, and sentence counts for the score.

**Functions:**

- [**a_measure**](#agrag-eval-answer-CitationAccuracyMetric-a_measure) – Judge the cited sentences with up to eight concurrent calls.
- [**measure**](#agrag-eval-answer-CitationAccuracyMetric-measure) – Judge the cited sentences one after the other.

##### `agrag.eval.answer.CitationAccuracyMetric.a_measure` \{#agrag-eval-answer-CitationAccuracyMetric-a_measure}

```python
a_measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Judge the cited sentences with up to eight concurrent calls.

**Parameters:**

- **test_case** (<code>LLMTestCase</code>) – The test case built by `answer_case`.
- \***args** (<code>Any</code>) – Additional positional arguments accepted by DeepEval.
- \*\***kwargs** (<code>Any</code>) – Additional keyword arguments accepted by DeepEval.

**Returns:**

- <code>float</code> – The citation accuracy score.

##### `agrag.eval.answer.CitationAccuracyMetric.judge` \{#agrag-eval-answer-CitationAccuracyMetric-judge}

```python
judge = judge
```

##### `agrag.eval.answer.CitationAccuracyMetric.measure` \{#agrag-eval-answer-CitationAccuracyMetric-measure}

```python
measure(test_case:LLMTestCase, *args:Any, **kwargs:Any) -> float
```

Judge the cited sentences one after the other.

**Parameters:**

- **test_case** (<code>LLMTestCase</code>) – The test case built by `answer_case`.
- \***args** (<code>Any</code>) – Additional positional arguments accepted by DeepEval.
- \*\***kwargs** (<code>Any</code>) – Additional keyword arguments accepted by DeepEval.

**Returns:**

- <code>float</code> – The citation accuracy score.

##### `agrag.eval.answer.CitationAccuracyMetric.score_breakdown` \{#agrag-eval-answer-CitationAccuracyMetric-score_breakdown}

```python
score_breakdown: CitationScoreBreakdown
```

##### `agrag.eval.answer.CitationAccuracyMetric.threshold` \{#agrag-eval-answer-CitationAccuracyMetric-threshold}

```python
threshold = threshold
```

#### `agrag.eval.answer.CitationScoreBreakdown` \{#agrag-eval-answer-CitationScoreBreakdown}

Bases: <code>TypedDict</code>

Available precision, recall, and sentence-count fields for one score.

All fields are optional because abstentions and uncited answers have partial
breakdowns.

**Attributes:**

- [**citation_precision**](#agrag-eval-answer-CitationScoreBreakdown-citation_precision) (<code>float</code>) – Fraction of cited sentences supported by evidence.
- [**citation_recall**](#agrag-eval-answer-CitationScoreBreakdown-citation_recall) (<code>float</code>) – Fraction of eligible sentences supported by evidence.
- [**cited_sentences**](#agrag-eval-answer-CitationScoreBreakdown-cited_sentences) (<code>int</code>) – Number of sentences with citations.
- [**supported_sentences**](#agrag-eval-answer-CitationScoreBreakdown-supported_sentences) (<code>int</code>) – Number of cited sentences supported by evidence.
- [**sentences**](#agrag-eval-answer-CitationScoreBreakdown-sentences) (<code>int</code>) – Number of eligible sentences in the answer.
- [**sentence_rows**](#agrag-eval-answer-CitationScoreBreakdown-sentence_rows) (<code>list\[[CitationSentenceRow](#agrag-eval-answer-CitationSentenceRow)\]</code>) – One row per cited sentence with its keys and verdict.

##### `agrag.eval.answer.CitationScoreBreakdown.citation_precision` \{#agrag-eval-answer-CitationScoreBreakdown-citation_precision}

```python
citation_precision: float
```

##### `agrag.eval.answer.CitationScoreBreakdown.citation_recall` \{#agrag-eval-answer-CitationScoreBreakdown-citation_recall}

```python
citation_recall: float
```

##### `agrag.eval.answer.CitationScoreBreakdown.cited_sentences` \{#agrag-eval-answer-CitationScoreBreakdown-cited_sentences}

```python
cited_sentences: int
```

##### `agrag.eval.answer.CitationScoreBreakdown.sentence_rows` \{#agrag-eval-answer-CitationScoreBreakdown-sentence_rows}

```python
sentence_rows: list[CitationSentenceRow]
```

##### `agrag.eval.answer.CitationScoreBreakdown.sentences` \{#agrag-eval-answer-CitationScoreBreakdown-sentences}

```python
sentences: int
```

##### `agrag.eval.answer.CitationScoreBreakdown.supported_sentences` \{#agrag-eval-answer-CitationScoreBreakdown-supported_sentences}

```python
supported_sentences: int
```

#### `agrag.eval.answer.CitationSentenceRow` \{#agrag-eval-answer-CitationSentenceRow}

Bases: <code>TypedDict</code>

One cited sentence and its support verdict, for the report.

**Attributes:**

- [**text**](#agrag-eval-answer-CitationSentenceRow-text) (<code>str</code>) – The sentence with its citation keys removed.
- [**keys**](#agrag-eval-answer-CitationSentenceRow-keys) (<code>list\[str\]</code>) – The keys the sentence cites, including bracketed keys the run
  never assigned. Empty only when the sentence cites no key-shaped
  token at all.
- [**fabricated**](#agrag-eval-answer-CitationSentenceRow-fabricated) (<code>bool</code>) – Whether the sentence cites a key the run never assigned.
- [**supported**](#agrag-eval-answer-CitationSentenceRow-supported) (<code>bool</code>) – Whether the cited evidence supports the sentence.
- [**reason**](#agrag-eval-answer-CitationSentenceRow-reason) (<code>str</code>) – The support judge's reason, or why no judge call happened.

##### `agrag.eval.answer.CitationSentenceRow.fabricated` \{#agrag-eval-answer-CitationSentenceRow-fabricated}

```python
fabricated: bool
```

##### `agrag.eval.answer.CitationSentenceRow.keys` \{#agrag-eval-answer-CitationSentenceRow-keys}

```python
keys: list[str]
```

##### `agrag.eval.answer.CitationSentenceRow.reason` \{#agrag-eval-answer-CitationSentenceRow-reason}

```python
reason: str
```

##### `agrag.eval.answer.CitationSentenceRow.supported` \{#agrag-eval-answer-CitationSentenceRow-supported}

```python
supported: bool
```

##### `agrag.eval.answer.CitationSentenceRow.text` \{#agrag-eval-answer-CitationSentenceRow-text}

```python
text: str
```

#### `agrag.eval.answer.answer_case` \{#agrag-eval-answer-answer_case}

```python
answer_case(question:str, result:AgentRunResult, reference:str) -> LLMTestCase
```

Build the test case that every answer-quality metric scores.

`retrieval_context` holds the evidence the agent saw, as the ledger
rendered it, in key order. `metadata["citations"]` maps each
key to that text for `CitationAccuracyMetric`.

**Parameters:**

- **question** (<code>str</code>) – The question the agent answered.
- **result** (<code>[AgentRunResult](agents.md#agrag-agents-result-AgentRunResult)</code>) – The result of `agent.ainvoke` for that question.
- **reference** (<code>str</code>) – The reference answer.

**Returns:**

- <code>LLMTestCase</code> – The test case with the answer and rendered evidence.

#### `agrag.eval.answer.context_precision` \{#agrag-eval-answer-context_precision}

```python
context_precision(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the metric for useful evidence ranked before noise.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The context precision metric.

#### `agrag.eval.answer.context_recall` \{#agrag-eval-answer-context_recall}

```python
context_recall(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the metric for reference facts that the evidence covers.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The context recall metric.

#### `agrag.eval.answer.correctness` \{#agrag-eval-answer-correctness}

```python
correctness(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the answer correctness metric against the reference.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The correctness metric.

#### `agrag.eval.answer.faithfulness` \{#agrag-eval-answer-faithfulness}

```python
faithfulness(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the metric for claims that the evidence the agent saw does not contradict.

A claim that the evidence does not mention counts as faithful. Only a claim
that the evidence contradicts lowers the score. `CitationAccuracyMetric`
catches unsupported claims.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The faithfulness metric.

#### `agrag.eval.answer.final_answer` \{#agrag-eval-answer-final_answer}

```python
final_answer(result:AgentRunResult) -> str
```

Return the text of the last assistant message in an agent run.

Handles message dicts and LangChain message objects, and content that is a
string or a list of blocks. Only text blocks count.

**Parameters:**

- **result** (<code>[AgentRunResult](agents.md#agrag-agents-result-AgentRunResult)</code>) – The result of `agent.ainvoke`.

**Raises:**

- <code>ValueError</code> – The run holds no assistant message.

### `agrag.eval.answer_case` \{#agrag-eval-answer_case}

```python
answer_case(question:str, result:AgentRunResult, reference:str) -> LLMTestCase
```

Build the test case that every answer-quality metric scores.

`retrieval_context` holds the evidence the agent saw, as the ledger
rendered it, in key order. `metadata["citations"]` maps each
key to that text for `CitationAccuracyMetric`.

**Parameters:**

- **question** (<code>str</code>) – The question the agent answered.
- **result** (<code>[AgentRunResult](agents.md#agrag-agents-result-AgentRunResult)</code>) – The result of `agent.ainvoke` for that question.
- **reference** (<code>str</code>) – The reference answer.

**Returns:**

- <code>LLMTestCase</code> – The test case with the answer and rendered evidence.

### `agrag.eval.cluster_quality_metric` \{#agrag-eval-cluster_quality_metric}

```python
cluster_quality_metric(*, threshold:float = 0.5) -> ScoreMetric
```

Build a metric for cluster quality on one test case.

The score is B-cubed F1. The breakdown holds `b_cubed_precision`,
`b_cubed_recall`, `pairwise_precision`, `pairwise_recall` and
`pairwise_f`. An over-merge lowers precision and an under-merge lowers
recall. The score of a whole dataset is the score of one case that holds
all its mentions, because pooling clusters from separate cases is not
defined.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A metric that scores one case from `resolution_case`.

### `agrag.eval.context_precision` \{#agrag-eval-context_precision}

```python
context_precision(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the metric for useful evidence ranked before noise.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The context precision metric.

### `agrag.eval.context_recall` \{#agrag-eval-context_recall}

```python
context_recall(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the metric for reference facts that the evidence covers.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The context recall metric.

### `agrag.eval.correctness` \{#agrag-eval-correctness}

```python
correctness(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the answer correctness metric against the reference.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The correctness metric.

### `agrag.eval.entity_quality_metric` \{#agrag-eval-entity_quality_metric}

```python
entity_quality_metric(*, threshold:float = 0.0) -> ScoreMetric
```

Build a metric for entity F1 on one test case.

The case score is the exact F1. Use a new metric for each case, and pass the
measured metrics to `micro_scores`. The default threshold is 0 because the
gate belongs on the dataset score.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum case score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A metric that scores exact entity F1 for one case.

### `agrag.eval.expected_tools_metric` \{#agrag-eval-expected_tools_metric}

```python
expected_tools_metric(names:Sequence[str], *, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that the run called every expected tool.

Compares the trajectory's tool calls with the expected names as a
superset, ignoring arguments: extra tools do not matter, a missing name
fails. Scores 1.0 or 0.0.

**Parameters:**

- **names** (<code>Sequence\[str\]</code>) – The tool names the run must include.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A `ScoreMetric` that scores tool presence.

### `agrag.eval.extraction` \{#agrag-eval-extraction}

Extraction quality: entity and relation-triple F1 against gold annotations.

A gold annotation for one chunk is a hand-written `ExtractionResult`. Scoring
has two steps. First, each predicted entity is aligned to a gold entity of the
same label. Second, each predicted relation is mapped through that alignment to
gold entity indices and compared as a `(source, label, target)` triple. Exact
alignment needs the same character span. Relaxed alignment needs an overlap
(intersection over union) of at least 0.5. Both are one to one: when several
predictions overlap gold entities, alignment maximizes valid pairs and then
total overlap. Unaligned predictions count as false positives.

Every case reports exact and relaxed results. The exact score gates. A large gap
between the two shows a span boundary problem, not a missed entity. The
counting is scikit-learn's `precision_recall_fscore_support`. Use
`micro_scores` for the dataset score, because a mean of per-chunk scores
weights a short chunk the same as a long one.

**Classes:**

- [**EntityBreakdown**](#agrag-eval-extraction-EntityBreakdown) – The `score_breakdown` of an entity quality metric for one case.
- [**ExtractionGold**](#agrag-eval-extraction-ExtractionGold) – One gold-annotated chunk of text.
- [**LabelCounts**](#agrag-eval-extraction-LabelCounts) – True positives, false positives and false negatives for one entity label.
- [**MicroScores**](#agrag-eval-extraction-MicroScores) – Dataset scores pooled over every item, for entities and relations.
- [**RelationBreakdown**](#agrag-eval-extraction-RelationBreakdown) – The `score_breakdown` of a relation quality metric for one case.
- [**Scores**](#agrag-eval-extraction-Scores) – Precision, recall and F1.

**Functions:**

- [**entity_quality_metric**](#agrag-eval-extraction-entity_quality_metric) – Build a metric for entity F1 on one test case.
- [**extraction_case**](#agrag-eval-extraction-extraction_case) – Build a test case that holds a predicted and a gold extraction.
- [**micro_scores**](#agrag-eval-extraction-micro_scores) – Pool measured entity and relation metrics into dataset scores.
- [**relation_quality_metric**](#agrag-eval-extraction-relation_quality_metric) – Build a metric for relation triple F1 on one test case.
- [**run_extractor**](#agrag-eval-extraction-run_extractor) – Run an extractor over gold items and build one test case per item.

#### `agrag.eval.extraction.EntityBreakdown` \{#agrag-eval-extraction-EntityBreakdown}

Bases: <code>[RelationBreakdown](#agrag-eval-extraction-RelationBreakdown)</code>

The `score_breakdown` of an entity quality metric for one case.

`per_label` counts the exact-match results for each entity label.

**Attributes:**

- [**kind**](#agrag-eval-extraction-EntityBreakdown-kind) (<code>Literal['entity', 'relation']</code>) –
- [**per_label**](#agrag-eval-extraction-EntityBreakdown-per_label) (<code>dict\[str, [LabelCounts](#agrag-eval-extraction-LabelCounts)\]</code>) –
- [**relaxed_y_pred**](#agrag-eval-extraction-EntityBreakdown-relaxed_y_pred) (<code>list\[int\]</code>) –
- [**relaxed_y_true**](#agrag-eval-extraction-EntityBreakdown-relaxed_y_true) (<code>list\[int\]</code>) –
- [**y_pred**](#agrag-eval-extraction-EntityBreakdown-y_pred) (<code>list\[int\]</code>) –
- [**y_true**](#agrag-eval-extraction-EntityBreakdown-y_true) (<code>list\[int\]</code>) –

##### `agrag.eval.extraction.EntityBreakdown.kind` \{#agrag-eval-extraction-EntityBreakdown-kind}

```python
kind: Literal['entity', 'relation']
```

##### `agrag.eval.extraction.EntityBreakdown.per_label` \{#agrag-eval-extraction-EntityBreakdown-per_label}

```python
per_label: dict[str, LabelCounts]
```

##### `agrag.eval.extraction.EntityBreakdown.relaxed_y_pred` \{#agrag-eval-extraction-EntityBreakdown-relaxed_y_pred}

```python
relaxed_y_pred: list[int]
```

##### `agrag.eval.extraction.EntityBreakdown.relaxed_y_true` \{#agrag-eval-extraction-EntityBreakdown-relaxed_y_true}

```python
relaxed_y_true: list[int]
```

##### `agrag.eval.extraction.EntityBreakdown.y_pred` \{#agrag-eval-extraction-EntityBreakdown-y_pred}

```python
y_pred: list[int]
```

##### `agrag.eval.extraction.EntityBreakdown.y_true` \{#agrag-eval-extraction-EntityBreakdown-y_true}

```python
y_true: list[int]
```

#### `agrag.eval.extraction.ExtractionGold` \{#agrag-eval-extraction-ExtractionGold}

Bases: <code>BaseModel</code>

One gold-annotated chunk of text.

**Attributes:**

- [**id**](#agrag-eval-extraction-ExtractionGold-id) (<code>str</code>) – A stable id for the item. It seeds the chunk and document ids.
- [**text**](#agrag-eval-extraction-ExtractionGold-text) (<code>str</code>) – The chunk text the extractor reads.
- [**gold**](#agrag-eval-extraction-ExtractionGold-gold) (<code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code>) – The annotation. Entity offsets index into `text`.

##### `agrag.eval.extraction.ExtractionGold.gold` \{#agrag-eval-extraction-ExtractionGold-gold}

```python
gold: ExtractionResult
```

##### `agrag.eval.extraction.ExtractionGold.id` \{#agrag-eval-extraction-ExtractionGold-id}

```python
id: str
```

##### `agrag.eval.extraction.ExtractionGold.text` \{#agrag-eval-extraction-ExtractionGold-text}

```python
text: str
```

#### `agrag.eval.extraction.LabelCounts` \{#agrag-eval-extraction-LabelCounts}

Bases: <code>TypedDict</code>

True positives, false positives and false negatives for one entity label.

**Attributes:**

- [**fn**](#agrag-eval-extraction-LabelCounts-fn) (<code>int</code>) –
- [**fp**](#agrag-eval-extraction-LabelCounts-fp) (<code>int</code>) –
- [**tp**](#agrag-eval-extraction-LabelCounts-tp) (<code>int</code>) –

##### `agrag.eval.extraction.LabelCounts.fn` \{#agrag-eval-extraction-LabelCounts-fn}

```python
fn: int
```

##### `agrag.eval.extraction.LabelCounts.fp` \{#agrag-eval-extraction-LabelCounts-fp}

```python
fp: int
```

##### `agrag.eval.extraction.LabelCounts.tp` \{#agrag-eval-extraction-LabelCounts-tp}

```python
tp: int
```

#### `agrag.eval.extraction.MicroScores` \{#agrag-eval-extraction-MicroScores}

Bases: <code>BaseModel</code>

Dataset scores pooled over every item, for entities and relations.

**Attributes:**

- [**entities_exact**](#agrag-eval-extraction-MicroScores-entities_exact) (<code>[Scores](#agrag-eval-extraction-Scores)</code>) – Entity scores with exact span matching.
- [**entities_relaxed**](#agrag-eval-extraction-MicroScores-entities_relaxed) (<code>[Scores](#agrag-eval-extraction-Scores)</code>) – Entity scores with overlap of at least 0.5.
- [**relations_exact**](#agrag-eval-extraction-MicroScores-relations_exact) (<code>[Scores](#agrag-eval-extraction-Scores)</code>) – Relation triple scores over exact entity alignment.
- [**relations_relaxed**](#agrag-eval-extraction-MicroScores-relations_relaxed) (<code>[Scores](#agrag-eval-extraction-Scores)</code>) – Relation triple scores over relaxed entity alignment.

##### `agrag.eval.extraction.MicroScores.entities_exact` \{#agrag-eval-extraction-MicroScores-entities_exact}

```python
entities_exact: Scores
```

##### `agrag.eval.extraction.MicroScores.entities_relaxed` \{#agrag-eval-extraction-MicroScores-entities_relaxed}

```python
entities_relaxed: Scores
```

##### `agrag.eval.extraction.MicroScores.relations_exact` \{#agrag-eval-extraction-MicroScores-relations_exact}

```python
relations_exact: Scores
```

##### `agrag.eval.extraction.MicroScores.relations_relaxed` \{#agrag-eval-extraction-MicroScores-relations_relaxed}

```python
relations_relaxed: Scores
```

#### `agrag.eval.extraction.RelationBreakdown` \{#agrag-eval-extraction-RelationBreakdown}

Bases: <code>TypedDict</code>

The `score_breakdown` of a relation quality metric for one case.

The label lists are 0/1 values over the union of gold and predicted items:
`y_true` marks gold items and `y_pred` marks predicted ones. The
`relaxed_` lists use an overlap of at least 0.5 to align entities.

**Attributes:**

- [**kind**](#agrag-eval-extraction-RelationBreakdown-kind) (<code>Literal['entity', 'relation']</code>) –
- [**relaxed_y_pred**](#agrag-eval-extraction-RelationBreakdown-relaxed_y_pred) (<code>list\[int\]</code>) –
- [**relaxed_y_true**](#agrag-eval-extraction-RelationBreakdown-relaxed_y_true) (<code>list\[int\]</code>) –
- [**y_pred**](#agrag-eval-extraction-RelationBreakdown-y_pred) (<code>list\[int\]</code>) –
- [**y_true**](#agrag-eval-extraction-RelationBreakdown-y_true) (<code>list\[int\]</code>) –

##### `agrag.eval.extraction.RelationBreakdown.kind` \{#agrag-eval-extraction-RelationBreakdown-kind}

```python
kind: Literal['entity', 'relation']
```

##### `agrag.eval.extraction.RelationBreakdown.relaxed_y_pred` \{#agrag-eval-extraction-RelationBreakdown-relaxed_y_pred}

```python
relaxed_y_pred: list[int]
```

##### `agrag.eval.extraction.RelationBreakdown.relaxed_y_true` \{#agrag-eval-extraction-RelationBreakdown-relaxed_y_true}

```python
relaxed_y_true: list[int]
```

##### `agrag.eval.extraction.RelationBreakdown.y_pred` \{#agrag-eval-extraction-RelationBreakdown-y_pred}

```python
y_pred: list[int]
```

##### `agrag.eval.extraction.RelationBreakdown.y_true` \{#agrag-eval-extraction-RelationBreakdown-y_true}

```python
y_true: list[int]
```

#### `agrag.eval.extraction.Scores` \{#agrag-eval-extraction-Scores}

Bases: <code>BaseModel</code>

Precision, recall and F1.

**Attributes:**

- [**precision**](#agrag-eval-extraction-Scores-precision) (<code>float</code>) – Correct predictions over all predictions.
- [**recall**](#agrag-eval-extraction-Scores-recall) (<code>float</code>) – Correct predictions over all gold items.
- [**f1**](#agrag-eval-extraction-Scores-f1) (<code>float</code>) – The harmonic mean of precision and recall.

##### `agrag.eval.extraction.Scores.f1` \{#agrag-eval-extraction-Scores-f1}

```python
f1: float
```

##### `agrag.eval.extraction.Scores.precision` \{#agrag-eval-extraction-Scores-precision}

```python
precision: float
```

##### `agrag.eval.extraction.Scores.recall` \{#agrag-eval-extraction-Scores-recall}

```python
recall: float
```

#### `agrag.eval.extraction.entity_quality_metric` \{#agrag-eval-extraction-entity_quality_metric}

```python
entity_quality_metric(*, threshold:float = 0.0) -> ScoreMetric
```

Build a metric for entity F1 on one test case.

The case score is the exact F1. Use a new metric for each case, and pass the
measured metrics to `micro_scores`. The default threshold is 0 because the
gate belongs on the dataset score.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum case score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A metric that scores exact entity F1 for one case.

#### `agrag.eval.extraction.extraction_case` \{#agrag-eval-extraction-extraction_case}

```python
extraction_case(chunk_text:str, predicted:ExtractionResult, gold:ExtractionResult) -> LLMTestCase
```

Build a test case that holds a predicted and a gold extraction.

**Parameters:**

- **chunk_text** (<code>str</code>) – The text the extractor read.
- **predicted** (<code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code>) – The extractor output.
- **gold** (<code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code>) – The gold annotation.

**Returns:**

- <code>LLMTestCase</code> – A test case with serialized predicted and gold extractions.

#### `agrag.eval.extraction.micro_scores` \{#agrag-eval-extraction-micro_scores}

```python
micro_scores(metrics:Iterable[ScoreMetric]) -> MicroScores
```

Pool measured entity and relation metrics into dataset scores.

**Parameters:**

- **metrics** (<code>Iterable\[[ScoreMetric](#agrag-eval-adapter-ScoreMetric)\]</code>) – Metrics from `entity_quality_metric` and
  `relation_quality_metric`, after `measure`.

**Returns:**

- <code>[MicroScores](#agrag-eval-extraction-MicroScores)</code> – Pooled exact and relaxed scores for entities and relations.

**Raises:**

- <code>ValueError</code> – No entity metric or no relation metric was given.

#### `agrag.eval.extraction.relation_quality_metric` \{#agrag-eval-extraction-relation_quality_metric}

```python
relation_quality_metric(*, symmetric_labels:frozenset[str] = frozenset(), threshold:float = 0.0) -> ScoreMetric
```

Build a metric for relation triple F1 on one test case.

A relation counts only when both endpoints align to gold entities and the
triple is in gold. Use a new metric for each case.

**Parameters:**

- **symmetric_labels** (<code>frozenset\[str\]</code>) – Relation labels with no direction. Their two endpoints
  are sorted before comparison.
- **threshold** (<code>float</code>) – The minimum case score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A metric that scores exact relation F1 for one case.

#### `agrag.eval.extraction.run_extractor` \{#agrag-eval-extraction-run_extractor}

```python
run_extractor(extractor:Extractor, items:Sequence[ExtractionGold], schema:GraphSchema, *, concurrency:int = _CONCURRENCY) -> list[LLMTestCase]
```

Run an extractor over gold items and build one test case per item.

Chunk and document ids come from the item id, so runs are repeatable.

**Parameters:**

- **extractor** (<code>[Extractor](ingestion.md#agrag-ingestion-extract-Extractor)</code>) – The extractor under test.
- **items** (<code>Sequence\[[ExtractionGold](#agrag-eval-extraction-ExtractionGold)\]</code>) – The gold-annotated chunks.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The schema the extractor works to.
- **concurrency** (<code>int</code>) – The most extractor calls that run at once. Lower it for an
  endpoint that limits concurrent requests.

**Returns:**

- <code>list\[LLMTestCase\]</code> – One test case per item, in the order of `items`.

**Raises:**

- <code>ValueError</code> – `concurrency` is less than 1.

### `agrag.eval.extraction_case` \{#agrag-eval-extraction_case}

```python
extraction_case(chunk_text:str, predicted:ExtractionResult, gold:ExtractionResult) -> LLMTestCase
```

Build a test case that holds a predicted and a gold extraction.

**Parameters:**

- **chunk_text** (<code>str</code>) – The text the extractor read.
- **predicted** (<code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code>) – The extractor output.
- **gold** (<code>[ExtractionResult](common.md#agrag-common-data_models-extraction-ExtractionResult)</code>) – The gold annotation.

**Returns:**

- <code>LLMTestCase</code> – A test case with serialized predicted and gold extractions.

### `agrag.eval.faithfulness` \{#agrag-eval-faithfulness}

```python
faithfulness(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the metric for claims that the evidence the agent saw does not contradict.

A claim that the evidence does not mention counts as faithful. Only a claim
that the evidence contradicts lowers the score. `CitationAccuracyMetric`
catches unsupported claims.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The faithfulness metric.

### `agrag.eval.final_answer` \{#agrag-eval-final_answer}

```python
final_answer(result:AgentRunResult) -> str
```

Return the text of the last assistant message in an agent run.

Handles message dicts and LangChain message objects, and content that is a
string or a list of blocks. Only text blocks count.

**Parameters:**

- **result** (<code>[AgentRunResult](agents.md#agrag-agents-result-AgentRunResult)</code>) – The result of `agent.ainvoke`.

**Raises:**

- <code>ValueError</code> – The run holds no assistant message.

### `agrag.eval.judge` \{#agrag-eval-judge}

A DeepEval judge model backed by an agrag chat model.

**Classes:**

- [**ChatModelJudge**](#agrag-eval-judge-ChatModelJudge) – Wrap a LangChain chat model as a DeepEval judge.

#### `agrag.eval.judge.ChatModelJudge` \{#agrag-eval-judge-ChatModelJudge}

```python
ChatModelJudge(chat_model:Any, name:str, *, tracer:Tracer | None = None) -> None
```

Bases: <code>DeepEvalBaseLLM</code>

Wrap a LangChain chat model as a DeepEval judge.

Pass an instance as `model=` to any DeepEval metric. With a `schema`,
`generate` returns an instance of it. Without one, it returns the reply
text. Provider errors surface unchanged.

**Functions:**

- [**a_generate**](#agrag-eval-judge-ChatModelJudge-a_generate) – Run one judge call asynchronously. See `generate`.
- [**from_settings**](#agrag-eval-judge-ChatModelJudge-from_settings) – Build a judge from settings.
- [**generate**](#agrag-eval-judge-ChatModelJudge-generate) – Run one judge call, returning a `schema` instance or the reply text.
- [**get_model_name**](#agrag-eval-judge-ChatModelJudge-get_model_name) – Return the judge's model id.
- [**load_model**](#agrag-eval-judge-ChatModelJudge-load_model) – Return the wrapped chat model.

##### `agrag.eval.judge.ChatModelJudge.a_generate` \{#agrag-eval-judge-ChatModelJudge-a_generate}

```python
a_generate(prompt:str, schema:type[BaseModel] | None = None) -> Any
```

Run one judge call asynchronously. See `generate`.

##### `agrag.eval.judge.ChatModelJudge.from_settings` \{#agrag-eval-judge-ChatModelJudge-from_settings}

```python
from_settings(settings:EvalJudgeSettings, *, tracer:Tracer | None = None) -> ChatModelJudge
```

Build a judge from settings.

The chat model is copied with `settings.temperature` set. When that
is `None`, no temperature is set. A model that rejects the
parameter then needs `EVAL_JUDGE_TEMPERATURE` empty.

**Parameters:**

- **settings** (<code>[EvalJudgeSettings](#agrag-eval-settings-EvalJudgeSettings)</code>) – The judge client config and temperature.
- **tracer** (<code>Tracer | None</code>) – Receives OpenInference spans for every judge call.
  None emits no spans.

##### `agrag.eval.judge.ChatModelJudge.generate` \{#agrag-eval-judge-ChatModelJudge-generate}

```python
generate(prompt:str, schema:type[BaseModel] | None = None) -> Any
```

Run one judge call, returning a `schema` instance or the reply text.

##### `agrag.eval.judge.ChatModelJudge.get_model_name` \{#agrag-eval-judge-ChatModelJudge-get_model_name}

```python
get_model_name() -> str
```

Return the judge's model id.

##### `agrag.eval.judge.ChatModelJudge.load_model` \{#agrag-eval-judge-ChatModelJudge-load_model}

```python
load_model() -> Any
```

Return the wrapped chat model.

### `agrag.eval.micro_scores` \{#agrag-eval-micro_scores}

```python
micro_scores(metrics:Iterable[ScoreMetric]) -> MicroScores
```

Pool measured entity and relation metrics into dataset scores.

**Parameters:**

- **metrics** (<code>Iterable\[[ScoreMetric](#agrag-eval-adapter-ScoreMetric)\]</code>) – Metrics from `entity_quality_metric` and
  `relation_quality_metric`, after `measure`.

**Returns:**

- <code>[MicroScores](#agrag-eval-extraction-MicroScores)</code> – Pooled exact and relaxed scores for entities and relations.

**Raises:**

- <code>ValueError</code> – No entity metric or no relation metric was given.

### `agrag.eval.parse_json_case` \{#agrag-eval-parse_json_case}

```python
parse_json_case(test_case:LLMTestCase, model:type[ModelT]) -> tuple[ModelT, ModelT]
```

Read the `(actual, expected)` models back from a JSON test case.

**Parameters:**

- **test_case** (<code>LLMTestCase</code>) – A case built by `to_json_case`.
- **model** (<code>type\[[ModelT](#agrag-eval-adapter-ModelT)\]</code>) – The pydantic model both outputs were serialized from.

### `agrag.eval.read_trajectory` \{#agrag-eval-read_trajectory}

```python
read_trajectory(spans:Sequence[ReadableSpan]) -> Trajectory
```

Read the tool and model steps from finished spans.

Keeps `TOOL` and `LLM` spans, drops `CHAIN` spans, and orders steps
by start time rather than export order. Skips spans `agrag` opens
itself and spans nested under an `agrag.eval.judge` span, so judge
calls and BAML request spans never read as planner steps. A step's
`subagent` is the `subagent_type` of its nearest ancestor `task`
span, or None for a planner step.

**Parameters:**

- **spans** (<code>Sequence\[ReadableSpan\]</code>) – The finished spans of one traced agent run.

**Returns:**

- <code>[Trajectory](#agrag-eval-trajectory-Trajectory)</code> – The run's trajectory in start order.

### `agrag.eval.relation_quality_metric` \{#agrag-eval-relation_quality_metric}

```python
relation_quality_metric(*, symmetric_labels:frozenset[str] = frozenset(), threshold:float = 0.0) -> ScoreMetric
```

Build a metric for relation triple F1 on one test case.

A relation counts only when both endpoints align to gold entities and the
triple is in gold. Use a new metric for each case.

**Parameters:**

- **symmetric_labels** (<code>frozenset\[str\]</code>) – Relation labels with no direction. Their two endpoints
  are sorted before comparison.
- **threshold** (<code>float</code>) – The minimum case score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A metric that scores exact relation F1 for one case.

### `agrag.eval.resolution` \{#agrag-eval-resolution}

Resolution quality: B-cubed and pairwise scores of mention clusters.

`run_resolver` sends mention strings through a `Resolver` and returns the
clusters it forms. `cluster_quality_metric` compares those clusters with gold
clusters. The score is B-cubed F1. The breakdown also holds B-cubed precision
and recall and pairwise precision, recall and F1. The counting is
`er-evaluation`'s.

Both sides list mentions by index. A mention that is in no cluster is a cluster
of one, so a gold set can list only its multi-mention clusters.

**Classes:**

- [**ClusterAssignment**](#agrag-eval-resolution-ClusterAssignment) – A grouping of mentions, listed by position in the mention list.

**Functions:**

- [**cluster_quality_metric**](#agrag-eval-resolution-cluster_quality_metric) – Build a metric for cluster quality on one test case.
- [**resolution_case**](#agrag-eval-resolution-resolution_case) – Build a test case that holds predicted and gold clusters.
- [**run_resolver**](#agrag-eval-resolution-run_resolver) – Resolve mention strings and return the clusters the resolver forms.
- [**run_resolver_detailed**](#agrag-eval-resolution-run_resolver_detailed) – Resolve mention strings and return the clusters plus raw evidence.

#### `agrag.eval.resolution.ClusterAssignment` \{#agrag-eval-resolution-ClusterAssignment}

Bases: <code>BaseModel</code>

A grouping of mentions, listed by position in the mention list.

**Attributes:**

- [**size**](#agrag-eval-resolution-ClusterAssignment-size) (<code>int</code>) – The number of mentions.
- [**clusters**](#agrag-eval-resolution-ClusterAssignment-clusters) (<code>list\[list\[int\]\]</code>) – Groups of mention indices. An index in no group is a cluster
  of one.
- [**matches_by_tier**](#agrag-eval-resolution-ClusterAssignment-matches_by_tier) (<code>dict\[str, int\]</code>) – How many confirmed non-exact matches each comparator
  made. Empty for gold clusters.
- [**failed_llm_requests**](#agrag-eval-resolution-ClusterAssignment-failed_llm_requests) (<code>int</code>) – LLM verification requests that errored and were
  mapped to "no match". Zero on gold clusters.

##### `agrag.eval.resolution.ClusterAssignment.clusters` \{#agrag-eval-resolution-ClusterAssignment-clusters}

```python
clusters: list[list[int]]
```

##### `agrag.eval.resolution.ClusterAssignment.failed_llm_requests` \{#agrag-eval-resolution-ClusterAssignment-failed_llm_requests}

```python
failed_llm_requests: int = 0
```

##### `agrag.eval.resolution.ClusterAssignment.matches_by_tier` \{#agrag-eval-resolution-ClusterAssignment-matches_by_tier}

```python
matches_by_tier: dict[str, int] = {}
```

##### `agrag.eval.resolution.ClusterAssignment.size` \{#agrag-eval-resolution-ClusterAssignment-size}

```python
size: int
```

#### `agrag.eval.resolution.cluster_quality_metric` \{#agrag-eval-resolution-cluster_quality_metric}

```python
cluster_quality_metric(*, threshold:float = 0.5) -> ScoreMetric
```

Build a metric for cluster quality on one test case.

The score is B-cubed F1. The breakdown holds `b_cubed_precision`,
`b_cubed_recall`, `pairwise_precision`, `pairwise_recall` and
`pairwise_f`. An over-merge lowers precision and an under-merge lowers
recall. The score of a whole dataset is the score of one case that holds
all its mentions, because pooling clusters from separate cases is not
defined.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A metric that scores one case from `resolution_case`.

#### `agrag.eval.resolution.resolution_case` \{#agrag-eval-resolution-resolution_case}

```python
resolution_case(mentions:Sequence[str], predicted:ClusterAssignment, gold:ClusterAssignment) -> LLMTestCase
```

Build a test case that holds predicted and gold clusters.

**Parameters:**

- **mentions** (<code>Sequence\[str\]</code>) – The mention texts. They show in DeepEval reports.
- **predicted** (<code>[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment)</code>) – The clusters the resolver formed.
- **gold** (<code>[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment)</code>) – The gold clusters.

**Returns:**

- <code>LLMTestCase</code> – A test case with serialized predicted and gold clusters.

#### `agrag.eval.resolution.run_resolver` \{#agrag-eval-resolution-run_resolver}

```python
run_resolver(resolver:Resolver, mentions:Sequence[str], *, label:str = 'Organization') -> ClusterAssignment
```

Resolve mention strings and return the clusters the resolver forms.

See `run_resolver_detailed` for the chunk construction. Use that variant
when a caller also needs the raw `ResolutionResult` evidence.

**Parameters:**

- **resolver** (<code>[Resolver](ingestion.md#agrag-ingestion-resolve-resolver-Resolver)</code>) – The resolver under test.
- **mentions** (<code>Sequence\[str\]</code>) – The mention texts.
- **label** (<code>str</code>) – The entity label given to every mention.

**Returns:**

- <code>[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment)</code> – The predicted clusters, the count of matches per comparator, and
- <code>[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment)</code> – the count of failed LLM requests.

#### `agrag.eval.resolution.run_resolver_detailed` \{#agrag-eval-resolution-run_resolver_detailed}

```python
run_resolver_detailed(resolver:Resolver, mentions:Sequence[str], *, label:str = 'Organization') -> tuple[ClusterAssignment, ResolutionResult]
```

Resolve mention strings and return the clusters plus raw evidence.

Each mention becomes one entity in its own chunk. The chunk holds only the
mention text, and is registered with any `LLMVerify` comparator of the
resolver so the comparator can look it up. Chunk ids come from the mention
position, so runs are repeatable.

**Parameters:**

- **resolver** (<code>[Resolver](ingestion.md#agrag-ingestion-resolve-resolver-Resolver)</code>) – The resolver under test.
- **mentions** (<code>Sequence\[str\]</code>) – The mention texts.
- **label** (<code>str</code>) – The entity label given to every mention.

**Returns:**

- <code>[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment)</code> – The predicted clusters with the counts of matches per comparator and
- <code>[ResolutionResult](ingestion.md#agrag-ingestion-resolve-resolver-ResolutionResult)</code> – of failed LLM requests, and the raw `ResolutionResult` whose match
- <code>tuple\[[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment), [ResolutionResult](ingestion.md#agrag-ingestion-resolve-resolver-ResolutionResult)\]</code> – records carry the comparator that confirmed each pair.

### `agrag.eval.resolution_case` \{#agrag-eval-resolution_case}

```python
resolution_case(mentions:Sequence[str], predicted:ClusterAssignment, gold:ClusterAssignment) -> LLMTestCase
```

Build a test case that holds predicted and gold clusters.

**Parameters:**

- **mentions** (<code>Sequence\[str\]</code>) – The mention texts. They show in DeepEval reports.
- **predicted** (<code>[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment)</code>) – The clusters the resolver formed.
- **gold** (<code>[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment)</code>) – The gold clusters.

**Returns:**

- <code>LLMTestCase</code> – A test case with serialized predicted and gold clusters.

### `agrag.eval.retry_budget_metric` \{#agrag-eval-retry_budget_metric}

```python
retry_budget_metric(max_attempts:int, *, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that retries stay within budget.

Counts researcher `task` spans starting after the first verifier
`task` span ended. A call the limiter blocks leaves no span, so only
executed delegations count. Scores 1.0 or 0.0.

**Parameters:**

- **max_attempts** (<code>int</code>) – How many researcher retries after verification pass.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A `ScoreMetric` that scores the retry budget.

### `agrag.eval.run_extractor` \{#agrag-eval-run_extractor}

```python
run_extractor(extractor:Extractor, items:Sequence[ExtractionGold], schema:GraphSchema, *, concurrency:int = _CONCURRENCY) -> list[LLMTestCase]
```

Run an extractor over gold items and build one test case per item.

Chunk and document ids come from the item id, so runs are repeatable.

**Parameters:**

- **extractor** (<code>[Extractor](ingestion.md#agrag-ingestion-extract-Extractor)</code>) – The extractor under test.
- **items** (<code>Sequence\[[ExtractionGold](#agrag-eval-extraction-ExtractionGold)\]</code>) – The gold-annotated chunks.
- **schema** (<code>[GraphSchema](common.md#agrag-common-data_models-graph_schema-GraphSchema)</code>) – The schema the extractor works to.
- **concurrency** (<code>int</code>) – The most extractor calls that run at once. Lower it for an
  endpoint that limits concurrent requests.

**Returns:**

- <code>list\[LLMTestCase\]</code> – One test case per item, in the order of `items`.

**Raises:**

- <code>ValueError</code> – `concurrency` is less than 1.

### `agrag.eval.run_resolver` \{#agrag-eval-run_resolver}

```python
run_resolver(resolver:Resolver, mentions:Sequence[str], *, label:str = 'Organization') -> ClusterAssignment
```

Resolve mention strings and return the clusters the resolver forms.

See `run_resolver_detailed` for the chunk construction. Use that variant
when a caller also needs the raw `ResolutionResult` evidence.

**Parameters:**

- **resolver** (<code>[Resolver](ingestion.md#agrag-ingestion-resolve-resolver-Resolver)</code>) – The resolver under test.
- **mentions** (<code>Sequence\[str\]</code>) – The mention texts.
- **label** (<code>str</code>) – The entity label given to every mention.

**Returns:**

- <code>[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment)</code> – The predicted clusters, the count of matches per comparator, and
- <code>[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment)</code> – the count of failed LLM requests.

### `agrag.eval.run_resolver_detailed` \{#agrag-eval-run_resolver_detailed}

```python
run_resolver_detailed(resolver:Resolver, mentions:Sequence[str], *, label:str = 'Organization') -> tuple[ClusterAssignment, ResolutionResult]
```

Resolve mention strings and return the clusters plus raw evidence.

Each mention becomes one entity in its own chunk. The chunk holds only the
mention text, and is registered with any `LLMVerify` comparator of the
resolver so the comparator can look it up. Chunk ids come from the mention
position, so runs are repeatable.

**Parameters:**

- **resolver** (<code>[Resolver](ingestion.md#agrag-ingestion-resolve-resolver-Resolver)</code>) – The resolver under test.
- **mentions** (<code>Sequence\[str\]</code>) – The mention texts.
- **label** (<code>str</code>) – The entity label given to every mention.

**Returns:**

- <code>[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment)</code> – The predicted clusters with the counts of matches per comparator and
- <code>[ResolutionResult](ingestion.md#agrag-ingestion-resolve-resolver-ResolutionResult)</code> – of failed LLM requests, and the raw `ResolutionResult` whose match
- <code>tuple\[[ClusterAssignment](#agrag-eval-resolution-ClusterAssignment), [ResolutionResult](ingestion.md#agrag-ingestion-resolve-resolver-ResolutionResult)\]</code> – records carry the comparator that confirmed each pair.

### `agrag.eval.run_verifier` \{#agrag-eval-run_verifier}

```python
run_verifier(model:Any, items:Sequence[VerdictItem], *, concurrency:int = _CONCURRENCY) -> list[str]
```

Run the verifier over items and return one label per item.

A call that raises gives the label `ERROR`. It is wrong for every gold
class and shows in the report. It is never dropped.

**Parameters:**

- **model** (<code>Any</code>) – The chat model under test.
- **items** (<code>Sequence\[[VerdictItem](#agrag-eval-verifier-VerdictItem)\]</code>) – The fixed inputs.
- **concurrency** (<code>int</code>) – The most calls that run at once. Lower it for an endpoint
  that limits concurrent requests.

**Returns:**

- <code>list\[str\]</code> – One verdict label per item, in the order of `items`.

**Raises:**

- <code>ValueError</code> – `concurrency` is less than 1.

### `agrag.eval.settings` \{#agrag-eval-settings}

Env-backed configuration for the eval judge model.

**Classes:**

- [**EvalJudgeSettings**](#agrag-eval-settings-EvalJudgeSettings) – LLM client config for the eval judge.

#### `agrag.eval.settings.EvalJudgeSettings` \{#agrag-eval-settings-EvalJudgeSettings}

Bases: <code>BaseSettings</code>

LLM client config for the eval judge.

**Attributes:**

- [**client**](#agrag-eval-settings-EvalJudgeSettings-client) (<code>LLMClientConfig</code>) – The judge model's client config.
- [**temperature**](#agrag-eval-settings-EvalJudgeSettings-temperature) (<code>Annotated\[float | None, NoDecode\]</code>) – The sampling temperature the judge sends. `None` sends
  none, for models that reject the parameter. Set
  `EVAL_JUDGE_TEMPERATURE` empty to get `None`.
  Env: `EVAL_JUDGE_TEMPERATURE`.

Env prefix: `EVAL_JUDGE_`.

**Functions:**

- [**from_openai_compatible_env**](#agrag-eval-settings-EvalJudgeSettings-from_openai_compatible_env) – Build settings from OpenAI-compatible env vars.

##### `agrag.eval.settings.EvalJudgeSettings.client` \{#agrag-eval-settings-EvalJudgeSettings-client}

```python
client: LLMClientConfig
```

##### `agrag.eval.settings.EvalJudgeSettings.from_openai_compatible_env` \{#agrag-eval-settings-EvalJudgeSettings-from_openai_compatible_env}

```python
from_openai_compatible_env() -> EvalJudgeSettings
```

Build settings from OpenAI-compatible env vars.

Loads `.env` first, then resolves `EVAL_JUDGE_BASE_URL`,
`EVAL_JUDGE_API_KEY` and `EVAL_JUDGE_MODEL_ID` through
pydantic-settings. Each falls back to the shared `LLM_*` variable
when unset or empty, so the judge is the agent's own model unless
`EVAL_JUDGE_*` is set. That model grades its own answers, which
biases scores upward. There is no default model.

**Returns:**

- <code>[EvalJudgeSettings](#agrag-eval-settings-EvalJudgeSettings)</code> – EvalJudgeSettings with one openai-generic client.

**Raises:**

- <code>ValueError</code> – No model id resolves from either set of variables.

##### `agrag.eval.settings.EvalJudgeSettings.model_config` \{#agrag-eval-settings-EvalJudgeSettings-model_config}

```python
model_config = SettingsConfigDict(env_prefix='EVAL_JUDGE_', env_file='.env', extra='ignore', hide_input_in_errors=True)
```

##### `agrag.eval.settings.EvalJudgeSettings.temperature` \{#agrag-eval-settings-EvalJudgeSettings-temperature}

```python
temperature: Annotated[float | None, NoDecode] = 0.0
```

### `agrag.eval.task_completion` \{#agrag-eval-task_completion}

```python
task_completion(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the judged metric for task completion.

Scores whether the run achieved the question's goal, from the question,
the answer and the tool calls, with one judge call. The gate is the mean
over questions, following the answer-quality eval, so no median of
repeated calls is needed.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The task completion metric.

### `agrag.eval.to_json_case` \{#agrag-eval-to_json_case}

```python
to_json_case(input:str, actual:BaseModel, expected:BaseModel) -> LLMTestCase
```

Build a test case that carries structured data as JSON.

`LLMTestCase` has no field for structured gold data, so both models are
serialized to JSON in `actual_output` and `expected_output`. The JSON
also shows in DeepEval reports.

**Parameters:**

- **input** (<code>str</code>) – The input text, such as a question or a chunk.
- **actual** (<code>BaseModel</code>) – The system output.
- **expected** (<code>BaseModel</code>) – The gold data.

### `agrag.eval.trajectory` \{#agrag-eval-trajectory}

Agent trajectory evaluation: read runs, check structure, judge quality.

A trajectory is the ordered tool and model steps of one agent run, read from
its OpenTelemetry spans (see `agrag.agents.tracing`). Structural rules over
it are deterministic; task completion and trajectory quality use an LLM judge.

**Classes:**

- [**SpanCapture**](#agrag-eval-trajectory-SpanCapture) – Capture one agent run's spans for `read_trajectory`.
- [**Step**](#agrag-eval-trajectory-Step) – One tool or model step of an agent run.
- [**Trajectory**](#agrag-eval-trajectory-Trajectory) – The ordered steps of one agent run.

**Functions:**

- [**expected_tools_metric**](#agrag-eval-trajectory-expected_tools_metric) – Build the metric that the run called every expected tool.
- [**read_trajectory**](#agrag-eval-trajectory-read_trajectory) – Read the tool and model steps from finished spans.
- [**retry_budget_metric**](#agrag-eval-trajectory-retry_budget_metric) – Build the metric that retries stay within budget.
- [**task_completion**](#agrag-eval-trajectory-task_completion) – Build the judged metric for task completion.
- [**trajectory_case**](#agrag-eval-trajectory-trajectory_case) – Build the test case every trajectory metric scores.
- [**trajectory_quality**](#agrag-eval-trajectory-trajectory_quality) – Build the judged metric for trajectory quality.
- [**verifier_before_answer_metric**](#agrag-eval-trajectory-verifier_before_answer_metric) – Build the metric that the verifier ran before the answer.

#### `agrag.eval.trajectory.SpanCapture` \{#agrag-eval-trajectory-SpanCapture}

```python
SpanCapture() -> None
```

Capture one agent run's spans for `read_trajectory`.

Use as a context manager around `agent.ainvoke` and read the run with
`trajectory()` after. Each capture has its own provider and exporter,
so captures never share spans and the global provider is unchanged.

<details open>
<summary>Example</summary>

```python
with SpanCapture() as capture:
    agent = build_agent(engine, settings, tracer=capture.tracer)
    result = await agent.ainvoke({"messages": [...]})
trajectory = capture.trajectory()
```

</details>

**Functions:**

- [**trajectory**](#agrag-eval-trajectory-SpanCapture-trajectory) – Read the captured spans as a trajectory.

**Attributes:**

- [**tracer**](#agrag-eval-trajectory-SpanCapture-tracer) (<code>Tracer</code>) – The tracer to pass as `tracer=` to `build_agent`.

##### `agrag.eval.trajectory.SpanCapture.tracer` \{#agrag-eval-trajectory-SpanCapture-tracer}

```python
tracer: Tracer
```

The tracer to pass as `tracer=` to `build_agent`.

**Returns:**

- <code>Tracer</code> – A tracer bound to this capture's private provider.

##### `agrag.eval.trajectory.SpanCapture.trajectory` \{#agrag-eval-trajectory-SpanCapture-trajectory}

```python
trajectory() -> Trajectory
```

Read the captured spans as a trajectory.

**Returns:**

- <code>[Trajectory](#agrag-eval-trajectory-Trajectory)</code> – The trajectory read from the spans captured so far.

#### `agrag.eval.trajectory.Step` \{#agrag-eval-trajectory-Step}

Bases: <code>BaseModel</code>

One tool or model step of an agent run.

**Attributes:**

- [**kind**](#agrag-eval-trajectory-Step-kind) (<code>Literal['tool', 'llm']</code>) – `"tool"` for a tool call, `"llm"` for a model call.
- [**name**](#agrag-eval-trajectory-Step-name) (<code>str</code>) – The tool name, or the span name for a model call.
- [**args**](#agrag-eval-trajectory-Step-args) (<code>dict\[str, Any\]</code>) – The parsed `input.value` span attribute.
- [**output**](#agrag-eval-trajectory-Step-output) (<code>str</code>) – The step's output text, unwrapped from its tool message.
- [**span_id**](#agrag-eval-trajectory-Step-span_id) (<code>str</code>) – The span id as hex.
- [**parent_ids**](#agrag-eval-trajectory-Step-parent_ids) (<code>list\[str\]</code>) – The ancestor span ids, nearest first, as hex.
- [**started**](#agrag-eval-trajectory-Step-started) (<code>int</code>) – Start time in nanoseconds.
- [**ended**](#agrag-eval-trajectory-Step-ended) (<code>int</code>) – End time in nanoseconds.
- [**subagent**](#agrag-eval-trajectory-Step-subagent) (<code>str | None</code>) – The `subagent_type` of the nearest ancestor `task`
  span, or None for a planner step.

##### `agrag.eval.trajectory.Step.args` \{#agrag-eval-trajectory-Step-args}

```python
args: dict[str, Any]
```

##### `agrag.eval.trajectory.Step.ended` \{#agrag-eval-trajectory-Step-ended}

```python
ended: int
```

##### `agrag.eval.trajectory.Step.kind` \{#agrag-eval-trajectory-Step-kind}

```python
kind: Literal['tool', 'llm']
```

##### `agrag.eval.trajectory.Step.name` \{#agrag-eval-trajectory-Step-name}

```python
name: str
```

##### `agrag.eval.trajectory.Step.output` \{#agrag-eval-trajectory-Step-output}

```python
output: str
```

##### `agrag.eval.trajectory.Step.parent_ids` \{#agrag-eval-trajectory-Step-parent_ids}

```python
parent_ids: list[str]
```

##### `agrag.eval.trajectory.Step.span_id` \{#agrag-eval-trajectory-Step-span_id}

```python
span_id: str
```

##### `agrag.eval.trajectory.Step.started` \{#agrag-eval-trajectory-Step-started}

```python
started: int
```

##### `agrag.eval.trajectory.Step.subagent` \{#agrag-eval-trajectory-Step-subagent}

```python
subagent: str | None
```

#### `agrag.eval.trajectory.Trajectory` \{#agrag-eval-trajectory-Trajectory}

Bases: <code>BaseModel</code>

The ordered steps of one agent run.

**Attributes:**

- [**steps**](#agrag-eval-trajectory-Trajectory-steps) (<code>list\[[Step](#agrag-eval-trajectory-Step)\]</code>) – The run's tool and model steps in start order.

##### `agrag.eval.trajectory.Trajectory.steps` \{#agrag-eval-trajectory-Trajectory-steps}

```python
steps: list[Step]
```

#### `agrag.eval.trajectory.expected_tools_metric` \{#agrag-eval-trajectory-expected_tools_metric}

```python
expected_tools_metric(names:Sequence[str], *, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that the run called every expected tool.

Compares the trajectory's tool calls with the expected names as a
superset, ignoring arguments: extra tools do not matter, a missing name
fails. Scores 1.0 or 0.0.

**Parameters:**

- **names** (<code>Sequence\[str\]</code>) – The tool names the run must include.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A `ScoreMetric` that scores tool presence.

#### `agrag.eval.trajectory.read_trajectory` \{#agrag-eval-trajectory-read_trajectory}

```python
read_trajectory(spans:Sequence[ReadableSpan]) -> Trajectory
```

Read the tool and model steps from finished spans.

Keeps `TOOL` and `LLM` spans, drops `CHAIN` spans, and orders steps
by start time rather than export order. Skips spans `agrag` opens
itself and spans nested under an `agrag.eval.judge` span, so judge
calls and BAML request spans never read as planner steps. A step's
`subagent` is the `subagent_type` of its nearest ancestor `task`
span, or None for a planner step.

**Parameters:**

- **spans** (<code>Sequence\[ReadableSpan\]</code>) – The finished spans of one traced agent run.

**Returns:**

- <code>[Trajectory](#agrag-eval-trajectory-Trajectory)</code> – The run's trajectory in start order.

#### `agrag.eval.trajectory.retry_budget_metric` \{#agrag-eval-trajectory-retry_budget_metric}

```python
retry_budget_metric(max_attempts:int, *, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that retries stay within budget.

Counts researcher `task` spans starting after the first verifier
`task` span ended. A call the limiter blocks leaves no span, so only
executed delegations count. Scores 1.0 or 0.0.

**Parameters:**

- **max_attempts** (<code>int</code>) – How many researcher retries after verification pass.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A `ScoreMetric` that scores the retry budget.

#### `agrag.eval.trajectory.task_completion` \{#agrag-eval-trajectory-task_completion}

```python
task_completion(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the judged metric for task completion.

Scores whether the run achieved the question's goal, from the question,
the answer and the tool calls, with one judge call. The gate is the mean
over questions, following the answer-quality eval, so no median of
repeated calls is needed.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The task completion metric.

#### `agrag.eval.trajectory.trajectory_case` \{#agrag-eval-trajectory-trajectory_case}

```python
trajectory_case(question:str, answer:str, trajectory:Trajectory) -> LLMTestCase
```

Build the test case every trajectory metric scores.

`tools_called` holds every `TOOL` step, planner and researcher, as a
`ToolCall`. `metadata["trajectory"]` holds the serialized trajectory
the deterministic metrics read.

**Parameters:**

- **question** (<code>str</code>) – The question the agent answered.
- **answer** (<code>str</code>) – The agent's final answer.
- **trajectory** (<code>[Trajectory](#agrag-eval-trajectory-Trajectory)</code>) – The run's trajectory from `read_trajectory`.

**Returns:**

- <code>LLMTestCase</code> – The test case with the answer, the tool calls and the trajectory.

#### `agrag.eval.trajectory.trajectory_quality` \{#agrag-eval-trajectory-trajectory_quality}

```python
trajectory_quality(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the judged metric for trajectory quality.

Scores whether the steps follow logically from the question, with no
reference trajectory and one judge call. The gate is the mean over
questions, following the answer-quality eval.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model. Its chat model grades the trajectory.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The trajectory quality metric.

**Raises:**

- <code>TypeError</code> – The judge holds no LangChain chat model.

#### `agrag.eval.trajectory.verifier_before_answer_metric` \{#agrag-eval-trajectory-verifier_before_answer_metric}

```python
verifier_before_answer_metric(*, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that the verifier ran before the answer.

Passes when the planner's last `LLM` span starts after at least one
verifier `task` span ended. Scores 1.0 or 0.0.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A `ScoreMetric` that scores verifier-before-answer.

### `agrag.eval.trajectory_case` \{#agrag-eval-trajectory_case}

```python
trajectory_case(question:str, answer:str, trajectory:Trajectory) -> LLMTestCase
```

Build the test case every trajectory metric scores.

`tools_called` holds every `TOOL` step, planner and researcher, as a
`ToolCall`. `metadata["trajectory"]` holds the serialized trajectory
the deterministic metrics read.

**Parameters:**

- **question** (<code>str</code>) – The question the agent answered.
- **answer** (<code>str</code>) – The agent's final answer.
- **trajectory** (<code>[Trajectory](#agrag-eval-trajectory-Trajectory)</code>) – The run's trajectory from `read_trajectory`.

**Returns:**

- <code>LLMTestCase</code> – The test case with the answer, the tool calls and the trajectory.

### `agrag.eval.trajectory_quality` \{#agrag-eval-trajectory_quality}

```python
trajectory_quality(judge:DeepEvalBaseLLM, *, threshold:float = 0.5) -> BaseMetric
```

Build the judged metric for trajectory quality.

Scores whether the steps follow logically from the question, with no
reference trajectory and one judge call. The gate is the mean over
questions, following the answer-quality eval.

**Parameters:**

- **judge** (<code>DeepEvalBaseLLM</code>) – The judge model. Its chat model grades the trajectory.
- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>BaseMetric</code> – The trajectory quality metric.

**Raises:**

- <code>TypeError</code> – The judge holds no LangChain chat model.

### `agrag.eval.verdict_case` \{#agrag-eval-verdict_case}

```python
verdict_case(item:VerdictItem, predicted:str) -> LLMTestCase
```

Build a test case with the predicted and the gold verdict.

**Parameters:**

- **item** (<code>[VerdictItem](#agrag-eval-verifier-VerdictItem)</code>) – The fixed input.
- **predicted** (<code>str</code>) – The label from `run_verifier`.

**Returns:**

- <code>LLMTestCase</code> – An `LLMTestCase` with the question, predicted verdict and gold verdict.

### `agrag.eval.verdict_match_metric` \{#agrag-eval-verdict_match_metric}

```python
verdict_match_metric(*, threshold:float = 0.0) -> ScoreMetric
```

Build a metric that scores 1.0 when the verdict equals the gold verdict.

The default threshold is 0 because the gate belongs on the macro F1 of
`verdict_report`.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum case score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A `ScoreMetric` that scores verdict equality against `threshold`.

### `agrag.eval.verdict_report` \{#agrag-eval-verdict_report}

```python
verdict_report(gold:Sequence[str], predicted:Sequence[str]) -> VerdictReport
```

Score predicted verdicts against gold verdicts.

**Parameters:**

- **gold** (<code>Sequence\[str\]</code>) – The gold label of each item.
- **predicted** (<code>Sequence\[str\]</code>) – The label of each item from `run_verifier`.

**Returns:**

- <code>[VerdictReport](#agrag-eval-verifier-VerdictReport)</code> – Per-class scores, macro F1, the confusion matrix and the error count.

### `agrag.eval.verifier` \{#agrag-eval-verifier}

Verifier calibration: does the verifier give the right verdict?

Each item is a fixed `(question, sub-questions, findings)` input with a gold
verdict. The verdict and the gold label are both one of three values, so scoring
is an equality check and needs no judge. `verdict_report` gives per-class
precision, recall and F1, the macro F1 that gates, and a confusion matrix.

**Classes:**

- [**ClassScores**](#agrag-eval-verifier-ClassScores) – Precision, recall and F1 of one verdict class.
- [**VerdictItem**](#agrag-eval-verifier-VerdictItem) – One fixed verifier input with its gold verdict.
- [**VerdictReport**](#agrag-eval-verifier-VerdictReport) – Scores of predicted verdicts against gold verdicts.

**Functions:**

- [**run_verifier**](#agrag-eval-verifier-run_verifier) – Run the verifier over items and return one label per item.
- [**verdict_case**](#agrag-eval-verifier-verdict_case) – Build a test case with the predicted and the gold verdict.
- [**verdict_match_metric**](#agrag-eval-verifier-verdict_match_metric) – Build a metric that scores 1.0 when the verdict equals the gold verdict.
- [**verdict_report**](#agrag-eval-verifier-verdict_report) – Score predicted verdicts against gold verdicts.

#### `agrag.eval.verifier.ClassScores` \{#agrag-eval-verifier-ClassScores}

Bases: <code>BaseModel</code>

Precision, recall and F1 of one verdict class.

**Attributes:**

- [**f1**](#agrag-eval-verifier-ClassScores-f1) (<code>float</code>) –
- [**precision**](#agrag-eval-verifier-ClassScores-precision) (<code>float</code>) –
- [**recall**](#agrag-eval-verifier-ClassScores-recall) (<code>float</code>) –

##### `agrag.eval.verifier.ClassScores.f1` \{#agrag-eval-verifier-ClassScores-f1}

```python
f1: float
```

##### `agrag.eval.verifier.ClassScores.precision` \{#agrag-eval-verifier-ClassScores-precision}

```python
precision: float
```

##### `agrag.eval.verifier.ClassScores.recall` \{#agrag-eval-verifier-ClassScores-recall}

```python
recall: float
```

#### `agrag.eval.verifier.VerdictItem` \{#agrag-eval-verifier-VerdictItem}

Bases: <code>BaseModel</code>

One fixed verifier input with its gold verdict.

**Attributes:**

- [**id**](#agrag-eval-verifier-VerdictItem-id) (<code>str</code>) – A stable id for the item.
- [**question**](#agrag-eval-verifier-VerdictItem-question) (<code>str</code>) – The original question.
- [**sub_questions**](#agrag-eval-verifier-VerdictItem-sub_questions) (<code>list\[str\]</code>) – The sub-questions the question was split into.
- [**findings**](#agrag-eval-verifier-VerdictItem-findings) (<code>str</code>) – The findings text with citation keys such as `E1`.
- [**gold**](#agrag-eval-verifier-VerdictItem-gold) (<code>Literal['PASS', 'INSUFFICIENT', 'CONTRADICTORY']</code>) – The verdict the verifier should give.
- [**human_reviewed**](#agrag-eval-verifier-VerdictItem-human_reviewed) (<code>bool</code>) – True when a person confirmed the gold label.

##### `agrag.eval.verifier.VerdictItem.findings` \{#agrag-eval-verifier-VerdictItem-findings}

```python
findings: str
```

##### `agrag.eval.verifier.VerdictItem.gold` \{#agrag-eval-verifier-VerdictItem-gold}

```python
gold: Literal['PASS', 'INSUFFICIENT', 'CONTRADICTORY']
```

##### `agrag.eval.verifier.VerdictItem.human_reviewed` \{#agrag-eval-verifier-VerdictItem-human_reviewed}

```python
human_reviewed: bool = False
```

##### `agrag.eval.verifier.VerdictItem.id` \{#agrag-eval-verifier-VerdictItem-id}

```python
id: str
```

##### `agrag.eval.verifier.VerdictItem.question` \{#agrag-eval-verifier-VerdictItem-question}

```python
question: str
```

##### `agrag.eval.verifier.VerdictItem.sub_questions` \{#agrag-eval-verifier-VerdictItem-sub_questions}

```python
sub_questions: list[str]
```

#### `agrag.eval.verifier.VerdictReport` \{#agrag-eval-verifier-VerdictReport}

Bases: <code>BaseModel</code>

Scores of predicted verdicts against gold verdicts.

**Attributes:**

- [**labels**](#agrag-eval-verifier-VerdictReport-labels) (<code>list\[str\]</code>) – The class order of `confusion_matrix`.
- [**per_class**](#agrag-eval-verifier-VerdictReport-per_class) (<code>dict\[str, [ClassScores](#agrag-eval-verifier-ClassScores)\]</code>) – Scores for each class.
- [**macro_f1**](#agrag-eval-verifier-VerdictReport-macro_f1) (<code>float</code>) – The mean F1 over the three classes.
- [**confusion_matrix**](#agrag-eval-verifier-VerdictReport-confusion_matrix) (<code>list\[list\[int\]\]</code>) – Counts with gold classes as rows and predicted classes
  as columns. A prediction of `ERROR` is in no column.
- [**errors**](#agrag-eval-verifier-VerdictReport-errors) (<code>int</code>) – The number of `ERROR` predictions. Each one is a miss for
  the gold class of its item.

##### `agrag.eval.verifier.VerdictReport.confusion_matrix` \{#agrag-eval-verifier-VerdictReport-confusion_matrix}

```python
confusion_matrix: list[list[int]]
```

##### `agrag.eval.verifier.VerdictReport.errors` \{#agrag-eval-verifier-VerdictReport-errors}

```python
errors: int
```

##### `agrag.eval.verifier.VerdictReport.labels` \{#agrag-eval-verifier-VerdictReport-labels}

```python
labels: list[str]
```

##### `agrag.eval.verifier.VerdictReport.macro_f1` \{#agrag-eval-verifier-VerdictReport-macro_f1}

```python
macro_f1: float
```

##### `agrag.eval.verifier.VerdictReport.per_class` \{#agrag-eval-verifier-VerdictReport-per_class}

```python
per_class: dict[str, ClassScores]
```

#### `agrag.eval.verifier.run_verifier` \{#agrag-eval-verifier-run_verifier}

```python
run_verifier(model:Any, items:Sequence[VerdictItem], *, concurrency:int = _CONCURRENCY) -> list[str]
```

Run the verifier over items and return one label per item.

A call that raises gives the label `ERROR`. It is wrong for every gold
class and shows in the report. It is never dropped.

**Parameters:**

- **model** (<code>Any</code>) – The chat model under test.
- **items** (<code>Sequence\[[VerdictItem](#agrag-eval-verifier-VerdictItem)\]</code>) – The fixed inputs.
- **concurrency** (<code>int</code>) – The most calls that run at once. Lower it for an endpoint
  that limits concurrent requests.

**Returns:**

- <code>list\[str\]</code> – One verdict label per item, in the order of `items`.

**Raises:**

- <code>ValueError</code> – `concurrency` is less than 1.

#### `agrag.eval.verifier.verdict_case` \{#agrag-eval-verifier-verdict_case}

```python
verdict_case(item:VerdictItem, predicted:str) -> LLMTestCase
```

Build a test case with the predicted and the gold verdict.

**Parameters:**

- **item** (<code>[VerdictItem](#agrag-eval-verifier-VerdictItem)</code>) – The fixed input.
- **predicted** (<code>str</code>) – The label from `run_verifier`.

**Returns:**

- <code>LLMTestCase</code> – An `LLMTestCase` with the question, predicted verdict and gold verdict.

#### `agrag.eval.verifier.verdict_match_metric` \{#agrag-eval-verifier-verdict_match_metric}

```python
verdict_match_metric(*, threshold:float = 0.0) -> ScoreMetric
```

Build a metric that scores 1.0 when the verdict equals the gold verdict.

The default threshold is 0 because the gate belongs on the macro F1 of
`verdict_report`.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum case score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A `ScoreMetric` that scores verdict equality against `threshold`.

#### `agrag.eval.verifier.verdict_report` \{#agrag-eval-verifier-verdict_report}

```python
verdict_report(gold:Sequence[str], predicted:Sequence[str]) -> VerdictReport
```

Score predicted verdicts against gold verdicts.

**Parameters:**

- **gold** (<code>Sequence\[str\]</code>) – The gold label of each item.
- **predicted** (<code>Sequence\[str\]</code>) – The label of each item from `run_verifier`.

**Returns:**

- <code>[VerdictReport](#agrag-eval-verifier-VerdictReport)</code> – Per-class scores, macro F1, the confusion matrix and the error count.

### `agrag.eval.verifier_before_answer_metric` \{#agrag-eval-verifier_before_answer_metric}

```python
verifier_before_answer_metric(*, threshold:float = 0.5) -> ScoreMetric
```

Build the metric that the verifier ran before the answer.

Passes when the planner's last `LLM` span starts after at least one
verifier `task` span ended. Scores 1.0 or 0.0.

**Parameters:**

- **threshold** (<code>float</code>) – The minimum score that counts as success.

**Returns:**

- <code>[ScoreMetric](#agrag-eval-adapter-ScoreMetric)</code> – A `ScoreMetric` that scores verifier-before-answer.
