---
title: agrag.eval
sidebar_position: 6
---


# `agrag.eval` \{#agrag-eval}

Public evaluation metrics for agrag, built on DeepEval and AgentEvals.

Needs the `eval` extra: `pip install 'agentic-graphrag[eval]'`.

**Modules:**

- [**adapter**](adapter/index.md) – Adapters that let plain scoring functions report through DeepEval.
- [**answer**](answer/index.md) – Answer-quality metrics for agrag, scored from questions and reference answers.
- [**extraction**](extraction/index.md) – Extraction quality: entity and relation-triple F1 against gold annotations.
- [**judge**](judge/index.md) – A DeepEval judge model backed by an agrag chat model.
- [**resolution**](resolution/index.md) – Resolution quality: B-cubed and pairwise scores of mention clusters.
- [**settings**](settings/index.md) – Env-backed configuration for the eval judge model.
- [**trajectory**](trajectory/index.md) – Agent trajectory evaluation: read runs, check structure, judge quality.
- [**verifier**](verifier/index.md) – Verifier calibration: does the verifier give the right verdict?

**Classes:**

- [**ChatModelJudge**](ChatModelJudge.md) – Wrap a LangChain chat model as a DeepEval judge.
- [**CitationAccuracyMetric**](CitationAccuracyMetric.md) – Score whether each cited sentence follows from the evidence it cites.
- [**CitationScoreBreakdown**](CitationScoreBreakdown.md) – Available precision, recall, and sentence-count fields for one score.
- [**CitationSentenceRow**](CitationSentenceRow.md) – One cited sentence and its support verdict, for the report.
- [**ClusterAssignment**](ClusterAssignment.md) – A grouping of mentions, listed by position in the mention list.
- [**EvalJudgeSettings**](EvalJudgeSettings.md) – LLM client config for the eval judge.
- [**ExtractionGold**](ExtractionGold.md) – One gold-annotated chunk of text.
- [**MicroScores**](MicroScores.md) – Dataset scores pooled over every item, for entities and relations.
- [**ScoreMetric**](ScoreMetric.md) – A DeepEval metric backed by a plain scoring function.
- [**ScoreResult**](ScoreResult.md) – The outcome of one scoring function call.
- [**Scores**](Scores.md) – Precision, recall and F1.
- [**SpanCapture**](SpanCapture.md) – Capture one agent run's spans for `read_trajectory`.
- [**Trajectory**](Trajectory-ref.md) – The ordered steps of one agent run.
- [**VerdictItem**](VerdictItem.md) – One fixed verifier input with its gold verdict.
- [**VerdictReport**](VerdictReport.md) – Scores of predicted verdicts against gold verdicts.

**Functions:**

- [**answer_case**](answer_case.md) – Build the test case that every answer-quality metric scores.
- [**cluster_quality_metric**](cluster_quality_metric.md) – Build a metric for cluster quality on one test case.
- [**context_precision**](context_precision.md) – Build the metric for useful evidence ranked before noise.
- [**context_recall**](context_recall.md) – Build the metric for reference facts that the evidence covers.
- [**correctness**](correctness.md) – Build the answer correctness metric against the reference.
- [**entity_quality_metric**](entity_quality_metric.md) – Build a metric for entity F1 on one test case.
- [**expected_tools_metric**](expected_tools_metric.md) – Build the metric that the run called every expected tool.
- [**extraction_case**](extraction_case.md) – Build a test case that holds a predicted and a gold extraction.
- [**faithfulness**](faithfulness.md) – Build the metric for claims that the evidence the agent saw does not contradict.
- [**final_answer**](final_answer.md) – Return the text of the last assistant message in an agent run.
- [**micro_scores**](micro_scores.md) – Pool measured entity and relation metrics into dataset scores.
- [**parse_json_case**](parse_json_case.md) – Read the `(actual, expected)` models back from a JSON test case.
- [**read_trajectory**](read_trajectory.md) – Read the tool and model steps from finished spans.
- [**relation_quality_metric**](relation_quality_metric.md) – Build a metric for relation triple F1 on one test case.
- [**resolution_case**](resolution_case.md) – Build a test case that holds predicted and gold clusters.
- [**retry_budget_metric**](retry_budget_metric.md) – Build the metric that retries stay within budget.
- [**run_extractor**](run_extractor.md) – Run an extractor over gold items and build one test case per item.
- [**run_resolver**](run_resolver.md) – Resolve mention strings and return the clusters the resolver forms.
- [**run_resolver_detailed**](run_resolver_detailed.md) – Resolve mention strings and return the clusters plus raw evidence.
- [**run_verifier**](run_verifier.md) – Run the verifier over items and return one label per item.
- [**task_completion**](task_completion.md) – Build the judged metric for task completion.
- [**to_json_case**](to_json_case.md) – Build a test case that carries structured data as JSON.
- [**trajectory_case**](trajectory_case.md) – Build the test case every trajectory metric scores.
- [**trajectory_quality**](trajectory_quality.md) – Build the judged metric for trajectory quality.
- [**verdict_case**](verdict_case.md) – Build a test case with the predicted and the gold verdict.
- [**verdict_match_metric**](verdict_match_metric.md) – Build a metric that scores 1.0 when the verdict equals the gold verdict.
- [**verdict_report**](verdict_report.md) – Score predicted verdicts against gold verdicts.
- [**verifier_before_answer_metric**](verifier_before_answer_metric.md) – Build the metric that the verifier ran before the answer.
